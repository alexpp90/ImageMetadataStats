import hashlib
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from send2trash import send2trash

from image_metadata_analyzer.reader import SUPPORTED_EXTENSIONS

# Extend supported extensions for duplicates to include basic formats
# not necessarily supported by the metadata analyzer (like GIF/BMP)
IMAGE_EXTENSIONS = SUPPORTED_EXTENSIONS | {".bmp", ".gif"}


def get_file_hash(filepath, block_size=65536):
    """Calculates the SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(block_size), b""):
                sha256_hash.update(block)
        return sha256_hash.hexdigest()
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
    ext_tuple = tuple(IMAGE_EXTENSIONS)

    def _scan(path):
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_file():
                        if entry.name.lower().endswith(ext_tuple):
                            try:
                                s = entry.stat().st_size
                                size_groups[s].append(Path(entry.path))
                            except OSError:
                                pass
                    elif entry.is_dir(follow_symlinks=False):
                        _scan(entry.path)
        except OSError:
            pass

    _scan(root_path)

    # Filter for groups that have more than 1 file
    potential_groups = [paths for paths in size_groups.values() if len(paths) > 1]

    # Count total files to hash
    total_files_to_hash = sum(len(g) for g in potential_groups)
    processed_count = 0

    duplicates = []

    all_files = []
    for group_id, group in enumerate(potential_groups):
        for filepath in group:
            all_files.append((filepath, group_id))

    def _hash_worker(item):
        filepath, group_id = item
        h = get_file_hash(filepath)
        return filepath, group_id, h

    hash_groups_by_id = defaultdict(lambda: defaultdict(list))

    with ThreadPoolExecutor() as executor:
        # executor.map yields results sequentially in the main thread
        for filepath, group_id, h in executor.map(_hash_worker, all_files):
            processed_count += 1
            if callback:
                callback(processed_count, total_files_to_hash)

            if h:
                hash_groups_by_id[group_id][h].append(filepath)

    # Add confirmed duplicates
    for group_id, hash_groups in hash_groups_by_id.items():
        for h, paths in hash_groups.items():
            if len(paths) > 1:
                duplicates.append(
                    {
                        "hash": h,
                        "size": os.path.getsize(
                            paths[0]
                        ),  # Should be same as key of size_groups
                        "files": sorted(paths),  # Sort for consistent display
                    }
                )

    return duplicates


def move_to_trash(filepath):
    """Moves a file to the trash/recycle bin. Raises exception on failure."""
    # send2trash expects a string, not a Path object on some versions/platforms,
    # but modern versions usually handle it. To be safe, cast to str.
    send2trash(str(filepath))
