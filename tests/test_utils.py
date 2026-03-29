import sys
from unittest.mock import MagicMock

# Mock dependencies that are not in the environment to allow importing utils
# Remove this mock because poetry installed PIL during pytest-cov installation
# and tests in test_visualizer fail because it tries to import PIL.PngImagePlugin
# which this mock breaks
sys.modules['rawpy'] = MagicMock()

import unittest
from unittest.mock import patch
from pathlib import Path
from image_metadata_analyzer.utils import resolve_path

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

    @patch("sys.platform", "linux")
    @patch("os.getuid", side_effect=AttributeError)
    def test_smb_linux_no_getuid(self, mock_getuid):
        """Tests SMB URL resolution on Linux when os.getuid is missing/raises AttributeError."""
        path_str = "smb://myserver/myshare/path/to/image.jpg"
        result = resolve_path(path_str)
        # Should fall back to returning Path(path_str)
        self.assertEqual(result, Path(path_str))

if __name__ == "__main__":
    unittest.main()
