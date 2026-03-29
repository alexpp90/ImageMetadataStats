import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from image_metadata_analyzer.visualizer import (
    get_shutter_speed_plot,
    get_aperture_plot,
    get_iso_plot,
    get_focal_length_plot,
    get_lens_plot,
    get_combination_plot,
    _open_file_for_user,
)


def test_get_shutter_speed_plot():
    data = [{"Shutter Speed": 0.01}, {"Shutter Speed": 0.02}, {"Shutter Speed": 0.01}]
    fig = get_shutter_speed_plot(data)
    assert fig is not None


def test_get_shutter_speed_plot_empty():
    data = []
    fig = get_shutter_speed_plot(data)
    assert fig is None


def test_get_aperture_plot():
    data = [{"Aperture": 2.8}, {"Aperture": 4.0}]
    fig = get_aperture_plot(data)
    assert fig is not None


def test_get_iso_plot():
    data = [{"ISO": 100}, {"ISO": 200}]
    fig = get_iso_plot(data)
    assert fig is not None


def test_get_focal_length_plot():
    data = [{"Focal Length": 50}, {"Focal Length": 85}]
    fig = get_focal_length_plot(data)
    assert fig is not None


def test_get_lens_plot():
    data = [{"Lens": "Lens A"}, {"Lens": "Lens B"}]
    fig = get_lens_plot(data)
    assert fig is not None


def test_get_combination_plot():
    data = [{"Aperture": 2.8, "Focal Length": 50}]
    fig = get_combination_plot(data)
    assert fig is not None


@patch("image_metadata_analyzer.visualizer.subprocess.run")
@patch("image_metadata_analyzer.visualizer.os.startfile", create=True)
def test_open_file_for_user_absolute_path(mock_startfile, mock_run):
    """Test that _open_file_for_user always resolves paths to absolute before calling system commands."""
    test_path = Path("-test_file.png")
    absolute_test_path = test_path.absolute()

    # Test Windows
    with patch("image_metadata_analyzer.visualizer.sys.platform", "win32"):
        _open_file_for_user(test_path)
        mock_startfile.assert_called_once_with(absolute_test_path)
        mock_run.assert_not_called()

    mock_startfile.reset_mock()
    mock_run.reset_mock()

    # Test Darwin
    with patch("image_metadata_analyzer.visualizer.sys.platform", "darwin"):
        _open_file_for_user(test_path)
        mock_run.assert_called_once_with(["open", str(absolute_test_path)], check=True)
        mock_startfile.assert_not_called()

    mock_startfile.reset_mock()
    mock_run.reset_mock()

    # Test Linux/Other
    with patch("image_metadata_analyzer.visualizer.sys.platform", "linux"):
        _open_file_for_user(test_path)
        mock_run.assert_called_once_with(["xdg-open", str(absolute_test_path)], check=True)
        mock_startfile.assert_not_called()
