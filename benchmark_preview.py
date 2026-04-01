import time
import os
import shutil
from pathlib import Path
from PIL import Image

def setup_benchmark_images(folder, num_images=100):
    os.makedirs(folder, exist_ok=True)
    for i in range(num_images):
        img = Image.new('RGB', (1000, 1000), color=(i%255, i%255, i%255))
        img.save(os.path.join(folder, f"img_{i}.jpg"))

def benchmark():
    from image_metadata_analyzer.utils import load_image_preview
    import concurrent.futures

    test_dir = "test_benchmark_images"
    setup_benchmark_images(test_dir, 200)

    # Create fake results list matching duplicates format
    results = [{"files": [Path(os.path.join(test_dir, f"img_{i}.jpg"))]} for i in range(200)]

    # Sequential
    start = time.time()
    thumbnails_seq = []
    for group in results:
        thumb = None
        if group['files']:
            try:
                thumb = load_image_preview(group['files'][0], max_size=(150, 150))
            except Exception:
                pass
        thumbnails_seq.append(thumb)
    seq_time = time.time() - start

    # Parallel
    start = time.time()
    def _load_thumb(group):
        if group["files"]:
            try:
                return load_image_preview(group["files"][0], max_size=(150, 150))
            except Exception:
                pass
        return None

    with concurrent.futures.ThreadPoolExecutor() as executor:
        thumbnails_par = list(executor.map(_load_thumb, results))
    par_time = time.time() - start

    print(f"Sequential Time: {seq_time:.3f} s")
    print(f"Parallel Time:   {par_time:.3f} s")
    speedup = seq_time / par_time
    print(f"Speedup:         {speedup:.2f}x")

    shutil.rmtree(test_dir)

if __name__ == "__main__":
    benchmark()
