import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from image_metadata_analyzer.cli import main


def test_main_no_args(capsys):
    """Test that main exits with an error if no arguments are provided."""
    with patch.object(sys, "argv", ["cli.py"]):
        with pytest.raises(SystemExit):
            main()

    captured = capsys.readouterr()
    assert "the following arguments are required: root_folder" in captured.err


def test_main_invalid_folder(capsys, tmp_path):
    """Test that main reports an error if the specified folder does not exist."""
    invalid_folder = tmp_path / "nonexistent"
    with patch.object(sys, "argv", ["cli.py", str(invalid_folder)]):
        main()

    captured = capsys.readouterr()
    assert f"Error: Folder not found at '{invalid_folder}'" in captured.out


def test_main_no_supported_images(capsys, tmp_path):
    """Test that main stops if the folder exists but has no supported images."""
    with patch.object(sys, "argv", ["cli.py", str(tmp_path)]):
        main()

    captured = capsys.readouterr()
    assert f"Scanning for images in '{tmp_path}'..." in captured.out
    assert "No supported image files found." in captured.out


def test_main_images_no_metadata(capsys, tmp_path):
    """Test that main stops if images are found but no metadata can be extracted."""
    img_path = tmp_path / "test.jpg"
    img_path.touch()

    with patch.object(sys, "argv", ["cli.py", str(tmp_path)]):
        with patch("image_metadata_analyzer.cli.get_exif_data", return_value=None):
            main()

    captured = capsys.readouterr()
    assert "Found 1 image files. Extracting metadata..." in captured.out
    assert "Could not extract any valid EXIF metadata from the found images." in captured.out


def test_main_success(capsys, tmp_path):
    """Test a successful run processing images and invoking downstream functions."""
    img_path1 = tmp_path / "test1.jpg"
    img_path2 = tmp_path / "test2.png"
    img_path1.touch()
    img_path2.touch()

    fake_metadata = {"Aperture": 2.8, "Shutter Speed": 0.01}
    out_dir = tmp_path / "out"

    args = [
        "cli.py",
        str(tmp_path),
        "--output", str(out_dir),
        "--debug",
        "--show-plots"
    ]

    with patch.object(sys, "argv", args):
        with patch("image_metadata_analyzer.cli.get_exif_data", return_value=fake_metadata) as mock_get_exif:
            with patch("image_metadata_analyzer.cli.analyze_data") as mock_analyze:
                with patch("image_metadata_analyzer.cli.create_plots") as mock_create_plots:
                    main()

    captured = capsys.readouterr()
    assert "Found 2 image files. Extracting metadata..." in captured.out

    assert mock_get_exif.call_count == 2
    mock_get_exif.assert_any_call(img_path1, debug=True)
    mock_get_exif.assert_any_call(img_path2, debug=True)

    mock_analyze.assert_called_once_with([fake_metadata, fake_metadata])
    mock_create_plots.assert_called_once_with([fake_metadata, fake_metadata], out_dir, show_plots=True)
