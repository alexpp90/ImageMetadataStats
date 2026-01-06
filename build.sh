#!/bin/bash
set -e

echo "Cleaning up previous builds..."
rm -rf build dist *.spec

echo "Building standalone executable..."
poetry run pyinstaller --name image-metadata-analyzer --onefile --distpath dist src/image_metadata_analyzer/cli.py
poetry run pyinstaller --name image-metadata-gui --onefile --distpath dist src/image_metadata_analyzer/gui.py

echo "Build complete! The executables are located in the dist/ folder."
