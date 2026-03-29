import pytest
from unittest.mock import patch, MagicMock
import sys

# Aggressively mock all internal modules to prevent hangs on Python 3.14
sys.modules["rawpy"] = MagicMock()
sys.modules["image_metadata_analyzer.controllers"] = MagicMock()
sys.modules["image_metadata_analyzer.models"] = MagicMock()
sys.modules["image_metadata_analyzer.sharpness"] = MagicMock()
sys.modules["image_metadata_analyzer.reader"] = MagicMock()
sys.modules["image_metadata_analyzer.utils"] = MagicMock()
sys.modules["image_metadata_analyzer.formatting"] = MagicMock()
sys.modules["send2trash"] = MagicMock()


@pytest.fixture(autouse=True)
def mock_sharpness_gui_deps():
    with (
        patch("image_metadata_analyzer.sharpness_gui.tk.Tk"),
        patch(
            "image_metadata_analyzer.sharpness_gui.tk.StringVar",
            return_value=MagicMock(),
        ),
        patch(
            "image_metadata_analyzer.sharpness_gui.tk.IntVar", return_value=MagicMock()
        ),
        patch(
            "image_metadata_analyzer.sharpness_gui.tk.DoubleVar",
            return_value=MagicMock(),
        ),
        patch(
            "image_metadata_analyzer.sharpness_gui.tk.BooleanVar",
            return_value=MagicMock(),
        ),
        patch("image_metadata_analyzer.sharpness_gui.ttk.Frame"),
        patch("image_metadata_analyzer.sharpness_gui.ttk.LabelFrame"),
        patch("image_metadata_analyzer.sharpness_gui.ttk.Label"),
        patch("image_metadata_analyzer.sharpness_gui.ttk.Button"),
        patch("image_metadata_analyzer.sharpness_gui.ttk.Notebook"),
        patch("image_metadata_analyzer.sharpness_gui.ttk.Treeview"),
        patch("image_metadata_analyzer.sharpness_gui.ttk.Scrollbar"),
        patch("image_metadata_analyzer.sharpness_gui.ImageTk.PhotoImage"),
        patch("image_metadata_analyzer.controllers.ImageCacheManager"),
    ):
        yield


def test_sharpness_tool_init():
    from image_metadata_analyzer.sharpness_gui import SharpnessTool

    parent = MagicMock()

    # Needs to mock out parent methods used in __init__
    parent.register = MagicMock()

    with (
        patch("image_metadata_analyzer.sharpness_gui.tk.Toplevel"),
        patch("image_metadata_analyzer.sharpness_gui.SharpnessTool.setup_ui"),
        patch("image_metadata_analyzer.sharpness_gui.SharpnessTool.setup_focus_ui"),
    ):
        tool = SharpnessTool(parent)
        assert not tool.is_scanning
        assert tool.images_list == []
        assert tool.current_index == -1
