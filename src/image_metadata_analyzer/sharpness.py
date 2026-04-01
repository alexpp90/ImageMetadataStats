import os

# Suppress OpenCV terminal noise from its internal C++ decoders (like grfmt_tiff.cpp)
# Must be set BEFORE importing cv2
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

import cv2
import numpy as np

try:
    if hasattr(cv2, 'utils') and hasattr(cv2.utils, 'logging'):
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except Exception:
    pass

try:
    import rawpy
except ImportError:
    rawpy = None
from pathlib import Path
import glob
from typing import List, Optional
import logging
from PIL import Image

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
    Handles RAW files via rawpy and standard images via Pillow (falling back to cv2).
    """
    path_str = str(filepath)
    ext = filepath.suffix.lower()

    try:
        # 1. Try rawpy for known RAW formats
        raw_exts = {
            ".arw", ".nef", ".cr2", ".dng", ".raw", ".cr3", 
            ".raf", ".orf", ".rw2", ".pef", ".srw", ".sr2"
        }

        if ext in raw_exts and rawpy is not None:
            try:
                with rawpy.imread(path_str) as raw:
                    rgb = raw.postprocess(
                        use_camera_wb=True, no_auto_bright=True, bright=1.0
                    )
                    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            except Exception as e:
                logger.warning(f"Failed to read RAW file {path_str} with rawpy: {e}")
                # Fallthrough to Pillow for fallback

        # 2. Try Pillow (better TIFF support, much quieter than OpenCV)
        try:
            with Image.open(filepath) as img:
                # Ensure it is in RGB mode for consistent conversion
                rgb_img = img.convert("RGB")
                numpy_img = np.array(rgb_img)
                # Convert RGB (Pillow) to BGR (OpenCV)
                return cv2.cvtColor(numpy_img, cv2.COLOR_RGB2BGR)
        except Exception:
            # If Pillow fails, we do NOT fall back to cv2.imread anymore because
            # it is noisy on corrupted TIFFs and unlikely to succeed if Pillow failed.
            logger.debug(f"Both rawpy and Pillow failed to read {path_str}")
            return None

    except Exception as e:
        # Restore logging for Python exceptions so we can see why a file is "skipped"
        logger.error(f"Error reading image {path_str}: {e}")
        return None


def calculate_noise(filepath: Path) -> float:
    """
    Estimates the noise level in an image.
    Uses the Median Absolute Deviation (MAD) of the image's Laplacian,
    which is a common approach to estimate standard deviation of Gaussian noise.

    Returns a float score (higher means more noise).
    Returns 0.0 if image cannot be read.
    """
    img = get_image_data(filepath)

    if img is None:
        return 0.0

    try:
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply Laplacian filter
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)

        # Calculate Median Absolute Deviation (MAD)
        # Using the standard constant 0.6745 for Gaussian distribution
        # sigma = MAD / 0.6745
        mad = np.median(np.abs(laplacian - np.median(laplacian)))
        sigma = mad / 0.6745

        return sigma

    except Exception as e:
        logger.error(f"Error calculating noise for {filepath}: {e}")
        return 0.0


def calculate_sharpness(filepath: Path, grid_size: int = 1) -> float:
    """
    Calculates the sharpness score of an image using the Laplacian Variance method.
    The image is converted to grayscale and cropped to the center 50% before analysis.

    If grid_size > 1, the cropped area is split into grid_size x grid_size blocks,
    and the maximum score among the blocks is returned.

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

        if grid_size <= 1:
            # Original behavior: Calculate Laplacian Variance for the whole crop
            score = cv2.Laplacian(cropped, cv2.CV_64F).var()
            return score
        else:
            # Grid-based analysis: find the maximum sharpness among blocks
            ch, cw = cropped.shape
            block_h = ch // grid_size
            block_w = cw // grid_size

            # If blocks are too small, fallback to global
            if block_h < 10 or block_w < 10:
                return cv2.Laplacian(cropped, cv2.CV_64F).var()

            max_score = 0.0

            for r in range(grid_size):
                for c in range(grid_size):
                    y0 = r * block_h
                    y1 = y0 + block_h
                    x0 = c * block_w
                    x1 = x0 + block_w

                    block = cropped[y0:y1, x0:x1]
                    score = cv2.Laplacian(block, cv2.CV_64F).var()
                    if score > max_score:
                        max_score = score

            return max_score

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
    related = []
    if not filepath.exists():
        return related

    parent = filepath.parent
    stem = filepath.stem

    try:
        # Use glob for efficient filtering instead of O(N) directory iteration.
        # Escape the stem to handle filenames with glob-special characters (e.g. '[', ']', '*').
        escaped_stem = glob.escape(stem)

        # glob with f"{escaped_stem}.*" matches files with the same stem.
        # We also check that they are files, not directories.
        for f in parent.glob(f"{escaped_stem}.*"):
            if f.is_file() and f.stem == stem:
                related.append(f)

        # If the file has no extension (e.g. "DSC001"), glob f"{escaped_stem}.*" won't find it.
        # But we must ensure we include the exact match. We don't need glob for it,
        # since we know the exact filename.
        exact_match = parent / stem
        if exact_match.is_file() and exact_match not in related:
            related.append(exact_match)

    except Exception as e:
        logger.warning(f"Error scanning for related files in {parent}: {e}")
        # Fallback: just return the file itself if scan fails
        if filepath not in related:
            related.append(filepath)

    return related
