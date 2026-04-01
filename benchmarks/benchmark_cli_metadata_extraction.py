import time
import concurrent.futures
from pathlib import Path
from typing import List, Optional

# Mocking get_exif_data to simulate I/O delay
def mock_get_exif_data(path: Path, debug: bool = False) -> Optional[dict]:
    time.sleep(0.05)  # Simulate 50ms I/O delay
    return {"path": path, "metadata": "fake"}

def sequential_extraction(image_files: List[Path], debug: bool = False):
    results = []
    for f in image_files:
        data = mock_get_exif_data(f, debug=debug)
        if data:
            results.append(data)
    return results

def parallel_extraction(image_files: List[Path], debug: bool = False):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Use map to preserve order if needed, or as_completed for speed
        # Here we use map to match the logic of list comprehension
        results = list(executor.map(lambda f: mock_get_exif_data(f, debug=debug), image_files))
    return [r for r in results if r]

def run_benchmark():
    num_images = 100
    image_files = [Path(f"image_{i}.jpg") for i in range(num_images)]

    print(f"Benchmarking extraction for {num_images} images (simulated 50ms delay per image)...")

    # Sequential
    start_time = time.time()
    seq_results = sequential_extraction(image_files)
    seq_duration = time.time() - start_time
    print(f"Sequential Duration: {seq_duration:.4f} seconds")

    # Parallel
    start_time = time.time()
    par_results = parallel_extraction(image_files)
    par_duration = time.time() - start_time
    print(f"Parallel Duration: {par_duration:.4f} seconds")

    improvement = (seq_duration - par_duration) / seq_duration * 100
    speedup = seq_duration / par_duration
    print(f"Improvement: {improvement:.2f}%")
    print(f"Speedup: {speedup:.2f}x")

    assert len(seq_results) == len(par_results) == num_images

if __name__ == "__main__":
    run_benchmark()
