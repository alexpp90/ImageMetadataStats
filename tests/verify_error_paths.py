import sys
from unittest.mock import MagicMock
from pathlib import Path

# Mock cv2, numpy, and rawpy
mock_cv2 = MagicMock()
mock_np = MagicMock()
mock_rawpy = MagicMock()

sys.modules["cv2"] = mock_cv2
sys.modules["numpy"] = mock_np
sys.modules["rawpy"] = mock_rawpy

# Now import the code to test
from image_metadata_analyzer.sharpness import calculate_sharpness, calculate_noise

import unittest
from unittest.mock import patch

class TestErrorPaths(unittest.TestCase):
    @patch("image_metadata_analyzer.sharpness.get_image_data")
    def test_calculate_sharpness_exception(self, mock_get_data):
        # Setup mock to return a valid dummy image
        mock_get_data.return_value = MagicMock() # Representing a numpy array
        # Mock cvtColor to raise an exception
        mock_cv2.cvtColor.side_effect = Exception("Mocked sharpness error")

        # The function should catch the exception and return 0.0
        score = calculate_sharpness(Path("error.jpg"))
        self.assertEqual(score, 0.0)
        # Reset side effect for other tests
        mock_cv2.cvtColor.side_effect = None

    @patch("image_metadata_analyzer.sharpness.get_image_data")
    def test_calculate_noise_exception(self, mock_get_data):
        # Setup mock to return a valid dummy image
        mock_get_data.return_value = MagicMock() # Representing a numpy array
        # Mock cvtColor to raise an exception
        mock_cv2.cvtColor.side_effect = Exception("Mocked noise error")

        # The function should catch the exception and return 0.0
        score = calculate_noise(Path("error.jpg"))
        self.assertEqual(score, 0.0)
        # Reset side effect for other tests
        mock_cv2.cvtColor.side_effect = None

if __name__ == "__main__":
    unittest.main()
