import time
import os
import shutil
from pathlib import Path
from image_metadata_analyzer.duplicates import find_duplicates

def setup_test_files(base_dir, num_files, size_bytes):
    base_path = Path(base_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    # Create num_files with the same size but slightly different content
    for i in range(num_files):
        content = os.urandom(size_bytes)
        file_path = base_path / f"test_file_{i}.jpg"
        with open(file_path, 'wb') as f:
            f.write(content)

    # Create duplicates for some of the files
    for i in range(num_files // 2):
        src_path = base_path / f"test_file_{i}.jpg"
        dst_path = base_path / f"test_file_{i}_dup.jpg"
        shutil.copy(src_path, dst_path)

if __name__ == "__main__":
    test_dir = "benchmarks/test_data_duplicates"

    # Clean up first
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

    print("Setting up test files...")
    # Setup 100 files of 10MB each, 50 of them duplicated
    setup_test_files(test_dir, 100, 10 * 1024 * 1024)
    print("Test files created.")

    start_time = time.time()
    results = find_duplicates(test_dir)
    end_time = time.time()

    print(f"Time taken to find duplicates: {end_time - start_time:.4f} seconds")
    print(f"Found {len(results)} groups of duplicates.")

    # Clean up
    shutil.rmtree(test_dir)
