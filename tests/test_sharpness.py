import pytest
from pathlib import Path
import numpy as np
from unittest.mock import patch, MagicMock
from image_metadata_analyzer.sharpness import (
    calculate_sharpness,
    calculate_noise,
    categorize_sharpness,
    find_related_files,
    SharpnessCategories,
    get_image_data,
    rawpy,
)
import image_metadata_analyzer.sharpness as shp


# Mock data for testing
@pytest.fixture
def mock_image():
    # Create a simple 100x100 black image with a white square in center
    # This should have some edges and thus variance
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    MagicMock()
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


def test_categorize_sharpness():
    # Thresholds: Blur < 100, Sharp > 500
    blur_t = 100
    sharp_t = 500

    assert categorize_sharpness(50, blur_t, sharp_t) == SharpnessCategories.BLURRY
    assert categorize_sharpness(200, blur_t, sharp_t) == SharpnessCategories.ACCEPTABLE
    assert categorize_sharpness(600, blur_t, sharp_t) == SharpnessCategories.CRISP


@patch.object(shp, "Image")
def test_get_image_data_standard(mock_pil_image):
    # Setup mock Pillow image
    mock_img = MagicMock()
    mock_img.__enter__.return_value = mock_img
    # The return of convert("RGB") should be something that np.array() can handle
    # A 10x10x3 uint8 array is perfect.
    mock_img.convert.return_value = np.zeros((10, 10, 3), dtype=np.uint8)
    mock_pil_image.open.return_value = mock_img

    path = Path("test.jpg")
    res = get_image_data(path)
    assert res is not None
    mock_pil_image.open.assert_called_once_with(path)


@pytest.mark.skipif(rawpy is None, reason="rawpy is not installed")
@patch.object(shp, "rawpy")
def test_get_image_data_raw(mock_rawpy):
    # Setup mock raw object
    mock_raw_obj = MagicMock()
    mock_raw_obj.__enter__.return_value = mock_raw_obj
    mock_raw_obj.postprocess.return_value = np.zeros((10, 10, 3), dtype=np.uint8)
    mock_rawpy.imread.return_value = mock_raw_obj

    path = Path("test.ARW")
    res = get_image_data(path)

    assert res is not None
    mock_rawpy.imread.assert_called_once_with("test.ARW")
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


@patch.object(shp, "get_image_data")
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


@patch.object(shp, "get_image_data")
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


@patch.object(shp, "get_image_data")
@patch.object(shp, "cv2")
def test_calculate_sharpness_exception(mock_cv2, mock_get_data):
    # Setup mock to return a valid dummy image
    mock_get_data.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    # Mock cvtColor to raise an exception
    mock_cv2.cvtColor.side_effect = Exception("Mocked error")

    # The function should catch the exception and return 0.0
    score = calculate_sharpness(Path("error.jpg"))
    assert score == 0.0


@patch.object(shp, "get_image_data")
@patch.object(shp, "cv2")
def test_calculate_sharpness_grid_exception(mock_cv2, mock_get_data):
    # Setup mock to return a valid dummy image large enough for grid processing
    mock_get_data.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    # Mock cvtColor to pass normally
    mock_cv2.cvtColor.return_value = np.zeros((100, 100), dtype=np.uint8)

    # Mock Laplacian to raise an exception
    mock_cv2.Laplacian.side_effect = Exception("Mocked grid error")

    # Call with grid_size > 1
    score = calculate_sharpness(Path("grid_error.jpg"), grid_size=2)
    assert score == 0.0


@patch.object(shp, "get_image_data")
@patch.object(shp, "cv2")
def test_calculate_noise_exception(mock_cv2, mock_get_data):
    # Setup mock to return a valid dummy image
    mock_get_data.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    # Mock cvtColor to raise an exception
    mock_cv2.cvtColor.side_effect = Exception("Mocked noise error")

    # The function should catch the exception and return 0.0
    score = calculate_noise(Path("error.jpg"))
    assert score == 0.0
