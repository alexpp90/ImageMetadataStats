"""
Cross-platform compatibility tests.

Verifies that core modules import and function correctly on all platforms
(Mac, Linux, Windows). Platform-specific tests use markers defined in
conftest.py to skip automatically on the wrong OS.
"""
import pytest


# ── Core import tests (all platforms) ────────────────────────────────

def test_models_import():
    from photo_selector_toolbox.core.models import ScanResult, ExifData
    assert ScanResult is not None
    assert ExifData is not None


def test_analyzer_import():
    from photo_selector_toolbox.core.analyzer import analyze_data
    assert callable(analyze_data)


def test_duplicates_import():
    from photo_selector_toolbox.core.duplicates import find_duplicates, get_file_hash
    assert callable(find_duplicates)
    assert callable(get_file_hash)


def test_formatting_import():
    from photo_selector_toolbox.core.formatting import format_score, format_meta
    assert callable(format_score)
    assert callable(format_meta)


def test_cache_import():
    from photo_selector_toolbox.core.cache import ScoreCache
    assert ScoreCache is not None


def test_utils_import():
    from photo_selector_toolbox.core import utils
    assert utils is not None


def test_cli_import():
    from photo_selector_toolbox.cli import main
    assert callable(main)


# ── Path handling (cross-platform) ───────────────────────────────────

def test_path_separator_handling(tmp_path):
    """Verify Path objects work correctly on all platforms."""
    test_dir = tmp_path / "test_images" / "subfolder"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "image.jpg"
    test_file.touch()

    assert test_file.exists()
    assert test_file.parent == test_dir
    assert test_file.suffix == ".jpg"
    assert test_file.stem == "image"


def test_unicode_filenames(tmp_path):
    """Verify unicode filenames work on the current platform."""
    unicode_name = tmp_path / "日本語_photo_1.jpg"
    unicode_name.touch()
    assert unicode_name.exists()
    assert unicode_name.name == "日本語_photo_1.jpg"


def test_long_path(tmp_path):
    """Verify reasonable path lengths work."""
    deep = tmp_path
    for i in range(10):
        deep = deep / f"level_{i}"
    deep.mkdir(parents=True)
    test_file = deep / "image.jpg"
    test_file.touch()
    assert test_file.exists()


# ── Platform-specific tests ──────────────────────────────────────────

@pytest.mark.linux_only
def test_exiftool_binary_linux():
    """On Linux, exiftool might be in PATH or bundled."""
    # Just verify the import works; exiftool may not be installed in CI
    from photo_selector_toolbox.exif.readers.exiftool import ExifToolReader
    assert ExifToolReader is not None


@pytest.mark.mac_only
def test_exiftool_binary_mac():
    """On macOS, exiftool might be in PATH or bundled."""
    from photo_selector_toolbox.exif.readers.exiftool import ExifToolReader
    assert ExifToolReader is not None


@pytest.mark.windows_only
def test_exiftool_binary_windows():
    """On Windows, exiftool is typically exiftool.exe."""
    from photo_selector_toolbox.exif.readers.exiftool import ExifToolReader
    assert ExifToolReader is not None


@pytest.mark.gui_required
def test_tkinter_available():
    """Verify tkinter can be imported when a display is available."""
    import tkinter as tk
    assert tk.Tk is not None


# ── File hash consistency across platforms ────────────────────────────

def test_file_hash_deterministic(tmp_path):
    """File hashes should be identical regardless of platform."""
    from photo_selector_toolbox.core.duplicates import get_file_hash

    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"deterministic content for hashing")

    hash1 = get_file_hash(test_file)
    hash2 = get_file_hash(test_file)
    assert hash1 == hash2
    assert len(hash1) == 128  # blake2b hex


def test_file_hash_different_content(tmp_path):
    """Different content produces different hashes on all platforms."""
    from photo_selector_toolbox.core.duplicates import get_file_hash

    file_a = tmp_path / "a.bin"
    file_b = tmp_path / "b.bin"
    file_a.write_bytes(b"content A")
    file_b.write_bytes(b"content B")

    assert get_file_hash(file_a) != get_file_hash(file_b)
