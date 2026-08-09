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
EXIFTOOL_VERSION = "13.59"
SF_BASE_URL = "https://downloads.sourceforge.net/project/exiftool"

PROJECT_ROOT = Path(__file__).parent.parent
BIN_DIR = PROJECT_ROOT / "src" / "photo_selector_toolbox" / "bin"

# Branding and licence texts are shared with the README and the Android
# products, so they stay at the repository root rather than inside
# products/desktop/. Resolve them from the script's own location: CI runs this
# with cwd=products/desktop, where "assets/logo.png" does not exist.
REPO_ROOT = PROJECT_ROOT.parent.parent
ASSETS_DIR = REPO_ROOT / "assets"

# Roots of the PyObjC import chain used by the Apple Vision aesthetics engine.
# `tools/aesthetic.py` imports `Vision` and `Foundation` inside function bodies
# guarded by try/except, and `Vision.__init__` pulls Quartz/CoreML/objc and its
# own `_Vision` extension module from inside a `_setup()` function as well.
# PyInstaller ships no hook for PyObjC, so if the graph walker ever stops
# following those deferred imports the frozen app raises ImportError,
# `apple_vision_available()` returns False, and aesthetic scoring silently
# degrades to the ~200x slower Ollama engine — a defect that exists only in the
# shipped bundle and never in development. Naming the two roots as hidden
# imports removes that dependence on static analysis.
#
# Measured (PyInstaller 6.19.0, PyObjC 12.2.1, Python 3.14.6, arm64), onedir
# probe importing the real `AppleVisionAestheticEngine`: 49400 KiB without any
# flags and 49400 KiB with these two — the guarantee is free, because analysis
# happens to find the same modules today. `--collect-all` on the same packages
# costs +2228 KiB, over half of it PyObjC's `.dSYM` debug bundles, so it is
# deliberately not used.
MACOS_PYOBJC_HIDDEN_IMPORTS = ["Vision", "Foundation"]


def pyobjc_hidden_import_args(target):
    """PyInstaller flags that pin the PyObjC Vision bridge into the bundle.

    macOS only, and GUI only: the CLI never imports `tools/`, so the CLI binary
    would carry bindings it can never reach.
    """
    if platform.system() != "Darwin" or target != "gui":
        return []
    args = []
    for module in MACOS_PYOBJC_HIDDEN_IMPORTS:
        args.extend(["--hidden-import", module])
    return args

def download_file(url, dest_path):
    print(f"Downloading {url}...")
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    except Exception as e:
        print(f"Error downloading with urllib: {e}")
        try:
            subprocess.run(["curl", "-L", url, "-o", str(dest_path)], check=True)
        except Exception as e2:
            print(f"Download failed with curl too: {e2}")
            sys.exit(1)

def setup_exiftool():
    # Clean bin dir first
    if BIN_DIR.exists():
        shutil.rmtree(BIN_DIR)
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    system = platform.system()

    if system == "Windows":
        filename = f"exiftool-{EXIFTOOL_VERSION}_64.zip"
        url = f"{SF_BASE_URL}/{filename}"
        dest = BIN_DIR / filename

        download_file(url, dest)

        print("Extracting...")
        with zipfile.ZipFile(dest, 'r') as zip_ref:
            # Secure extraction to prevent Zip Slip
            for member in zip_ref.infolist():
                target_path = (BIN_DIR / member.filename).resolve()
                if os.path.commonpath([BIN_DIR.resolve(), target_path]) != str(BIN_DIR.resolve()):
                    print(f"Warning: Skipping {member.filename} (Zip Slip vulnerability detected)")
                    continue
                zip_ref.extract(member, BIN_DIR)

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
        url = f"{SF_BASE_URL}/{filename}"
        dest = BIN_DIR / filename

        download_file(url, dest)
        print("Extracting...")
        # Use simple extraction
        with tarfile.open(dest, "r:gz") as tar:
            if hasattr(tarfile, 'data_filter'):
                tar.extractall(BIN_DIR, filter='data')
            else:
                # Secure extraction to prevent Tar Slip on older Python versions
                for member in tar.getmembers():
                    target_path = (BIN_DIR / member.name).resolve()
                    if os.path.commonpath([BIN_DIR.resolve(), target_path]) != str(BIN_DIR.resolve()):
                        print(f"Warning: Skipping {member.name} (Tar Slip vulnerability detected)")
                        continue
                    tar.extract(member, BIN_DIR)

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
    src_data = "src/photo_selector_toolbox/bin"
    dst_data = "."
    add_data_arg = f"{src_data}{sep}{dst_data}"

    name_map = {
        "analyzer": "photo-selector-toolbox",
        "gui": "Photo Selector Toolbox"
    }
    app_name = name_map.get(target, f"photo-selector-{target}")

    cmd = [
        "poetry", "run", "pyinstaller",
        "--name", app_name,
        "--paths", "src",
        "--distpath", "dist",
        "--add-data", add_data_arg,
        "--clean",
        "--noconfirm",
    ]

    # Use onedir on macOS for faster startup and to avoid security issues
    # Use onefile on other platforms for convenience
    if platform.system() == "Darwin":
        cmd.append("--onedir")
    else:
        cmd.append("--onefile")

    cmd.extend(pyobjc_hidden_import_args(target))

    if target == "gui":
        # Add icon file to data
        icon_src = str(ASSETS_DIR / "logo.png")
        icon_dst = "."
        cmd.extend(["--add-data", f"{icon_src}{sep}{icon_dst}"])

        # Add splash screen (not supported on macOS)
        if platform.system() != "Darwin":
            cmd.extend(["--splash", str(ASSETS_DIR / "logo.png")])

        # Set executable icon
        if platform.system() == "Windows":
            cmd.extend(["--icon", str(ASSETS_DIR / "logo.ico")])
        elif platform.system() == "Darwin":
            cmd.extend(["--icon", str(ASSETS_DIR / "logo.icns")])
        else:
            # Linux .desktop files handle icons, but we can set window icon in code.
            pass

        cmd.extend([
            "--windowed",
            "src/photo_selector_toolbox/gui/app.py"
        ])
    else:
        cmd.append("src/photo_selector_toolbox/cli.py")

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # Add ad-hoc signing for macOS .app bundles
    if platform.system() == "Darwin" and target == "gui":
        app_path = Path("dist") / "Photo Selector Toolbox.app"
        if app_path.exists():
            print(f"Signing {app_path} with ad-hoc signature...")
            subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app_path)], check=True)

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
        shutil.copy(REPO_ROOT / "LICENSE", dist_dir / "LICENSE")
        shutil.copy(REPO_ROOT / "THIRDPARTY_NOTICES.txt", dist_dir / "THIRDPARTY_NOTICES.txt")
        print("Licenses copied.")
    else:
        print("Warning: dist/ directory not found. Licenses were not copied.")

if __name__ == "__main__":
    main()
