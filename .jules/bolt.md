## 2024-08-26 - Optimize cv2.Laplacian precision
**Learning:** Using `cv2.CV_64F` for intermediate operations like `cv2.Laplacian` creates a measurable performance bottleneck compared to `cv2.CV_32F`, causing unnecessary slowdowns without meaningful benefit for sharpness and noise analysis. Results of functions on these objects like `.var()` return as `numpy.float32`.
**Action:** Default to `cv2.CV_32F` for OpenCV operations to gain significant speedups, and explicitly cast results back to standard Python floats using `float()` to avoid downstream serialization or typing errors.
