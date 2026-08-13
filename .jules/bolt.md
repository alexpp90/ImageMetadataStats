## 2025-05-24 - OpenCV Precision Optimization
**Learning:** In Tkinter/Python desktop apps processing large 40MP+ images, using `cv2.CV_64F` for Laplacian variance creates a measurable bottleneck.
**Action:** Default to `cv2.CV_32F` for intermediate operations like `cv2.Laplacian` to gain 40-60% performance speedups when extreme double precision isn't required.
