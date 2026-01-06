import shutil
import sys
import os
from pathlib import Path

def get_exiftool_path() -> str | None:
    """
    Returns the path to the exiftool executable.

    It checks:
    1. System PATH.
    2. A 'bin' directory adjacent to the executable (bundled).
    3. The PyInstaller temp directory (sys._MEIPASS).
    """
    # Check system PATH first
    if shutil.which("exiftool"):
        return "exiftool"

    # Check for bundled executable
    # If running as a PyInstaller bundle
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        # If running from source, check a 'bin' folder in the package
        base_path = Path(__file__).parent / "bin"

    # Determine executable name based on OS
    exe_name = "exiftool.exe" if sys.platform == "win32" else "exiftool"

    potential_path = base_path / exe_name

    if potential_path.exists():
        return str(potential_path)

    # Also check if it's just 'exiftool' without extension on Linux/Mac
    potential_path_no_ext = base_path / "exiftool"
    if potential_path_no_ext.exists():
        return str(potential_path_no_ext)

    return None
