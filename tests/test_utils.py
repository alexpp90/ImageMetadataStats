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
    sys.modules['rawpy'] = MagicMock()

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


class TestLoadImagePreview(unittest.TestCase):
    @patch('image_metadata_analyzer.utils.Image.open')
    def test_standard_image(self, mock_open):
        """Test loading a standard image (e.g., JPEG)."""
        mock_img = MagicMock()
        mock_open.return_value = mock_img

        path = Path('test.jpg')
        result = load_image_preview(path)

        mock_open.assert_called_once_with(path)
        mock_img.thumbnail.assert_called_once_with((150, 150))
        self.assertEqual(result, mock_img)

    @patch('image_metadata_analyzer.utils.Image.fromarray')
    @patch('image_metadata_analyzer.utils.rawpy.imread')
    def test_raw_image(self, mock_imread, mock_fromarray):
        """Test loading a RAW image."""
        mock_raw = MagicMock()
        mock_rgb = MagicMock()
        mock_raw.__enter__.return_value = mock_raw
        mock_raw.postprocess.return_value = mock_rgb
        mock_imread.return_value = mock_raw

        mock_img = MagicMock()
        mock_fromarray.return_value = mock_img

        path = Path('test.arw')
        result = load_image_preview(path)

        mock_imread.assert_called_once_with('test.arw')
        mock_raw.postprocess.assert_called_once_with(use_camera_wb=True, bright=1.0, half_size=True)
        mock_fromarray.assert_called_once_with(mock_rgb)
        mock_img.thumbnail.assert_called_once_with((150, 150))
        self.assertEqual(result, mock_img)

    @patch('image_metadata_analyzer.utils.Image.open')
    def test_full_res(self, mock_open):
        """Test loading a standard image at full resolution."""
        mock_img = MagicMock()
        mock_open.return_value = mock_img

        path = Path('test.jpg')
        result = load_image_preview(path, full_res=True)

        mock_open.assert_called_once_with(path)
        mock_img.thumbnail.assert_not_called()
        self.assertEqual(result, mock_img)

    @patch('image_metadata_analyzer.utils.Image.open')
    @patch('image_metadata_analyzer.utils.rawpy.imread')
    def test_raw_fallback_to_pillow(self, mock_imread, mock_open):
        """Test that Pillow is used if rawpy fails."""
        mock_imread.side_effect = Exception("rawpy failed")

        mock_img = MagicMock()
        mock_open.return_value = mock_img

        path = Path('test.arw')
        result = load_image_preview(path)

        mock_imread.assert_called_once_with('test.arw')
        mock_open.assert_called_once_with(path)
        mock_img.thumbnail.assert_called_once_with((150, 150))
        self.assertEqual(result, mock_img)

    @patch('image_metadata_analyzer.utils.Image.open')
    def test_exception_handling(self, mock_open):
        """Test that None is returned on common image loading exceptions."""
        mock_open.side_effect = OSError("File not found or access denied")

        path = Path('test.jpg')
        result = load_image_preview(path)

        self.assertIsNone(result)

    @patch('image_metadata_analyzer.utils.Image.open')
    def test_unidentified_image_error(self, mock_open):
        """Test that None is returned when Pillow cannot identify the image."""
        mock_open.side_effect = PIL.Image.UnidentifiedImageError("Cannot identify image file")

        path = Path('test.jpg')
        result = load_image_preview(path)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
