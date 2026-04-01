import time
import os
from pathlib import Path
from image_metadata_analyzer.controllers import ScanController
from image_metadata_analyzer.models import ScanResult

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

def main():
    files = setup_test_images()

    controller = ScanController()
    tools = {"sharpness": True, "noise": True}

    start = time.time()
    controller._scan_worker(
        files=files,
        grid_size=1,
        tools=tools,
        progress_callback=dummy_progress,
        finished_callback=dummy_finished,
        log_callback=log
    )
    end = time.time()
    print(f"Sequential Scan Time: {end - start:.2f} seconds")

if __name__ == "__main__":
    main()
