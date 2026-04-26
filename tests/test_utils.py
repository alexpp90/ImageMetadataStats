import sys
from unittest.mock import MagicMock

# Mock dependencies that are not in the environment to allow importing utils
try:
    import PIL
    import PIL.Image
except ImportError:
    class MockUnidentifiedImageError(Exception):
        pass
    mock_pil = MagicMock()
    mock_image = MagicMock()
    mock_image.UnidentifiedImageError = MockUnidentifiedImageError
    mock_pil.Image = mock_image
    sys.modules['PIL'] = mock_pil
    sys.modules['PIL.Image'] = mock_image
    PIL = mock_pil

try:
    import rawpy
except ImportError:
    class MockLibRawError(Exception):
        pass
    mock_rawpy = MagicMock()
    mock_rawpy.LibRawError = MockLibRawError
    sys.modules['rawpy'] = mock_rawpy
    rawpy = mock_rawpy

import unittest
from unittest.mock import patch
from pathlib import Path
from image_metadata_analyzer.utils import resolve_path, get_exiftool_path, load_image_preview

class TestGetExiftoolPath(unittest.TestCase):

    def setUp(self):
        # Clear the lru_cache before each test to ensure tests don't interfere with each other
        get_exiftool_path.cache_clear()

    @patch('shutil.which')
    def test_found_in_path(self, mock_which):
        """Tests that 'exiftool' is returned if found in system PATH."""
        mock_which.return_value = "/usr/bin/exiftool"
        self.assertEqual(get_exiftool_path(), "exiftool")

    @patch('pathlib.Path.exists')
    @patch('sys.platform', 'linux')
    @patch('shutil.which', return_value=None)
    def test_found_in_source_bin(self, mock_which, mock_exists):
        """Tests that it checks the bundled 'bin' directory when run from source."""
        mock_exists.return_value = True

        path = get_exiftool_path()
        self.assertIsNotNone(path)
        self.assertTrue("bin" in path and "exiftool" in path)

    @patch('pathlib.Path.exists')
    @patch('sys.platform', 'win32')
    @patch('shutil.which', return_value=None)
    def test_found_in_source_bin_windows(self, mock_which, mock_exists):
        """Tests that it checks for 'exiftool.exe' on Windows."""
        mock_exists.return_value = True

        path = get_exiftool_path()
        self.assertIsNotNone(path)
        self.assertTrue("bin" in path and "exiftool.exe" in path)

    @patch('pathlib.Path.exists')
    @patch('sys.platform', 'win32')
    @patch('shutil.which', return_value=None)
    def test_found_in_source_bin_windows_no_ext(self, mock_which, mock_exists):
        """Tests fallback to 'exiftool' without extension on Windows."""
        mock_exists.side_effect = [False, True]

        path = get_exiftool_path()
        self.assertIsNotNone(path)
        self.assertTrue("bin" in path)
        self.assertTrue(path.endswith("exiftool"))

    @patch('pathlib.Path.exists')
    @patch('sys.platform', 'linux')
    @patch('shutil.which', return_value=None)
    def test_not_found(self, mock_which, mock_exists):
        """Tests that it returns None if not found anywhere."""
        mock_exists.return_value = False
        self.assertIsNone(get_exiftool_path())

    @patch('pathlib.Path.exists')
    @patch('sys.platform', 'linux')
    @patch('shutil.which', return_value=None)
    def test_found_in_meipass_frozen(self, mock_which, mock_exists):
        """Tests that it checks sys._MEIPASS when frozen (PyInstaller)."""
        mock_exists.return_value = True

        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, '_MEIPASS', '/tmp/_MEI12345', create=True):
            path = get_exiftool_path()
            self.assertIsNotNone(path)
            expected = str(Path('/tmp/_MEI12345') / 'exiftool')
            self.assertEqual(path, expected)

class TestResolvePath(unittest.TestCase):
    def test_local_path(self):
        """Tests that standard local paths are correctly converted to Path objects."""
        path_str = "/tmp/test.jpg"
        result = resolve_path(path_str)
        self.assertIsInstance(result, Path)
        self.assertEqual(str(result), path_str)

    @patch("sys.platform", "linux")
    @patch("os.getuid", return_value=1000)
    def test_smb_linux(self, mock_getuid):
        """Tests SMB URL resolution to GVFS mount points on Linux."""
        path_str = "smb://myserver/myshare/path/to/image.jpg"
        result = resolve_path(path_str)
        expected = Path("/run/user/1000/gvfs/smb-share:server=myserver,share=myshare/path/to/image.jpg")
        self.assertEqual(result, expected)

    @patch("sys.platform", "darwin")
    def test_smb_macos(self):
        """Tests SMB URL resolution to /Volumes mount points on macOS."""
        path_str = "smb://myserver/myshare/path/to/image.jpg"
        result = resolve_path(path_str)
        expected = Path("/Volumes/myshare/path/to/image.jpg")
        self.assertEqual(result, expected)

    @patch("sys.platform", "win32")
    def test_smb_windows_fallback(self):
        """Tests that SMB URLs return as-is on platforms like Windows."""
        path_str = "smb://myserver/myshare/path/to/image.jpg"
        result = resolve_path(path_str)
        # On non-linux/non-darwin, it should return Path(path_str)
        self.assertEqual(result, Path(path_str))

    @patch("sys.platform", "darwin")
    def test_smb_url_decoding(self):
        """Tests that URL-encoded characters in SMB URLs are correctly decoded."""
        path_str = "smb://myserver/share%20with%20space/file%20name.jpg"
        result = resolve_path(path_str)
        expected = Path("/Volumes/share with space/file name.jpg")
        self.assertEqual(result, expected)

    def test_smb_no_path(self):
        """Tests handling of SMB URLs with no path component."""
        path_str = "smb://myserver"
        result = resolve_path(path_str)
        self.assertEqual(result, Path(path_str))


import tempfile
import os
from PIL import Image as PILImage

class TestLoadImagePreview(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_standard_image(self):
        """Test loading a standard image and resizing it."""
        img_path = self.temp_dir_path / "test.jpg"
        img = PILImage.new("RGB", (300, 300), color="red")
        img.save(img_path)

        result = load_image_preview(img_path, max_size=(150, 150))
        self.assertIsNotNone(result)
        # thumbnail preserves aspect ratio and fits within box
        # Our source is 300x300, max is 150x150, so result should be 150x150
        self.assertEqual(result.size, (150, 150))

    def test_full_res(self):
        """Test loading a standard image at full resolution."""
        img_path = self.temp_dir_path / "test.jpg"
        img = PILImage.new("RGB", (300, 300), color="blue")
        img.save(img_path)

        result = load_image_preview(img_path, full_res=True)
        self.assertIsNotNone(result)
        self.assertEqual(result.size, (300, 300))

    def test_file_not_found(self):
        """Test that None is returned for missing files."""
        img_path = self.temp_dir_path / "does_not_exist.jpg"
        result = load_image_preview(img_path)
        self.assertIsNone(result)

    def test_unidentified_image_error(self):
        """Test that None is returned when Pillow cannot identify the image."""
        img_path = self.temp_dir_path / "bad_image.jpg"
        with open(img_path, "w") as f:
            f.write("This is not an image file")

        result = load_image_preview(img_path)
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
