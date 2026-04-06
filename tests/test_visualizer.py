from pathlib import Path
from unittest.mock import patch, MagicMock
from image_metadata_analyzer.visualizer import (
    get_shutter_speed_plot,
    get_aperture_plot,
    get_iso_plot,
    get_focal_length_plot,
    get_equivalent_focal_length_plot,
    get_apsc_equivalent_focal_length_plot,
    get_lens_plot,
    get_combination_plot,
    create_plots,
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


def test_get_equivalent_focal_length_plot():
    data = [{"Focal Length (35mm)": 50.2}, {"Focal Length (35mm)": 84.8}]
    fig = get_equivalent_focal_length_plot(data)
    assert fig is not None


def test_get_equivalent_focal_length_plot_empty():
    data = [{"Focal Length": 50}]
    fig = get_equivalent_focal_length_plot(data)
    assert fig is None


def test_get_apsc_equivalent_focal_length_plot():
    data = [{"Focal Length (35mm)": 75.0}, {"Focal Length (35mm)": 50.0}]
    fig = get_apsc_equivalent_focal_length_plot(data)
    assert fig is not None


def test_get_apsc_equivalent_focal_length_plot_empty():
    data = []
    fig = get_apsc_equivalent_focal_length_plot(data)
    assert fig is None


def test_get_apsc_equivalent_focal_length_plot_missing_key():
    data = [{"Aperture": 2.8}]
    fig = get_apsc_equivalent_focal_length_plot(data)
    assert fig is None
def test_get_lens_plot():
    data = [{"Lens": "Lens A"}, {"Lens": "Lens B"}]
    fig = get_lens_plot(data)
    assert fig is not None


def test_get_combination_plot():
    data = [{"Aperture": 2.8, "Focal Length": 50}]
    fig = get_combination_plot(data)
    assert fig is not None


@patch("image_metadata_analyzer.visualizer._open_file_for_user")
def test_create_plots(mock_open, tmp_path):
    data = [
        {
            "Shutter Speed": 0.01,
            "Aperture": 2.8,
            "ISO": 100,
            "Focal Length": 50,
            "Focal Length (35mm)": 75,
            "Lens": "Test Lens",
        }
    ]

    # We mock fig.savefig to avoid issues with matplotlib interacting with the fake PIL module in sys.modules
    # because tests/test_utils.py injects a fake PIL into sys.modules to mock it out, which breaks
    # matplotlib when it tries to import PIL.PngImagePlugin if run in the same test session.
    with patch("matplotlib.figure.Figure.savefig") as mock_savefig:
        create_plots(data, tmp_path, show_plots=True)

        # Even though we mock savefig, we can verify that create_plots ran properly and
        # attempted to save the correct files.
        expected_files = [
            "shutter_speed_distribution.png",
            "aperture_distribution.png",
            "iso_distribution.png",
            "focal_length_distribution.png",
            "equivalent_focal_length_35mm_distribution.png",
            "equivalent_focal_length_apsc_distribution.png",
            "lens_usage.png",
            "aperture_focal_length_combinations.png",
        ]

        # Verify savefig was called with paths for all our expected files
        saved_paths = [call.args[0].name for call in mock_savefig.call_args_list if call.args]
        for filename in expected_files:
            assert filename in saved_paths, f"Expected {filename} to be saved."

        assert mock_open.called


@patch("image_metadata_analyzer.visualizer._open_file_for_user")
def test_create_plots_empty_data(mock_open, tmp_path):
    data = []

    with patch("matplotlib.figure.Figure.savefig") as mock_savefig:
        create_plots(data, tmp_path, show_plots=True)

        # Should not save any png files
        mock_savefig.assert_not_called()

        # _open_file_for_user shouldn't be called because no plots were generated
        assert not mock_open.called


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
