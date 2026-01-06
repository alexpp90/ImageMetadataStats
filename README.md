# Image Metadata Analyzer

This tool analyzes image metadata (EXIF) from a given root folder, including all subfolders. It provides statistics and generates graphs for:
- Shutter Speed
- Aperture (F-Number)
- ISO
- Focal Length
- Lens Model

## Installation & Usage

### Option 1: Standalone Executable (Recommended)

Go to the [Actions](https://github.com/OWNER/REPO/actions) tab (or Releases if configured) and download the artifact for your operating system (Linux or macOS).

1.  Extract the downloaded zip file.
2.  Run the executable:
    *   **GUI**: Double-click `image-metadata-gui`.
    *   **CLI**: Run `./image-metadata-analyzer` from the terminal.

The standalone executable comes with `exiftool` bundled, so you don't need to install anything else.

### Option 2: Run from Source

1.  Clone the repository.
2.  Install dependencies using [Poetry](https://python-poetry.org/):

    ```bash
    poetry install
    ```

3.  **System Requirements**:
    *   **Python 3.10+**
    *   **Tkinter**: Required for the GUI.
        *   Linux: `sudo apt-get install python3-tk`
        *   macOS: `brew install python-tk`
    *   **ExifTool**: Recommended for RAW file support. Install it via your package manager or download from [exiftool.org](https://exiftool.org). The app will automatically find it if it's in your PATH.

4.  Run the application:

    ```bash
    # GUI
    poetry run image-metadata-gui

    # CLI
    poetry run image-metadata-analyzer /path/to/photos
    ```

## Features

*   **No external dependencies** required for the standalone build.
*   **Cross-platform**: Runs on Linux and macOS.
*   **RAW Support**: Handles common RAW formats (.ARW, .NEF, .CR2, etc.) using `exiftool` (bundled in the executable).
*   **Fast Analysis**: Uses optimized metadata extraction.

## Development

### Building the Executable Locally

You can use the provided Python script to build the standalone executable. This script automatically downloads the correct `exiftool` binary for your platform and bundles it.

```bash
poetry run python scripts/build.py
```

The executables will be placed in the `dist/` folder.

### Running Tests

```bash
poetry run pytest
```
