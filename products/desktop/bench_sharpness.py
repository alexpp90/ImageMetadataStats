import time
import numpy as np
import cv2

gray = np.random.randint(0, 256, (4000, 6000), dtype=np.uint8)

# CV_64F benchmark
start = time.time()
for _ in range(10):
    var64 = cv2.Laplacian(gray, cv2.CV_64F).var()
end = time.time()
print(f"CV_64F time: {end - start:.4f}s")

# CV_32F benchmark
start = time.time()
for _ in range(10):
    var32 = cv2.Laplacian(gray, cv2.CV_32F).var()
end = time.time()
print(f"CV_32F time: {end - start:.4f}s")
