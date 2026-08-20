## 2024-03-24 - Speeding up OpenCV Laplacian calculation
**Learning:** Using `cv2.CV_64F` for simple sharpness estimation on 8-bit image data is unnecessarily slow. The exact precision of a 64-bit float isn't required for standard sharpness variance logic.
**Action:** Default to `cv2.CV_32F` for a significant speedup (~4x) with negligible loss of relevant precision. When changing precision, ensure downstream components relying on native Python `float` aren't affected by returning `numpy.float32`.
