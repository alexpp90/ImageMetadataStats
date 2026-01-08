import sys
from pathlib import Path

import cairosvg
from PIL import Image

PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
SVG_FILE = ASSETS_DIR / "logo.svg"
PNG_FILE = ASSETS_DIR / "logo.png"
ICO_FILE = ASSETS_DIR / "logo.ico"


def generate_icons():
    if not ASSETS_DIR.exists():
        print(f"Error: Assets directory not found at {ASSETS_DIR}")
        return False

    if not SVG_FILE.exists():
        print(f"Error: SVG file not found at {SVG_FILE}")
        return False

    print(f"Converting {SVG_FILE} to {PNG_FILE}...")
    try:
        cairosvg.svg2png(url=str(SVG_FILE), write_to=str(PNG_FILE), output_width=256, output_height=256)
    except Exception as e:
        print(f"Error converting SVG to PNG: {e}")
        return False

    if not PNG_FILE.exists():
        print("Error: PNG file was not created.")
        return False

    print(f"Converting {PNG_FILE} to {ICO_FILE}...")
    try:
        img = Image.open(PNG_FILE)
        # Create ICO with multiple sizes
        img.save(ICO_FILE, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    except Exception as e:
        print(f"Error converting PNG to ICO: {e}")
        return False

    print("Icon generation complete.")
    return True


if __name__ == "__main__":
    success = generate_icons()
    sys.exit(0 if success else 1)
