# Image Metadata Analyzer

This tool analyzes image metadata (EXIF) from a given root folder, including all subfolders. It provides statistics and generates graphs for:
- Shutter Speed
- Aperture (F-Number)
- ISO
- Focal Length
- Lens Model

## Installation

This project uses [Poetry](https://python-poetry.org/) for dependency management.

1.  Clone the repository.
2.  Install dependencies:

    ```bash
    poetry install
    ```

## Building a Standalone Executable

This project can be packaged into a single, standalone executable for easier distribution and execution on systems without Python or Poetry installed.

1.  **Build the executable**:

    ```bash
    ./build.sh
    ```

    This script uses `pyinstaller` to create a distributable binary in the `dist/` folder.

2.  **Platform-Specific Builds**:
    *   To create a **Linux** executable, run the script on a Linux machine.
    *   To create a **macOS** executable, run the script on a Mac.

    The generated executable will be tailored to the operating system it was built on.

## Usage

Once you have built the executable, you can run it directly from your terminal:

```bash
./dist/image-metadata-analyzer /path/to/your/photos
```

Alternatively, you can run the tool using `poetry run`:

```bash
poetry run python -m image_metadata_analyzer.cli /path/to/your/photos
```

### Options

-   `-o` or `--output`: Specify the folder to save graphs (default: `analysis_results`).
-   `--debug`: Enable detailed debug output for files that could not be processed.
-   `--show-plots`: Automatically open the generated plots after creation.

### Example

```bash
./dist/image-metadata-analyzer ./my_photos --output ./stats --show-plots
```

## Development

### Running Tests

```bash
poetry run pytest
```

### Linting

```bash
poetry run flake8 src tests
```
