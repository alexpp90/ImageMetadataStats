## 2024-08-14 - OpenCV Laplacian Precision
**Learning:** Using `cv2.CV_64F` for intermediate operations like `cv2.Laplacian` creates a measurable performance bottleneck. Defaulting to `cv2.CV_32F` yields significant speedups (40-60%) when extreme double precision is not strictly required.
**Action:** Default to `cv2.CV_32F` for OpenCV filters and operations unless extreme precision is mathematically required by the specific algorithm.
