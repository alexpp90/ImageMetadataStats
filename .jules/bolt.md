## 2025-01-20 - OpenCV precision bottleneck

**Learning:** Using `cv2.CV_64F` for intermediate operations like `cv2.Laplacian` creates a measurable performance bottleneck in Python OpenCV applications.
**Action:** Default to `cv2.CV_32F` to gain significant speedups (40-60%) when extreme double precision is not strictly required.
