## 2024-05-24 - OpenCV 64-bit float bottleneck
**Learning:** Using `cv2.CV_64F` for intermediate operations like `cv2.Laplacian` creates a measurable performance bottleneck in Python OpenCV applications, as seen in the sharpness heuristics.
**Action:** Default to `cv2.CV_32F` to gain significant speedups (40-60%) when extreme double precision is not strictly required. Remember to cast the results (like `.var()` or `.median()`) from `numpy.float32` back to Python `float()` to avoid downstream serialization or typing errors.
