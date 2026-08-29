import pytest
from unittest.mock import patch, MagicMock


# Mock out tk and ttk heavily for headless CI
@pytest.fixture(autouse=True)
def mock_gui_deps():
    with (
        patch("photo_selector_toolbox.gui.app.tk.Tk") as MockTk,
        patch("photo_selector_toolbox.gui.app.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.app.tk.Frame"),
        patch("photo_selector_toolbox.gui.app.tk.Label"),
        patch("photo_selector_toolbox.gui.app.tk.StringVar", return_value=MagicMock()),
        patch("photo_selector_toolbox.gui.app.tk.DoubleVar", return_value=MagicMock()),
        patch("photo_selector_toolbox.gui.app.tk.BooleanVar", return_value=MagicMock()),
        patch("photo_selector_toolbox.gui.app.ttk") as MockTtk,
        patch("photo_selector_toolbox.gui.app.FigureCanvasTkAgg"),
        patch("photo_selector_toolbox.gui.app.ImageTk.PhotoImage"),
    ):
        yield MockTk, MockTtk


def test_image_library_statistics_init(mock_gui_deps):
    from photo_selector_toolbox.gui.app import ImageLibraryStatistics

    parent = MagicMock()
    frame = ImageLibraryStatistics(parent)
    assert not frame.is_analyzing
    assert frame.root_folder_var is not None


def test_duplicate_finder_init(mock_gui_deps):
    from photo_selector_toolbox.gui.app import DuplicateFinder

    parent = MagicMock()
    finder = DuplicateFinder(parent)
    assert not finder.is_scanning
    assert finder.found_duplicates == []


def test_sidebar_init(mock_gui_deps):
    from photo_selector_toolbox.gui.app import Sidebar

    parent = MagicMock()
    controller = MagicMock()
    sidebar = Sidebar(parent, controller)
    assert sidebar.controller == controller


def test_main_app_init(mock_gui_deps):
    from photo_selector_toolbox.gui.app import MainApp

    with patch("photo_selector_toolbox.gui.app.SharpnessTool") as MockTool:
        MockTool.__name__ = "SharpnessTool"
        # Since Tk is mocked, MainApp's super init won't actually fail.
        # We need to ensure the mocked methods exist to avoid AttributeError.
        app = MainApp()
        assert "ImageLibraryStatistics" in app.frames
        assert "DuplicateFinder" in app.frames
        assert "SharpnessTool" in app.frames


def test_show_about(mock_gui_deps):
    from photo_selector_toolbox.gui.app import MainApp
    with (
        patch("photo_selector_toolbox.gui.app.tk.Tk"),
        patch("photo_selector_toolbox.gui.app.SharpnessTool") as MockTool,
        patch("photo_selector_toolbox.gui.app.AboutDialog") as MockAbout
    ):
        MockTool.__name__ = "SharpnessTool"
        app = MainApp()
        app.show_about()
        MockAbout.assert_called_once_with(app)
