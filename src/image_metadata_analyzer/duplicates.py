import hashlib
import os
from collections import defaultdict
from pathlib import Path
from send2trash import send2trash

from image_metadata_analyzer.reader import SUPPORTED_EXTENSIONS

# Extend supported extensions for duplicates to include basic formats
# not necessarily supported by the metadata analyzer (like GIF/BMP)
IMAGE_EXTENSIONS = SUPPORTED_EXTENSIONS | {'.bmp', '.gif'}


def get_file_hash(filepath, block_size=65536):
    """Calculates the MD5 hash of a file."""
    md5 = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                md5.update(block)
        return md5.hexdigest()
    except OSError:
        return None


def find_duplicates(root_folder, callback=None):
    """
    Scans a folder for duplicate image files based on size and content hash.

    Args:
        root_folder (str|Path): The directory to scan.
        callback (callable): Optional callback for progress updates.
                             Signature: callback(processed_count, total_count)

    Returns:
        list[dict]: A list of duplicate groups. Each group is a dict:
                    {'hash': str, 'size': int, 'files': [Path, Path, ...]}
    """
    root_path = Path(root_folder)
    if not root_path.exists():
        return []

    # Step 1: Group by size
    size_groups = defaultdict(list)

    # We'll first collect all candidate files to count them for progress,
    # but strictly speaking we only iterate `os.walk` once.
    # To support accurate progress for HASHING (the slow part),
    # we first gather potential candidates.

    # Using a list to store all image paths first is fast enough for typical library sizes.
    # But checking size is also stat().

    # Initial scan
    for root, _, files in os.walk(root_path):
        for name in files:
            path = Path(root) / name
            if path.suffix.lower() in IMAGE_EXTENSIONS:
                try:
                    s = path.stat().st_size
                    size_groups[s].append(path)
                except OSError:
                    pass

    # Filter for groups that have more than 1 file
    potential_groups = [paths for paths in size_groups.values() if len(paths) > 1]

    # Count total files to hash
    total_files_to_hash = sum(len(g) for g in potential_groups)
    processed_count = 0

    duplicates = []

    for group in potential_groups:
        # Group by hash within this size group
        hash_groups = defaultdict(list)

        for filepath in group:
            h = get_file_hash(filepath)
            processed_count += 1
            if callback:
                callback(processed_count, total_files_to_hash)

            if h:
                hash_groups[h].append(filepath)

        # Add confirmed duplicates
        for h, paths in hash_groups.items():
            if len(paths) > 1:
                duplicates.append({
                    'hash': h,
                    'size': os.path.getsize(paths[0]),  # Should be same as key of size_groups
                    'files': sorted(paths)  # Sort for consistent display
                })

    return duplicates


def move_to_trash(filepath):
    """Moves a file to the trash/recycle bin. Raises exception on failure."""
    # send2trash expects a string, not a Path object on some versions/platforms,
    # but modern versions usually handle it. To be safe, cast to str.
    send2trash(str(filepath))
