import time
import numpy as np
import cv2

gray = np.random.randint(0, 256, (4000, 6000), dtype=np.uint8)

# Warmup
cv2.Laplacian(gray, cv2.CV_64F).var()
cv2.Laplacian(gray, cv2.CV_32F).var()

start = time.perf_counter()
for _ in range(10):
    cv2.Laplacian(gray, cv2.CV_64F).var()
time_64 = time.perf_counter() - start

start = time.perf_counter()
for _ in range(10):
    cv2.Laplacian(gray, cv2.CV_32F).var()
time_32 = time.perf_counter() - start

print(f"Time CV_64F: {time_64:.4f}s")
print(f"Time CV_32F: {time_32:.4f}s")
print(f"Speedup: {(time_64 / time_32):.2f}x")
