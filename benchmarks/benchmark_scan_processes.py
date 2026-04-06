import time
import os
from pathlib import Path
from image_metadata_analyzer.controllers import ScanController
from image_metadata_analyzer.models import ScanResult
from concurrent.futures import ProcessPoolExecutor

def dummy_progress(res, i, total):
    pass

def dummy_finished():
    pass

def log(msg):
    pass

def setup_test_images():
    import cv2
    import numpy as np

    test_dir = Path("benchmarks/test_images")
    test_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for i in range(20):
        filepath = test_dir / f"test_{i}.jpg"
        if not filepath.exists():
            img = np.random.randint(0, 256, (1000, 1000, 3), dtype=np.uint8)
            cv2.imwrite(str(filepath), img)
        files.append(filepath)
    return files

def process_file(f, grid_size, tools):
    from image_metadata_analyzer.sharpness import calculate_sharpness, calculate_noise
    from image_metadata_analyzer.reader import get_exif_data

    score = "N/A"
    if tools.get("sharpness", False):
        score = calculate_sharpness(f, grid_size=grid_size)
    noise_score = "N/A"
    if tools.get("noise", False):
        noise_score = calculate_noise(f)
    exif = get_exif_data(f) or {}
    return ScanResult(path=f, score=score, noise_score=noise_score, exif=exif)


def main():
    files = setup_test_images()

    controller = ScanController()
    tools = {"sharpness": True, "noise": True}

    start = time.time()

    with ProcessPoolExecutor() as executor:
        futures = []
        for f in files:
            futures.append(executor.submit(process_file, f, 1, tools))

        for i, future in enumerate(futures):
            res = future.result()
            dummy_progress(res, i+1, len(files))

    end = time.time()
    print(f"Process Scan Time: {end - start:.2f} seconds")

if __name__ == "__main__":
    main()
