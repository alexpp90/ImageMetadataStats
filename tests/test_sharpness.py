from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from image_metadata_analyzer.sharpness import (
    SharpnessCategories,
    calculate_sharpness,
    categorize_sharpness,
    find_related_files,
    get_image_data,
)


# Mock data for testing
@pytest.fixture
def mock_image():
    # Create a simple 100x100 black image with a white square in center
    # This should have some edges and thus variance
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    # Drawing logic would depend on actual cv2, but here we just return array
    img[25:75, 25:75] = 255
    return img


@pytest.fixture
def mock_flat_image():
    # Completely flat image, variance should be 0
    return np.zeros((100, 100, 3), dtype=np.uint8)


def test_sharpness_categories():
    assert SharpnessCategories.get_name(1) == "Sharp"
    assert SharpnessCategories.get_name(3) == "Blurry"
    assert SharpnessCategories.get_color(1) == "green"
    assert SharpnessCategories.get_color(3) == "red"


def test_categorize_sharpness():
    # Thresholds: Blur < 100, Sharp > 500
    blur_t = 100
    sharp_t = 500

    assert categorize_sharpness(50, blur_t, sharp_t) == SharpnessCategories.BLURRY
    assert categorize_sharpness(200, blur_t, sharp_t) == SharpnessCategories.ACCEPTABLE
    assert categorize_sharpness(600, blur_t, sharp_t) == SharpnessCategories.CRISP


@patch("image_metadata_analyzer.sharpness.cv2.imread")
def test_get_image_data_standard(mock_imread):
    mock_imread.return_value = np.zeros((10, 10, 3))
    path = Path("test.jpg")
    res = get_image_data(path)
    assert res is not None
    mock_imread.assert_called_once_with("test.jpg")


@patch("image_metadata_analyzer.sharpness.rawpy.imread")
def test_get_image_data_raw(mock_raw_imread):
    # Setup mock raw object
    mock_raw_obj = MagicMock()
    mock_raw_obj.__enter__.return_value = mock_raw_obj
    mock_raw_obj.postprocess.return_value = np.zeros((10, 10, 3), dtype=np.uint8)
    mock_raw_imread.return_value = mock_raw_obj

    path = Path("test.ARW")
    res = get_image_data(path)

    assert res is not None
    mock_raw_imread.assert_called_once_with("test.ARW")
    mock_raw_obj.postprocess.assert_called_once()


def test_find_related_files(tmp_path):
    # Create dummy files
    (tmp_path / "DSC001.ARW").touch()
    (tmp_path / "DSC001.JPG").touch()
    (tmp_path / "DSC001.xmp").touch()
    (tmp_path / "DSC002.ARW").touch()

    target = tmp_path / "DSC001.ARW"
    related = find_related_files(target)

    related_names = {f.name for f in related}
    assert "DSC001.ARW" in related_names
    assert "DSC001.JPG" in related_names
    assert "DSC001.xmp" in related_names
    assert "DSC002.ARW" not in related_names


@patch("image_metadata_analyzer.sharpness.get_image_data")
def test_calculate_sharpness(mock_get_data):
    # Case 1: Flat image (Variance = 0)
    flat = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_get_data.return_value = flat
    score = calculate_sharpness(Path("dummy.jpg"))
    assert score == 0.0

    # Case 2: Image with noise/edges
    # Creating a random noise image will definitely have variance
    noise = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    mock_get_data.return_value = noise
    score = calculate_sharpness(Path("noise.jpg"))
    assert score > 0.0


@patch("image_metadata_analyzer.sharpness.get_image_data")
def test_calculate_sharpness_crop(mock_get_data):
    # Verify that it processes the center crop
    # We can't easily spy on the internal cv2 calls inside the function without more mocking,
    # but we can verify the logic by creating an image that is only sharp in the center.

    # 100x100 image
    # Center 50% is from 25 to 75.

    # Image A: White edges, Black center.
    img_edges = np.zeros((100, 100, 3), dtype=np.uint8)
    img_edges[0:25, :] = 255  # Top edge

    # Image B: Black edges, Noise center.
    img_center = np.zeros((100, 100, 3), dtype=np.uint8)
    # Add noise to center 25:75
    img_center[25:75, 25:75] = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)

    # Test Edge Image (Should be low score because center is flat black)
    mock_get_data.return_value = img_edges
    score_edges = calculate_sharpness(Path("edges.jpg"))

    # Test Center Image (Should be high score because center has noise)
    mock_get_data.return_value = img_center
    score_center = calculate_sharpness(Path("center.jpg"))

    assert score_center > score_edges
