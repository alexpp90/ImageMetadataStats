import cv2
import numpy as np
import time

def run():
    img = np.random.randint(0, 256, (4000, 4000), dtype=np.uint8)

    start = time.time()
    for _ in range(10):
        lap_64 = cv2.Laplacian(img, cv2.CV_64F)
        var_64 = lap_64.var()
    end = time.time()
    print(f"CV_64F Time: {end - start:.4f}s")

    start = time.time()
    for _ in range(10):
        lap_32 = cv2.Laplacian(img, cv2.CV_32F)
        var_32 = lap_32.var()
    end = time.time()
    print(f"CV_32F Time: {end - start:.4f}s")

run()
