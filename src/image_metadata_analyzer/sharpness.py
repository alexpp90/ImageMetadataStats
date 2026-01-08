import logging
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
import rawpy

logger = logging.getLogger(__name__)


class SharpnessCategories:
    CRISP = 1
    ACCEPTABLE = 2
    BLURRY = 3

    @staticmethod
    def get_name(category: int) -> str:
        if category == SharpnessCategories.CRISP:
            return "Sharp"
        elif category == SharpnessCategories.ACCEPTABLE:
            return "Acceptable"
        elif category == SharpnessCategories.BLURRY:
            return "Blurry"
        return "Unknown"

    @staticmethod
    def get_color(category: int) -> str:
        if category == SharpnessCategories.CRISP:
            return "green"
        elif category == SharpnessCategories.ACCEPTABLE:
            return "orange"
        elif category == SharpnessCategories.BLURRY:
            return "red"
        return "black"


def get_image_data(filepath: Path) -> Optional[np.ndarray]:
    """
    Reads an image file and returns a numpy array (BGR or Grayscale).
    Handles RAW files via rawpy and standard images via cv2.
    """
    path_str = str(filepath)
    ext = filepath.suffix.lower()

    try:
        # List of common raw extensions
        raw_exts = {".arw", ".nef", ".cr2", ".dng", ".orf", ".rw2", ".raf"}

        if ext in raw_exts:
            try:
                with rawpy.imread(path_str) as raw:
                    # Postprocess to get a usable RGB image
                    # use_camera_wb=True uses the camera's white balance
                    # no_auto_bright=True keeps original brightness
                    # bright=1.0 scales brightness
                    rgb = raw.postprocess(
                        use_camera_wb=True, no_auto_bright=True, bright=1.0
                    )
                    # Convert RGB (rawpy) to BGR (opencv)
                    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            except Exception as e:
                logger.warning(f"Failed to read RAW file {path_str} with rawpy: {e}")
                # Fallback to OpenCV if rawpy fails (some raw formats might be supported by opencv)
                return cv2.imread(path_str)
        else:
            # Standard image
            return cv2.imread(path_str)
    except Exception as e:
        logger.error(f"Error reading image {path_str}: {e}")
        return None


def calculate_sharpness(filepath: Path) -> float:
    """
    Calculates the sharpness score of an image using the Laplacian Variance method.
    The image is converted to grayscale and cropped to the center 50% before analysis.
    Returns a float score (higher is sharper).
    Returns 0.0 if image cannot be read.
    """
    img = get_image_data(filepath)

    if img is None:
        return 0.0

    try:
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Get dimensions
        h, w = gray.shape

        # Crop to center 50%
        # Calculate start and end points
        h_start = int(h * 0.25)
        h_end = int(h * 0.75)
        w_start = int(w * 0.25)
        w_end = int(w * 0.75)

        # Ensure we have a valid crop
        if h_start >= h_end or w_start >= w_end:
            # Fallback to full image if too small
            cropped = gray
        else:
            cropped = gray[h_start:h_end, w_start:w_end]

        # Calculate Laplacian Variance
        score = cv2.Laplacian(cropped, cv2.CV_64F).var()
        return score

    except Exception as e:
        logger.error(f"Error calculating sharpness for {filepath}: {e}")
        return 0.0


def categorize_sharpness(
    score: float, threshold_blur: float, threshold_sharp: float
) -> int:
    """
    Categorizes the sharpness score.
    < threshold_blur -> Blurry (3)
    >= threshold_blur and < threshold_sharp -> Acceptable (2)
    >= threshold_sharp -> Sharp (1)
    """
    if score < threshold_blur:
        return SharpnessCategories.BLURRY
    elif score < threshold_sharp:
        return SharpnessCategories.ACCEPTABLE
    else:
        return SharpnessCategories.CRISP


def find_related_files(filepath: Path) -> List[Path]:
    """
    Finds files related to the given filepath (same name, different extension)
    in the same directory.
    Example: DSC001.ARW -> [DSC001.ARW, DSC001.JPG, DSC001.xmp]
    """
    related: List[Path] = []
    if not filepath.exists():
        return related

    parent = filepath.parent
    stem = filepath.stem

    # We want to be case-insensitive but efficient.
    # Since we are iterating the dir, we can check.
    try:
        for f in parent.iterdir():
            if f.stem == stem and f.is_file():
                related.append(f)
    except Exception as e:
        logger.warning(f"Error scanning for related files in {parent}: {e}")
        # Fallback: just return the file itself if scan fails
        related.append(filepath)

    return related
