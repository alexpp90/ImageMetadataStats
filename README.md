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

## Usage

You can run the tool using `poetry run`:

```bash
poetry run python -m image_metadata_analyzer.cli /path/to/your/photos
```

Or if you have installed the package, you can invoke the module directly.

### Options

-   `-o` or `--output`: Specify the folder to save graphs (default: `analysis_results`).
-   `--debug`: Enable detailed debug output for files that could not be processed.
-   `--show-plots`: Automatically open the generated plots after creation.

### Example

```bash
poetry run python -m image_metadata_analyzer.cli ./my_photos --output ./stats --show-plots
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
