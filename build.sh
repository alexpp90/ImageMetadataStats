#!/bin/bash
set -e

echo "Checking for Tkinter availability..."
if ! poetry run python -c "import tkinter" 2>/dev/null; then
    echo "Error: 'tkinter' module not found."
    echo "It is required for building the GUI."
    echo "On Linux, you may need to install it via your package manager."
    echo "Example: sudo apt-get install python3-tk"

    if [[ "$(uname)" == "Darwin" ]]; then
        echo ""
        echo "On macOS, you may need to install python-tk:"
        echo "Example: brew install python-tk"
    fi
    exit 1
fi

echo "Cleaning up previous builds..."
rm -rf build dist *.spec

echo "Building standalone executable..."
# Add --collect-all pandas to ensure all dependencies and data files for pandas are included
# This fixes "ModuleNotFoundError: No module named 'pandas'" issues in some environments.
poetry run pyinstaller --name image-metadata-analyzer --onefile --distpath dist --collect-all pandas src/image_metadata_analyzer/cli.py
poetry run pyinstaller --name image-metadata-gui --onefile --distpath dist --collect-all pandas src/image_metadata_analyzer/gui.py

echo "Build complete! The executables are located in the dist/ folder."
