## 2024-10-24 - OpenCV Laplacian Optimization
**Learning:** Using cv2.CV_64F for intermediate operations like cv2.Laplacian creates a measurable performance bottleneck. Extreme double precision is rarely strictly required for sharpness/noise estimation in photos.
**Action:** Default to cv2.CV_32F to gain significant speedups (40-60%). Values derived from this (like .var() or .median()) may become numpy.float32, so explicitly cast them back to float() to avoid downstream type or serialization errors.
