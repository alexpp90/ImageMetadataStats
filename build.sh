#!/bin/bash
set -e

# Function to check for a python module
check_module() {
    local module=$1
    echo "Checking for $module..."

    # Capture output and exit code
    if ! output=$(poetry run python -c "import $module" 2>&1); then
        echo "Error: '$module' module check failed."
        echo "========================================"
        echo "Import Error Details:"
        echo "$output"
        echo "========================================"

        echo "Diagnosing installation status..."
        if poetry run pip show "$module" >/dev/null 2>&1; then
             echo "Diagnostic: '$module' seems to be installed in the poetry environment, but the import failed."
             echo "This usually indicates a runtime issue, such as missing system dependencies (e.g. C++ libraries for pandas)."
        else
             echo "Diagnostic: '$module' is NOT found in 'pip list'."
             echo "Please ensure you have run 'poetry install' successfully."
        fi

        return 1
    fi
}

# Check for Tkinter
if ! check_module "tkinter"; then
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

# Check for Pandas (and other core deps just in case)
if ! check_module "pandas"; then
    echo "Build failed due to missing or broken dependencies."
    exit 1
fi

echo "Cleaning up previous builds..."
rm -rf build dist *.spec

echo "Building standalone executable..."

# Build CLI
# We use --collect-all pandas to strictly ensure everything is bundled.
poetry run pyinstaller --name image-metadata-analyzer \
    --onefile \
    --distpath dist \
    --paths src \
    --collect-all pandas \
    src/image_metadata_analyzer/cli.py

# Build GUI
# We add --hidden-import and --paths to be extra safe for the GUI build
poetry run pyinstaller --name image-metadata-gui \
    --onefile \
    --distpath dist \
    --paths src \
    --hidden-import=pandas \
    --collect-all pandas \
    src/image_metadata_analyzer/gui.py

echo "Build complete! The executables are located in the dist/ folder."
