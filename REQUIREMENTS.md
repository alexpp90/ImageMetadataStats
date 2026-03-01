# Image Metadata Analyzer - Requirements Documentation

This document serves as the central source of truth for the functional, architectural, and business requirements of the Image Metadata Analyzer project. It must be kept up-to-date as new features are added or existing features are modified.

## 1. Introduction
The Image Metadata Analyzer is a cross-platform desktop application designed to process folders of images. It extracts and analyzes EXIF metadata (Shutter Speed, Aperture, ISO, Focal Length, Lens Model), generates statistical distributions, and provides advanced tools such as an Image Comparator (for detecting sharpness and blur) and a Duplicate Finder.

## 2. Core Features & Business Logic

### 2.1 Metadata Extraction and Analysis
*   **EXIF Data Standardization:** Extracted EXIF data must standardize on explicit keys: `Aperture` and `Shutter Speed`. Downstream consumers (e.g., the GUI) must rely on these standardized keys, avoiding raw tags like `FNumber` or `ExposureTime`.
*   **Focal Length Exclusions:** Statistical aggregations and plotting for Focal Length must explicitly exclude values less than or equal to `0.0 mm` to prevent division-by-zero errors.
*   **Shutter Speed Formatting:** In the GUI, shutter speed values less than `1.0` and greater than `0` must be formatted as fractions (e.g., `1/200s`). Values `1.0` or greater must be appended with `s` (e.g., `1.5s`).
*   **Supported File Types:** Supported file extensions are defined centrally in `src/image_metadata_analyzer/reader.py` as `SUPPORTED_EXTENSIONS`. Other tools (like `duplicates.py`) must import this list and may extend it locally (e.g., appending `.bmp` and `.gif`).

### 2.2 Image Comparator (Sharpness Tool)
*   **Sharpness Algorithm:** The sharpness analysis algorithm crops the center 50% of the image, divides it into a configurable grid (default 8x8), and uses the maximum block variance score to determine overall sharpness.
*   **Synchronous Pre-loading:** The application must synchronously pre-load all supported images from a selected folder for immediate side-by-side review prior to scanning, displaying metadata alongside 'N/A' placeholder scores initially.
*   **Score Labeling:** The evaluation metric must be explicitly labeled as "Sharpness Score" in the GUI (rather than just "Score").

### 2.3 Duplicate Finder
*   **Detection Logic:** Duplicate image detection utilizes MD5 hashing of file content.
*   **Deletion Strategy:** The utility first attempts to move files to the trash using `send2trash`.
*   **Deletion Error Handling:** If `send2trash` fails (e.g., on network drives), the backend utility (`move_to_trash`) must raise an exception rather than returning a boolean status. The GUI layer is responsible for catching this exception and prompting the user for a fallback to permanent deletion (`Path.unlink()`).

## 3. User Interface (GUI) Requirements

### 3.1 Layout and Rendering Constraints
*   **Responsive Scaling:** To prevent infinite resize loops, image labels that dynamically scale must be wrapped in `ttk.Frame` containers using `pack_propagate(False)` and `grid_propagate(False)`.
*   **Grid Weights:** Parent frames containing these constrained child frames must have explicit `rowconfigure` and `columnconfigure` weights assigned so the frame does not collapse and hide its contents.
*   **Resize Optimization:** Image resizing via `<Configure>` events must be optimized by caching `_last_width` and `_last_height` to prevent redundant processing, and the events must be debounced to stop continuous loops.
*   **Unscaled References:** The application must explicitly store the raw, unscaled `pil_image` to support high-quality responsive resizing when window adjustments occur.
*   **Preloader Cache:** The background image preloader cache size (`CACHE_SIZE`) must be strictly set to 1200x900 to guarantee high-resolution images for responsive UI scaling.

### 3.2 Display Modes (Sharpness Tool)
*   **Standard Mode Layout:** The current image is centered in the top row, with previous/next images side-by-side in the bottom row.
*   **Focus Mode Layout:** Hides the sidebar. Uses a grid layout where the top row is split evenly (weight=1 for both columns) between the current image and controls panel. The bottom row splits the previous and next images evenly, ensuring all three displayed images share the exact same dimensions.
*   **Image Reloading:** Switching views (Standard vs. Focus) triggers a reload of the image triplet to ensure the correct resolution is generated for the specific layout.
*   **Navigation Interactions:** In Focus Mode, clicking a non-central image (Previous/Next) must open it in a fullscreen viewer (via `tk.Toplevel`) instead of making it the new current image.

### 3.3 State and Interaction Management
*   **Thread Safety:** PIL Image objects must be loaded in background threads. Unscaled PIL images are returned and dynamically converted to `ImageTk.PhotoImage` in the main thread during `<Configure>` events.
*   **Tkinter Variable Access:** Access to Tkinter variables (`StringVar`, `IntVar`) must occur only in the main thread. Values must be passed as arguments to worker threads.
*   **Data Formatting Safety:** UI elements processing dynamically loaded scores must utilize explicit type checks (e.g., `isinstance(score_val, float)`) to safely format numerical data and prevent errors from 'N/A' string defaults.
*   **State Transitions:** The Sharpness Tool auto-switches to the Review tab *only* when an analysis scan is explicitly started. It must remain on the Configuration tab immediately after the initial folder selection.
*   **Error Reporting:** Analysis errors in the GUI must be displayed via a popup alert, and the progress bar state must reflect the failure (it must not auto-complete).
*   **Image RAW Loading:** The utility function `utils.load_image_preview` must explicitly convert images to `RGB` mode to handle 16-bit RAW data (`I;16`) that otherwise causes `ImageTk` crashes.

## 4. Technical & Architectural Requirements

### 4.1 Required Dependencies
*   **Runtime:** `opencv-python` and `rawpy` must be declared as main project dependencies (not development dependencies) to ensure they are bundled correctly by PyInstaller for runtime sharpness analysis.
*   **Type Hinting:** Development environments require `types-setuptools`, `types-tqdm`, `types-ExifRead`, `types-Pillow`, `types-requests`, and `types-Send2Trash` to pass Mypy static analysis.
*   **Backward Compatibility:** `reader.py` must use a `hasattr` check and type ignore for `_getexif` to support older Pillow versions while satisfying strict Mypy checks.

### 4.2 Build Scripts
*   **Splash Screen:** The application startup includes a splash screen (`assets/logo.png`) configured via the PyInstaller `--splash` argument. The `MainApp` class must close the splash screen via `pyi_splash.close()` inside a `try/except` block, scheduled via `after()` to run after GUI initialization.
*   **ExifTool Bundling:** The build script (`scripts/build.py`) relies on a hardcoded ExifTool version (e.g., 13.51) downloaded from SourceForge. This requires manual updates if SourceForge removes older releases. Windows builds must utilize the `_64` suffixed ExifTool binary.
*   **macOS Security:** The build script must apply ad-hoc code signing (`codesign -s -`) to the macOS `.app` bundle to prevent Gatekeeper from flagging it as damaged on Apple Silicon.

## 5. Build & Deployment (CI/CD)

### 5.1 GitHub Actions Workflow
*   **Matrix Strategy:** The build workflow uses an `architecture` matrix strategy to explicitly define `x64` or `arm64` Python environments.
*   **Runner Requirements:** Windows builds target the `windows-latest` runner (x64). MacOS builds must strictly target `macos-latest` (Apple Silicon/ARM64); legacy Intel and macOS v15+ specific builds are deprecated.
*   **Archive Creation:** The build workflow must use `zip -r -y` on Unix systems (to preserve symlinks) and `shutil.make_archive` on Windows for creating release archives.
*   **Artifact Naming:** Artifacts must be named exactly as follows:
    *   `image-metadata-analyzer-linux-x64`
    *   `image-metadata-analyzer-windows-x64`
    *   `image-metadata-analyzer-macos-apple-silicon`

### 5.2 Release Management
*   **Permissions:** GitHub Actions require `permissions: contents: write` to allow the workflow to create and update releases.
*   **Publishing Strategy:** The project utilizes `softprops/action-gh-release` to automatically publish artifacts to the `nightly` tag on every push to the `main` branch.

## 6. Testing Requirements

*   **GUI Unit Tests:** Tests validating GUI components (e.g., `tests/test_sharpness_gui_basic.py`) require extensive mocking of `tkinter`, `PIL`, and `image_metadata_analyzer` dependencies due to the lack of a display environment in CI runners.
*   **Headless Execution:** To run or test standalone Tkinter GUI scripts headlessly in the development environment, developers must use `xvfb-run` (e.g., `poetry run xvfb-run python3 script.py`) to avoid `_tkinter.TclError` exceptions.
*   **Execution Command:** Tests should be executed using `poetry run pytest tests/` after ensuring dependencies are installed via `poetry install`.
