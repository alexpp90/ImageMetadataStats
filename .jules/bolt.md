## 2025-05-24 - OpenCV Laplacian Precision Bottleneck
**Learning:** In Python OpenCV applications, using `cv2.CV_64F` for intermediate operations like `cv2.Laplacian` creates a significant performance bottleneck without practical benefit for aesthetic scoring.
**Action:** Default to `cv2.CV_32F` to gain significant speedups (~70% faster in tests) when extreme double precision is not strictly required. Remember to explicitly cast values like `.var()` or `.median()` back to standard Python floats using `float()` to avoid downstream serialization issues.
