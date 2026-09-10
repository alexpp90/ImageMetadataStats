## 2024-05-18 - OpenCV Laplacian Precision Impact
**Learning:** Computing Laplacian variance/MAD with `cv2.CV_32F` is ~4x faster than `cv2.CV_64F` for high-resolution images, with effectively identical results for thresholding or categorization. However, OpenCV functions might return `numpy.float32`, which can break downstream logic expecting native floats.
**Action:** Always prefer `CV_32F` over `CV_64F` for heavy filtering operations where absolute sub-decimal precision isn't critical, but explicitly cast results with `float()` to avoid downstream type issues or test failures.
