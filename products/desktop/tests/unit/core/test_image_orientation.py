"""EXIF orientation handling in `core.utils.load_image_preview`.

Every display path in the app (image panels, controllers, the fullscreen
viewer, the sharpness filmstrip, the aesthetic engines) funnels through
`load_image_preview`, so the orientation tag has to be applied there — once,
before any resize.

These tests use real Pillow images written to `tmp_path` rather than mocks:
the defect being guarded against is a geometry bug, and only real pixels can
show it. The rawpy path is mocked, as elsewhere in the suite.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from photo_selector_toolbox.core.utils import apply_exif_orientation, load_image_preview

ORIENTATION_TAG = 0x0112


def _write_jpeg(path: Path, size, orientation: int) -> Path:
    """Write a JPEG of `size` (w, h) carrying the given EXIF orientation tag."""
    img = Image.new("RGB", size, "red")
    # Paint a marker block in the stored top-left corner so a rotation is
    # detectable in the pixels, not only in the dimensions.
    img.paste((0, 0, 255), (0, 0, size[0] // 4, size[1] // 4))
    exif = img.getexif()
    exif[ORIENTATION_TAG] = orientation
    img.save(path, "JPEG", exif=exif.tobytes())
    return path


# Stored size is 40x60 (portrait on disk). Orientations 5-8 swap the axes.
#   1 = as stored, 3 = 180 deg (no swap), 6 = rotate 90 CW, 8 = rotate 90 CCW.
@pytest.mark.parametrize(
    "orientation, expected_size",
    [
        (1, (40, 60)),
        (3, (40, 60)),
        (6, (60, 40)),
        (8, (60, 40)),
    ],
)
def test_orientation_tag_is_applied(tmp_path, orientation, expected_size):
    path = _write_jpeg(tmp_path / f"o{orientation}.jpg", (40, 60), orientation)

    img = load_image_preview(path, max_size=(1200, 900))

    assert img is not None
    assert img.size == expected_size


def test_orientation_6_turns_a_stored_portrait_into_a_landscape_frame(tmp_path):
    """A 40x60 file tagged `Orientation=6` displays rotated 90 deg clockwise.

    That makes it *wider* than tall — the stored aspect ratio is the sensor's,
    not the photographer's. Guards the direction of the transform, which is
    easy to invert.
    """
    path = _write_jpeg(tmp_path / "rotate_cw.jpg", (40, 60), 6)

    img = load_image_preview(path, max_size=(1200, 900))

    assert img is not None
    width, height = img.size
    assert width > height, "Orientation=6 must swap the axes"


def test_orientation_8_is_the_mirror_of_orientation_6(tmp_path):
    """Orientations 6 and 8 rotate opposite ways: the marker corner differs."""
    six = load_image_preview(
        _write_jpeg(tmp_path / "six.jpg", (40, 60), 6), max_size=(1200, 900)
    )
    eight = load_image_preview(
        _write_jpeg(tmp_path / "eight.jpg", (40, 60), 8), max_size=(1200, 900)
    )

    assert six is not None and eight is not None
    assert six.size == eight.size
    # The blue marker sits in the stored top-left; after opposite rotations it
    # lands in opposite corners.
    assert six.getpixel((six.size[0] - 1, 0))[2] > 128
    assert eight.getpixel((0, eight.size[1] - 1))[2] > 128


def test_returned_image_no_longer_carries_an_orientation_tag(tmp_path):
    """The tag must be cleared so nothing downstream rotates a second time."""
    for orientation in (3, 6, 8):
        path = _write_jpeg(tmp_path / f"clear{orientation}.jpg", (40, 60), orientation)
        img = load_image_preview(path, max_size=(1200, 900))
        assert img is not None
        assert img.getexif().get(ORIENTATION_TAG) is None


def test_orientation_is_applied_before_thumbnailing(tmp_path):
    """Ordering guard.

    Thumbnailing first would fit the 400x600 stored portrait into the box as a
    portrait (100x150) and only then rotate it, yielding 150x100 — the right
    aspect ratio by luck but the wrong box. Rotating first gives 600x400 ->
    150x100 as well, so the distinguishing case is a non-square box: with a
    (150, 400) box, rotate-then-fit gives 150x100 while fit-then-rotate gives
    400x266 rotated to 266x400.
    """
    path = _write_jpeg(tmp_path / "big.jpg", (400, 600), 6)

    img = load_image_preview(path, max_size=(150, 400))

    assert img is not None
    assert img.size == (150, 100)


def test_untagged_image_is_untouched(tmp_path):
    img = Image.new("RGB", (40, 60), "red")
    path = tmp_path / "plain.jpg"
    img.save(path, "JPEG")

    result = load_image_preview(path, max_size=(1200, 900))

    assert result is not None
    assert result.size == (40, 60)


def test_apply_exif_orientation_survives_broken_exif():
    """A corrupt EXIF block must cost the rotation, never the preview."""
    broken = MagicMock()
    broken.getexif.side_effect = ValueError("corrupt exif")

    with patch(
        "photo_selector_toolbox.core.utils.ImageOps.exif_transpose",
        side_effect=ValueError("corrupt exif"),
    ):
        assert apply_exif_orientation(broken) is broken


def test_apply_exif_orientation_tolerates_a_copy_returning_implementation():
    """`in_place=True` returns None today; a returned image must be honoured."""
    original = MagicMock()
    rotated = MagicMock()

    with patch(
        "photo_selector_toolbox.core.utils.ImageOps.exif_transpose",
        return_value=rotated,
    ):
        assert apply_exif_orientation(original) is rotated


def test_raw_postprocess_path_is_not_rotated(tmp_path):
    """libraw already applies the camera flip (`user_flip=-1` by default).

    The `Image.fromarray` result carries no EXIF, so `exif_transpose` is a
    no-op — this asserts we did not accidentally rotate it a second time.
    """
    # Landscape 60x40 array: numpy shape is (height, width, channels).
    array = np.zeros((40, 60, 3), dtype=np.uint8)
    array[0, 0] = (0, 0, 255)
    expected = Image.fromarray(array)

    mock_raw = MagicMock()
    mock_raw.__enter__.return_value = mock_raw
    mock_raw.extract_thumb.side_effect = Exception("no embedded thumb")
    mock_raw.postprocess.return_value = array

    with patch(
        "photo_selector_toolbox.core.utils.rawpy.imread", return_value=mock_raw
    ):
        img = load_image_preview(Path("shot.arw"), full_res=True)

    assert img is not None
    assert img.size == (60, 40)
    assert np.array_equal(np.asarray(img), np.asarray(expected))
