import sys
from unittest.mock import MagicMock

# Mock dependencies
sys.modules['send2trash'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['PIL.ExifTags'] = MagicMock()
sys.modules['exifread'] = MagicMock()
sys.modules['exiftool'] = MagicMock()
sys.modules['rawpy'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['cv2'] = MagicMock()

import time
import os
import shutil
from pathlib import Path
# We need to make sure src is in sys.path
sys.path.insert(0, os.path.abspath("src"))
from image_metadata_analyzer.duplicates import find_duplicates

def setup_test_files(base_dir, num_groups, files_per_group, size_bytes):
    base_path = Path(base_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    for g in range(num_groups):
        content = os.urandom(size_bytes)
        for f in range(files_per_group):
            file_path = base_path / f"group_{g}_file_{f}.jpg"
            with open(file_path, 'wb') as fout:
                fout.write(content)

if __name__ == "__main__":
    test_dir = "benchmarks/test_data_duplicates_perf"

    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

    # Significantly more groups to emphasize overhead
    num_groups = 10000
    files_per_group = 2
    file_size = 64 # Very small files to minimize hashing time

    print(f"Setting up {num_groups * files_per_group} test files...")
    setup_test_files(test_dir, num_groups, files_per_group, file_size)
    print("Test files created.")

    # Warm up
    find_duplicates(test_dir)

    times = []
    for i in range(5):
        start_time = time.perf_counter()
        results = find_duplicates(test_dir)
        end_time = time.perf_counter()
        times.append(end_time - start_time)
        print(f"Run {i+1}: {times[-1]:.4f} seconds")

    avg_time = sum(times) / len(times)
    print(f"Average time taken: {avg_time:.4f} seconds")
    print(f"Found {len(results)} groups of duplicates.")

    # Clean up
    shutil.rmtree(test_dir)
