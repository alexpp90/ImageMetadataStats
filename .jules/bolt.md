## 2026-09-07 - Optimize OpenCV Operations
**Learning:** In Python OpenCV applications, using cv2.CV_64F for intermediate operations like cv2.Laplacian creates a measurable performance bottleneck.
**Action:** Default to cv2.CV_32F to gain significant speedups (40-60%) when extreme double precision is not strictly required. Results from operations on CV_32F may be np.float32, so cast them back to float() if returning to generic Python code.
