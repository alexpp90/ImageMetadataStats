import timeit
import tempfile
from pathlib import Path
from image_metadata_analyzer.sharpness import find_related_files

def setup_test_env(num_files=10000):
    temp_dir = tempfile.TemporaryDirectory()
    base_path = Path(temp_dir.name)

    # Create target files
    target_stem = "TARGET_FILE_[]*"
    (base_path / f"{target_stem}.ARW").touch()
    (base_path / f"{target_stem}.JPG").touch()
    (base_path / f"{target_stem}.xmp").touch()

    # Create noise files
    for i in range(num_files):
        (base_path / f"noise_{i}.jpg").touch()

    return temp_dir, base_path, target_stem

def run_benchmark():
    num_files = 10000
    print(f"Setting up directory with {num_files} files...")
    temp_dir, base_path, target_stem = setup_test_env(num_files)

    target_file = base_path / f"{target_stem}.ARW"

    print("Running benchmark...")

    # Run the function a few times
    iterations = 50
    total_time = timeit.timeit(lambda: find_related_files(target_file), number=iterations)

    avg_time = (total_time / iterations) * 1000 # in ms
    print(f"Average time per call: {avg_time:.2f} ms")

    temp_dir.cleanup()
    return avg_time

if __name__ == "__main__":
    run_benchmark()
