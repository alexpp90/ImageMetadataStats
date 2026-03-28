import pytest
from unittest.mock import patch, MagicMock


# Mock out tk and ttk heavily for headless CI
@pytest.fixture(autouse=True)
def mock_gui_deps():
    with (
        patch("image_metadata_analyzer.gui.tk.Tk") as MockTk,
        patch("image_metadata_analyzer.gui.tk.StringVar", return_value=MagicMock()),
        patch("image_metadata_analyzer.gui.tk.DoubleVar", return_value=MagicMock()),
        patch("image_metadata_analyzer.gui.tk.BooleanVar", return_value=MagicMock()),
        patch("image_metadata_analyzer.gui.ttk") as MockTtk,
        patch("image_metadata_analyzer.gui.FigureCanvasTkAgg"),
        patch("image_metadata_analyzer.gui.ImageTk.PhotoImage"),
    ):
        yield MockTk, MockTtk


def test_image_library_statistics_init(mock_gui_deps):
    from image_metadata_analyzer.gui import ImageLibraryStatistics

    parent = MagicMock()
    frame = ImageLibraryStatistics(parent)
    assert not frame.is_analyzing
    assert frame.root_folder_var is not None


def test_duplicate_finder_init(mock_gui_deps):
    from image_metadata_analyzer.gui import DuplicateFinder

    parent = MagicMock()
    finder = DuplicateFinder(parent)
    assert not finder.is_scanning
    assert finder.found_duplicates == []


def test_sidebar_init(mock_gui_deps):
    from image_metadata_analyzer.gui import Sidebar

    parent = MagicMock()
    controller = MagicMock()
    sidebar = Sidebar(parent, controller)
    assert sidebar.controller == controller


def test_main_app_init(mock_gui_deps):
    from image_metadata_analyzer.gui import MainApp

    with patch("image_metadata_analyzer.gui.SharpnessTool") as MockTool:
        MockTool.__name__ = "SharpnessTool"
        # Since Tk is mocked, MainApp's super init won't actually fail.
        # We need to ensure the mocked methods exist to avoid AttributeError.
        app = MainApp()
        assert "ImageLibraryStatistics" in app.frames
        assert "DuplicateFinder" in app.frames
        assert "SharpnessTool" in app.frames
