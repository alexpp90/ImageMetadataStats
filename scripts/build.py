import os
import sys
import shutil
import tarfile
import zipfile
import urllib.request
import platform
import subprocess
from pathlib import Path
from generate_notices import generate_notices

# Constants
EXIFTOOL_VERSION = "13.45"
SF_BASE_URL = "https://sourceforge.net/projects/exiftool/files"

PROJECT_ROOT = Path(__file__).parent.parent
BIN_DIR = PROJECT_ROOT / "src" / "image_metadata_analyzer" / "bin"

def download_file(url, dest_path):
    print(f"Downloading {url}...")
    try:
        urllib.request.urlretrieve(url, dest_path)
    except Exception as e:
        print(f"Error downloading with urllib: {e}")
        try:
             subprocess.run(["wget", url, "-O", str(dest_path)], check=True)
        except Exception as e2:
             print(f"Download failed with wget too: {e2}")
             sys.exit(1)

def setup_exiftool():
    # Clean bin dir first
    if BIN_DIR.exists():
        shutil.rmtree(BIN_DIR)
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    system = platform.system()

    if system == "Windows":
        filename = f"exiftool-{EXIFTOOL_VERSION}_64.zip"
        url = f"{SF_BASE_URL}/{filename}/download"
        dest = BIN_DIR / filename

        download_file(url, dest)

        print("Extracting...")
        with zipfile.ZipFile(dest, 'r') as zip_ref:
            zip_ref.extractall(BIN_DIR)

        found_exe = False
        for root, dirs, files in os.walk(BIN_DIR):
            for file in files:
                if file.startswith("exiftool") and file.endswith(".exe"):
                    source = Path(root) / file
                    target = BIN_DIR / "exiftool.exe"
                    shutil.move(str(source), str(target))
                    found_exe = True
                    break
            if found_exe:
                break

        if not found_exe:
            print("Error: Could not find exiftool.exe in the downloaded zip.")
            sys.exit(1)

        dest.unlink()
        for p in BIN_DIR.iterdir():
            if p.is_dir():
                shutil.rmtree(p)

    elif system in ["Linux", "Darwin"]:
        filename = f"Image-ExifTool-{EXIFTOOL_VERSION}.tar.gz"
        url = f"{SF_BASE_URL}/{filename}/download"
        dest = BIN_DIR / filename

        download_file(url, dest)
        print("Extracting...")
        # Use simple extraction
        with tarfile.open(dest, "r:gz") as tar:
            tar.extractall(BIN_DIR)

        # Check what we have
        extracted_dirs = [p for p in BIN_DIR.iterdir() if p.is_dir()]
        print(f"Extracted directories: {extracted_dirs}")

        if extracted_dirs:
            # We expect one folder like Image-ExifTool-13.45
            extracted_folder = extracted_dirs[0]

            # Move contents to BIN_DIR
            # 'exiftool' script
            src_script = extracted_folder / "exiftool"
            if src_script.exists():
                shutil.move(str(src_script), str(BIN_DIR / "exiftool"))
            else:
                print("Error: 'exiftool' script not found in extracted folder.")

            # 'lib' folder
            src_lib = extracted_folder / "lib"
            if src_lib.exists():
                shutil.move(str(src_lib), str(BIN_DIR / "lib"))
            else:
                print("Error: 'lib' folder not found in extracted folder.")

            # Cleanup extracted folder
            shutil.rmtree(extracted_folder)

        dest.unlink()

        # Make executable
        script_path = BIN_DIR / "exiftool"
        if script_path.exists():
            script_path.chmod(0o755)
        else:
            print("Error: exiftool script not found after setup.")
            sys.exit(1)

    else:
        print(f"Unsupported platform: {system}")
        sys.exit(1)

    print(f"Exiftool setup complete in {BIN_DIR}")

def run_pyinstaller(target):
    sep = ";" if platform.system() == "Windows" else ":"
    src_data = "src/image_metadata_analyzer/bin"
    dst_data = "."
    add_data_arg = f"{src_data}{sep}{dst_data}"

    cmd = [
        "poetry", "run", "pyinstaller",
        "--name", f"image-metadata-{target}",
        "--onefile",
        "--distpath", "dist",
        "--add-data", add_data_arg,
        "--clean",
        "--noconfirm",
    ]

    if target == "gui":
        # Add icon file to data
        icon_src = "assets/logo.png"
        icon_dst = "."
        cmd.extend(["--add-data", f"{icon_src}{sep}{icon_dst}"])

        # Set executable icon
        if platform.system() == "Windows":
             cmd.extend(["--icon", "assets/logo.ico"])
        elif platform.system() == "Darwin":
             # If we had .icns, we would use it. PyInstaller often accepts .png on some platforms or ignores it.
             # For now, let's try using the ico or png if supported, but typically .icns is best for Mac.
             # Given we only generated .ico and .png:
             # cmd.extend(["--icon", "assets/logo.png"]) # Warning: might not work as expected on Mac without .icns
             pass
        else:
             # Linux .desktop files handle icons, but we can set window icon in code.
             pass

        cmd.extend([
            "--windowed",
            "src/image_metadata_analyzer/gui.py"
        ])
    else:
        cmd.append("src/image_metadata_analyzer/cli.py")

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def generate_icons_if_possible():
    # Only try generating icons on Linux, or if explicit env var is set.
    # On Windows/Mac, installing Cairo is tricky, so we rely on pre-generated assets.
    if platform.system() != "Linux" and os.environ.get("FORCE_ICON_GEN") != "1":
        print("Skipping icon generation on non-Linux platform (using existing assets).")
        return True

    # Try importing and running generation script
    # It might fail if dependencies (cairo) are missing
    try:
        sys.path.append(str(Path(__file__).parent))
        from generate_icons import generate_icons
        print("Generating icons...")
        return generate_icons()
    except (ImportError, OSError) as e:
        print(f"Warning: Could not run icon generation script: {e}")
        print("Build will proceed using existing assets if available.")
        return False
    except Exception as e:
        print(f"Warning: Unexpected error during icon generation: {e}")
        return False

def main():
    generate_icons_if_possible()

    setup_exiftool()

    print("Building CLI...")
    run_pyinstaller("analyzer")

    print("Building GUI...")
    run_pyinstaller("gui")

    # Generate fresh notices
    try:
        generate_notices()
    except Exception as e:
        print(f"Warning: Failed to regenerate notices: {e}")

    print("Copying licenses to dist/...")
    dist_dir = Path("dist")
    if dist_dir.exists():
        shutil.copy("LICENSE", dist_dir / "LICENSE")
        shutil.copy("THIRDPARTY_NOTICES.txt", dist_dir / "THIRDPARTY_NOTICES.txt")
        print("Licenses copied.")
    else:
        print("Warning: dist/ directory not found. Licenses were not copied.")

if __name__ == "__main__":
    main()
