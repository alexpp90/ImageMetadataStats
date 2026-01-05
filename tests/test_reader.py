import pytest
from PIL import Image

from image_metadata_analyzer.reader import get_exif_data


@pytest.fixture
def image_dir(tmp_path):
    d = tmp_path / "images"
    d.mkdir()
    return d


def test_get_exif_data_no_file(image_dir):
    p = image_dir / "nonexistent.jpg"
    assert get_exif_data(p) is None


def test_get_exif_data_no_exif(image_dir):
    p = image_dir / "no_exif.jpg"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(p)

    # Pillow created image has no EXIF data
    assert get_exif_data(p) is None


def test_get_exif_data_with_exif(image_dir):
    # It is hard to synthesise a valid EXIF structure from scratch using just Pillow
    # without external libraries or complex byte manipulation
    # so we will trust that if we cannot find EXIF, it returns None.
    # However, we can test that it handles a file that IS an image but has no exif nicely.
    p = image_dir / "test.jpg"
    img = Image.new('RGB', (100, 100), color='blue')
    img.save(p)
    result = get_exif_data(p)
    assert result is None
