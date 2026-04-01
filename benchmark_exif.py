import time
from pathlib import Path
from image_metadata_analyzer.reader import get_exif_data
import concurrent.futures

def create_dummy_images(num_images=100):
    from PIL import Image
    import os

    test_dir = Path("benchmark_images")
    test_dir.mkdir(exist_ok=True)

    for i in range(num_images):
        img = Image.new('RGB', (100, 100), color = 'red')
        # Add some dummy EXIF
        img.save(test_dir / f"test_image_{i}.jpg")

    return list(test_dir.glob("*.jpg"))

def sequential_scan(image_files):
    all_metadata = []
    for f in image_files:
        data = get_exif_data(f)
        if data:
            all_metadata.append(data)
    return all_metadata

def parallel_scan(image_files):
    all_metadata = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for data in executor.map(get_exif_data, image_files):
            if data:
                all_metadata.append(data)
    return all_metadata

if __name__ == "__main__":
    print("Creating test images...")
    image_files = create_dummy_images(200)

    print("Running sequential scan...")
    start_time = time.time()
    seq_data = sequential_scan(image_files)
    seq_time = time.time() - start_time
    print(f"Sequential time: {seq_time:.2f} seconds")

    print("Running parallel scan...")
    start_time = time.time()
    par_data = parallel_scan(image_files)
    par_time = time.time() - start_time
    print(f"Parallel time: {par_time:.2f} seconds")

    print(f"Speedup: {seq_time/par_time:.2f}x")

    # Cleanup
    import shutil
    shutil.rmtree("benchmark_images")
