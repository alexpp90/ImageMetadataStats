import os
import shutil
import sys
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

import rawpy
from PIL import Image


def resolve_path(path_str: str) -> Path:
    """
    Resolves a path string to a pathlib.Path object.
    Supports resolving smb:// URLs to local mount points on Linux (GVFS) and macOS.

    Args:
        path_str: The input path string (e.g., '/tmp/test' or 'smb://server/share/path')

    Returns:
        Path object pointing to the local file system location.
    """
    # Check if it looks like an SMB URL
    if path_str.startswith("smb://"):
        # Parse the URL
        parsed = urllib.parse.urlparse(path_str)
        server = parsed.hostname
        # Path usually comes as '/share/folder/file'
        # We need to strip the leading slash to split easily, but keep it for logic
        full_path = parsed.path
        if not full_path:
            return Path(path_str)  # Should probably just return as is if malformed

        # Unquote to handle spaces (%20)
        full_path_decoded = urllib.parse.unquote(full_path)

        # Split into share and relative path
        # full_path_decoded starts with /, e.g. /private/Bilder_Alben
        parts = full_path_decoded.strip("/").split("/", 1)
        share_name = parts[0]
        remainder = parts[1] if len(parts) > 1 else ""

        if sys.platform == "linux":
            # GVFS mount point pattern: /run/user/<uid>/gvfs/smb-share:server=<server>,share=<share>/<remainder>
            try:
                uid = os.getuid()
                gvfs_root = Path(f"/run/user/{uid}/gvfs")

                # Construct the directory name.
                # Note: commas in server or share names might need escaping in theory,
                # but standard GVFS behavior for simple names is server=<server>,share=<share>
                # We assume standard behavior.
                mount_dir_name = f"smb-share:server={server},share={share_name}"

                potential_path = gvfs_root / mount_dir_name
                if remainder:
                    potential_path = potential_path / remainder

                return potential_path
            except AttributeError:
                # os.getuid might not be available on Windows, but we are in linux block
                pass

        elif sys.platform == "darwin":
            # macOS mount point pattern: /Volumes/<share>/<remainder>
            # macOS typically mounts using just the share name in /Volumes
            potential_path = Path(f"/Volumes/{share_name}")
            if remainder:
                potential_path = potential_path / remainder
            return potential_path

    # Default: treat as local path
    return Path(path_str)


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
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
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


def aggregate_focal_lengths(
    focal_lengths: List[float], max_buckets: int = 25
) -> List[Tuple[str, int, float]]:
    """
    Aggregates focal lengths into buckets based on percentage difference.

    Args:
        focal_lengths: List of focal length values.
        max_buckets: Maximum number of buckets to create.

    Returns:
        List of tuples (label, count, sort_key).
        - label: String representation (e.g., "50 mm" or "24-28 mm").
        - count: Number of items in this bucket.
        - sort_key: The representative value for sorting (e.g., min value of the bucket).
    """
    if not focal_lengths:
        return []

    # Count exact values first
    counts = Counter(focal_lengths)

    unique_fls = sorted(counts.keys())

    if len(unique_fls) <= max_buckets:
        # No aggregation needed
        # Return exact matches, format as integer if possible
        result = []
        for fl in unique_fls:
            label = f"{int(fl)} mm" if fl.is_integer() else f"{fl:.1f} mm"
            result.append((label, counts[fl], fl))
        return result

    def get_groups(threshold):
        groups = []
        if not unique_fls:
            return groups

        current_group = [unique_fls[0]]

        for fl in unique_fls[1:]:
            # Check if current value is within threshold of the group start
            # logic: (fl - start) / start <= threshold
            if (fl - current_group[0]) / current_group[0] <= threshold:
                current_group.append(fl)
            else:
                groups.append(current_group)
                current_group = [fl]
        groups.append(current_group)
        return groups

    # Binary search for the smallest threshold that yields <= max_buckets
    low = 0.0
    high = 2.0  # Allow up to 200% difference
    best_threshold = high

    # We do a fixed number of iterations for precision
    for _ in range(20):
        mid = (low + high) / 2
        groups = get_groups(mid)
        if len(groups) <= max_buckets:
            best_threshold = mid
            high = mid
        else:
            low = mid

    # Generate final groups with best_threshold
    final_groups = get_groups(best_threshold)

    result = []
    for group in final_groups:
        group_count = sum(counts[fl] for fl in group)
        min_fl = min(group)
        max_fl = max(group)

        def fmt(v):
            return f"{int(v)}" if v.is_integer() else f"{v:.1f}".rstrip("0").rstrip(".")

        if len(group) == 1:
            label = f"{fmt(min_fl)} mm"
        else:
            # If min and max round to same int, show one
            if fmt(min_fl) == fmt(max_fl):
                label = f"{fmt(min_fl)} mm"
            else:
                label = f"{fmt(min_fl)}-{fmt(max_fl)} mm"

        result.append((label, group_count, min_fl))

    return result


def load_image_preview(
    path: Path, max_size: Tuple[int, int] = (150, 150)
) -> Optional[Image.Image]:
    """
    Loads an image for preview, handling both standard formats (via Pillow)
    and RAW formats (via rawpy). Resizes the image to fit within max_size.

    Args:
        path: Path to the image file.
        max_size: Tuple (width, height) for thumbnail size.

    Returns:
        PIL Image object or None if loading fails.
    """
    try:
        ext = path.suffix.lower()
        raw_exts = {
            ".arw",
            ".nef",
            ".cr2",
            ".dng",
            ".orf",
            ".rw2",
            ".raf",
            ".pef",
            ".srw",
        }

        img = None

        # Try rawpy for known RAW extensions
        if ext in raw_exts:
            try:
                with rawpy.imread(str(path)) as raw:
                    # Fast processing for preview: half size, auto bright
                    rgb = raw.postprocess(
                        use_camera_wb=True, bright=1.0, half_size=True
                    )
                    img = Image.fromarray(rgb)
            except Exception:
                # Log or just fall through to Pillow
                pass

        # Fallback to Pillow if not RAW or rawpy failed
        if img is None:
            img = Image.open(path)

        # Resize (thumbnail modifies in-place)
        img.thumbnail(max_size)
        return img

    except Exception:
        # In a real app we might want to log this
        # print(f"Failed to load image preview for {path}: {e}")
        return None
