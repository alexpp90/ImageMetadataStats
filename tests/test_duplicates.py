import pytest
from unittest.mock import patch, MagicMock
from image_metadata_analyzer.duplicates import find_duplicates, move_to_trash, get_file_hash


@pytest.fixture
def temp_image_folder(tmp_path):
    """Creates a temporary folder with some image files."""
    folder = tmp_path / "images"
    folder.mkdir()

    # Image 1 (Original)
    img1 = folder / "img1.jpg"
    img1.write_bytes(b"image_content_A")

    # Image 2 (Duplicate of 1)
    img2 = folder / "img2.jpg"
    img2.write_bytes(b"image_content_A")

    # Image 3 (Unique content, same size as A)
    # This is tricky with short strings, but let's just make it different content
    img3 = folder / "img3.jpg"
    img3.write_bytes(b"image_content_B")

    # Image 4 (Unique size)
    img4 = folder / "img4.png"
    img4.write_bytes(b"image_content_C_longer")

    # Image 5 (HEIC, same content as A)
    img5 = folder / "img5.heic"
    img5.write_bytes(b"image_content_A")

    return folder


def test_get_file_hash(temp_image_folder):
    img1 = temp_image_folder / "img1.jpg"
    h = get_file_hash(img1)
    assert h is not None
    assert len(h) == 32  # MD5 hexdigest length


def test_find_duplicates(temp_image_folder):
    duplicates = find_duplicates(temp_image_folder)

    # We expect 1 group of duplicates (img1 and img2 and img5)
    # img1 and img2 are jpg, img5 is heic. All have content 'image_content_A' (15 bytes)
    assert len(duplicates) == 1
    group = duplicates[0]

    assert len(group['files']) == 3
    filenames = {p.name for p in group['files']}
    assert "img1.jpg" in filenames
    assert "img2.jpg" in filenames
    assert "img5.heic" in filenames
    assert "img3.jpg" not in filenames


def test_find_duplicates_no_duplicates(tmp_path):
    f = tmp_path / "unique"
    f.mkdir()
    (f / "a.jpg").write_bytes(b"1")
    (f / "b.jpg").write_bytes(b"2")

    assert len(find_duplicates(f)) == 0


def test_find_duplicates_progress_callback(temp_image_folder):
    # img1, img2, img3, img5 have same size. img4 different.
    # Group 1: img1, img2, img3, img5 (size 15 bytes) -> 4 files to hash
    # Group 2: img4 -> 1 file -> ignored by preliminary size check
    # Logic: "Filter for groups that have more than 1 file".
    # So img4 is skipped before hashing.
    # Total to hash = 4.

    mock_callback = MagicMock()
    find_duplicates(temp_image_folder, callback=mock_callback)

    # Should be called 4 times
    assert mock_callback.call_count == 4
    # Check last call args
    mock_callback.assert_called_with(4, 4)


@patch("image_metadata_analyzer.duplicates.send2trash")
def test_move_to_trash(mock_send2trash, tmp_path):
    f = tmp_path / "delete_me.txt"
    f.touch()

    move_to_trash(f)
    mock_send2trash.assert_called_once_with(str(f))


@patch("image_metadata_analyzer.duplicates.send2trash")
def test_move_to_trash_failure(mock_send2trash, tmp_path):
    mock_send2trash.side_effect = OSError("Access denied")
    f = tmp_path / "delete_me.txt"

    with pytest.raises(OSError):
        move_to_trash(f)
