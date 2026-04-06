import time
import os
import shutil
from pathlib import Path
from image_metadata_analyzer.duplicates import find_duplicates

def setup_test_data(root, num_groups, files_per_group):
    root_path = Path(root)
    if root_path.exists():
        shutil.rmtree(root_path)
    root_path.mkdir(parents=True)

    for i in range(num_groups):
        content = f"content_{i}".encode('utf-8')
        for j in range(files_per_group):
            file_path = root_path / f"file_{i}_{j}.jpg"
            file_path.write_bytes(content)

if __name__ == "__main__":
    test_dir = "test_duplicates_bench"
    setup_test_data(test_dir, 500, 5)

    start_time = time.time()
    duplicates = find_duplicates(test_dir)
    end_time = time.time()

    print(f"Found {len(duplicates)} duplicate groups")
    print(f"Execution time: {end_time - start_time:.4f} seconds")

    shutil.rmtree(test_dir)
