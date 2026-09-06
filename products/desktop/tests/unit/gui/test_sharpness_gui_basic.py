import pytest
from unittest.mock import patch, MagicMock
import sys

# Save original modules to prevent test pollution
original_modules = {}

@pytest.fixture(scope="module", autouse=True)
def mock_sys_modules():
    existing_modules = set(sys.modules.keys())
    import importlib
    modules_to_mock = [
        "rawpy",
        "photo_selector_toolbox.gui.controllers",
        "photo_selector_toolbox.core.models",
        "photo_selector_toolbox.core.sharpness",
        "photo_selector_toolbox.exif.reader",
        "photo_selector_toolbox.core.utils",
        "photo_selector_toolbox.core.formatting",
        "send2trash",
    ]
    for name in modules_to_mock:
        original_modules[name] = sys.modules.get(name)
        mock_mod = MagicMock()
        if name == "photo_selector_toolbox.core.models":
            orig_mod = importlib.import_module("photo_selector_toolbox.core.models")
            mock_mod.ScanResult.side_effect = orig_mod.ScanResult
            mock_mod.ExifData.side_effect = orig_mod.ExifData
        elif name == "photo_selector_toolbox.core.utils":
            orig_mod = importlib.import_module("photo_selector_toolbox.core.utils")
            mock_mod.select_representative.side_effect = orig_mod.select_representative
            mock_mod.is_excluded_subfolder.return_value = False
        sys.modules[name] = mock_mod

    yield

    for name in modules_to_mock:
        orig = original_modules[name]
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig

    # Pop any newly imported photo_selector_toolbox modules imported during mock session to prevent pollution
    to_pop = [
        m for m in list(sys.modules.keys())
        if m.startswith("photo_selector_toolbox") and m not in existing_modules
    ]
    for m in to_pop:
        sys.modules.pop(m, None)




@pytest.fixture(autouse=True)
def mock_sharpness_gui_deps():
    class DummyGet:
        def __init__(self, var):
            self.var = var
            self.return_value = None
        def __call__(self):
            if self.return_value is not None:
                return self.return_value
            return self.var._val

    class DummyVar:
        def __init__(self, value=None):
            self._val = value
            self.get = DummyGet(self)
        def set(self, val):
            self._val = val

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Tk"),
        patch(
            "photo_selector_toolbox.gui.sharpness_tool.tk.StringVar",
            side_effect=lambda value=None: DummyVar(value),
        ),
        patch(
            "photo_selector_toolbox.gui.sharpness_tool.tk.IntVar",
            side_effect=lambda value=None: DummyVar(value),
        ),
        patch(
            "photo_selector_toolbox.gui.sharpness_tool.tk.DoubleVar",
            side_effect=lambda value=None: DummyVar(value),
        ),
        patch(
            "photo_selector_toolbox.gui.sharpness_tool.tk.BooleanVar",
            side_effect=lambda value=None: DummyVar(value),
        ),
        patch("photo_selector_toolbox.gui.sharpness_tool.ttk.Frame"),
        patch("photo_selector_toolbox.gui.sharpness_tool.ttk.LabelFrame"),
        patch("photo_selector_toolbox.gui.sharpness_tool.ttk.Label"),
        patch("photo_selector_toolbox.gui.sharpness_tool.ttk.Button"),
        patch("photo_selector_toolbox.gui.sharpness_tool.ttk.Notebook"),
        patch("photo_selector_toolbox.gui.sharpness_tool.ttk.Treeview"),
        patch("photo_selector_toolbox.gui.sharpness_tool.ttk.Scrollbar"),
        patch("photo_selector_toolbox.gui.sharpness_tool.ImageTk.PhotoImage"),
        patch("photo_selector_toolbox.gui.controllers.ImageCacheManager"),
    ):
        yield



def test_is_grouping_enabled_error():
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool

    parent = MagicMock()
    parent.register = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.setup_ui"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.setup_focus_ui"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
    ):
        tool = SharpnessTool(parent)

        # Scenario 1: group_similar_var is missing
        if hasattr(tool, "group_similar_var"):
            delattr(tool, "group_similar_var")
        assert tool._is_grouping_enabled() is False

        # Scenario 2: group_similar_var is None
        tool.group_similar_var = None
        assert tool._is_grouping_enabled() is False

        # Scenario 3: Exception in get()
        mock_var = MagicMock()
        # Ensure the mock object's class name doesn't match 'MagicMock' or 'Mock'
        # so it bypasses the type check in _is_grouping_enabled.
        # Actually, if get() raises an exception, the type check won't matter.
        mock_var.get.side_effect = Exception("Test Exception")
        tool.group_similar_var = mock_var
        assert tool._is_grouping_enabled() is False


def test_sharpness_tool_init():
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool

    parent = MagicMock()

    # Needs to mock out parent methods used in __init__
    parent.register = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.setup_ui"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.setup_focus_ui"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
    ):
        tool = SharpnessTool(parent)
        assert not tool.is_scanning
        assert tool.candidates == []
        assert tool.sorted_files == []


def test_sharpness_tool_filtering():
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool

    parent = MagicMock()
    parent.register = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
    ):
        tool = SharpnessTool(parent)
        tool.config = MagicMock()
        tool.update = MagicMock()
        tool.folder_var.get.return_value = "/mock/folder"

        walk_return = [("/mock/folder", [], ["img1.jpg", "img2.arw", "img3.jpg", "img4.png"])]
        with patch("os.walk", return_value=walk_return):
            with patch("photo_selector_toolbox.exif.reader.SUPPORTED_EXTENSIONS", {".jpg", ".arw", ".png"}):
                tool._load_folder_contents("/mock/folder")

                # Check sorted_files and candidates initially contain everything
                assert len(tool.sorted_files) == 4
                assert len(tool.candidates) == 4

                # Mock file_type_var.get to return ".JPG"
                tool.file_type_var.get.return_value = ".JPG"
                tool.on_file_type_change()

                assert len(tool.candidates) == 2
                assert all(f.suffix.upper() == ".JPG" for f in tool.candidates)

                # Test resetting to All
                tool.file_type_var.get.return_value = "All Supported"
                tool.on_file_type_change()

                assert len(tool.candidates) == 4


def test_update_scan_button_state_no_recreation():
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool

    parent = MagicMock()
    parent.register = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
    ):
        tool = SharpnessTool(parent)
        # Verify that setup_review_ui created preview_area
        assert hasattr(tool, "preview_area")

        # Save reference of preview_area
        initial_preview_area = tool.preview_area

        # Call update_scan_button_state multiple times
        tool.update_scan_button_state()
        tool.is_scanning = True
        tool.update_scan_button_state()
        tool.is_scanning = False
        tool.update_scan_button_state()

        # Verify preview_area is still the same object and not recreated
        assert tool.preview_area is initial_preview_area


def test_get_candidate_listbox_text():
    import sys
    from unittest.mock import patch, MagicMock
    from pathlib import Path

    # Temporarily restore real models module to construct ScanResult properly
    orig_models = original_modules.get("photo_selector_toolbox.core.models")
    mock_models = sys.modules.get("photo_selector_toolbox.core.models")

    if orig_models:
        sys.modules["photo_selector_toolbox.core.models"] = orig_models
    else:
        sys.modules.pop("photo_selector_toolbox.core.models", None)

    try:
        import photo_selector_toolbox.gui.sharpness_tool as sg
        from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool
        from photo_selector_toolbox.core.models import ScanResult

        # Override format_score in the sharpness_gui module namespace
        original_format_score = sg.format_score
        sg.format_score = lambda val, **kwargs: (
            "N/A" if val is None or val == "N/A" else (f"{val:.1f}" if isinstance(val, float) else str(val))
        )

        parent = MagicMock()
        parent.register = MagicMock()

        try:
            with (
                patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
                patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
            ):
                tool = SharpnessTool(parent)
                path = Path("/mock/folder/img1.jpg")

                # Test case 1: No scan result (or all scores are N/A)
                tool.files_map[path] = ScanResult(path=path)
                assert tool._get_candidate_listbox_text(path, {}) == "img1.jpg"

                # Test case 2: Sharpness calculated, others not
                tool.files_map[path] = ScanResult(path=path, score=42.5)
                assert tool._get_candidate_listbox_text(path, {}) == "img1.jpg (42.5)"

                # Test case 3: Sharpness and Noise calculated
                tool.files_map[path] = ScanResult(path=path, score=42.5, noise_score=1.2)
                assert tool._get_candidate_listbox_text(path, {}) == "img1.jpg (42.5, 1.2)"

                # Test case 4: Sharpness, Noise, and Highlight/Shadow clipping calculated
                res = ScanResult(path=path, score=42.5, noise_score=1.2)
                res.scores["highlight_clipping"] = 0.5
                res.scores["shadow_clipping"] = 1.0
                tool.files_map[path] = res
                assert tool._get_candidate_listbox_text(path, {}) == "img1.jpg (42.5, 1.2, 0.5%, 1.0%)"
        finally:
            sg.format_score = original_format_score
    finally:
        # Re-mock models
        if mock_models:
            sys.modules["photo_selector_toolbox.core.models"] = mock_models
        else:
            sys.modules.pop("photo_selector_toolbox.core.models", None)


def test_update_metadata_label_loads_exif():
    import sys
    from unittest.mock import patch, MagicMock
    from pathlib import Path

    # Temporarily restore real models, reader, and formatting modules to test properly
    orig_models = original_modules.get("photo_selector_toolbox.core.models")
    mock_models = sys.modules.get("photo_selector_toolbox.core.models")
    orig_reader = original_modules.get("photo_selector_toolbox.exif.reader")
    mock_reader = sys.modules.get("photo_selector_toolbox.exif.reader")
    orig_formatting = original_modules.get("photo_selector_toolbox.core.formatting")
    mock_formatting = sys.modules.get("photo_selector_toolbox.core.formatting")

    if orig_models:
        sys.modules["photo_selector_toolbox.core.models"] = orig_models
    else:
        sys.modules.pop("photo_selector_toolbox.core.models", None)

    if orig_reader:
        sys.modules["photo_selector_toolbox.exif.reader"] = orig_reader
    else:
        sys.modules.pop("photo_selector_toolbox.exif.reader", None)

    if orig_formatting:
        sys.modules["photo_selector_toolbox.core.formatting"] = orig_formatting
    else:
        sys.modules.pop("photo_selector_toolbox.core.formatting", None)

    try:
        from photo_selector_toolbox.core.formatting import format_score, format_meta
        import photo_selector_toolbox.gui.sharpness_tool as sg
        from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool
        from photo_selector_toolbox.core.models import ScanResult, ExifData

        # Save original formatters and inject real ones
        orig_sg_format_score = sg.format_score
        orig_sg_format_meta = sg.format_meta
        sg.format_score = format_score
        sg.format_meta = format_meta

        parent = MagicMock()
        parent.register = MagicMock()

        try:
            with (
                patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
                patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
                patch("photo_selector_toolbox.gui.sharpness_tool.get_exif_data") as mock_get_exif,
            ):
                tool = SharpnessTool(parent)
                tool.meta_lbl = MagicMock()

                path = Path("/mock/folder/img1.jpg")
                res = ScanResult(path=path)
                tool.files_map[path] = res

                # Mock get_exif_data to return a valid ExifData
                mock_exif = ExifData(iso=100.0, shutter_speed=0.005, aperture=2.8, focal_length=50.0)
                mock_get_exif.return_value = mock_exif

                tool.update_metadata_label(path)

                # Verify get_exif_data was called and res.exif was populated
                mock_get_exif.assert_called_once_with(path)
                assert res.exif == mock_exif

                # Verify meta_lbl.config was called with formatted string
                tool.meta_lbl.config.assert_called_once()
                call_args = tool.meta_lbl.config.call_args[1]
                assert "ISO: 100" in call_args["text"]
                assert "1/200s" in call_args["text"]
                assert "f/2.8" in call_args["text"]
                assert "50mm" in call_args["text"]
        finally:
            sg.format_score = orig_sg_format_score
            sg.format_meta = orig_sg_format_meta
    finally:
        if mock_models:
            sys.modules["photo_selector_toolbox.core.models"] = mock_models
        else:
            sys.modules.pop("photo_selector_toolbox.core.models", None)

        if mock_reader:
            sys.modules["photo_selector_toolbox.exif.reader"] = mock_reader
        else:
            sys.modules.pop("photo_selector_toolbox.exif.reader", None)

        if mock_formatting:
            sys.modules["photo_selector_toolbox.core.formatting"] = mock_formatting
        else:
            sys.modules.pop("photo_selector_toolbox.core.formatting", None)

def test_mac_metadata_ignored():
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool
    parent = MagicMock()
    parent.register = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
    ):
        tool = SharpnessTool(parent)
        tool.config = MagicMock()
        tool.update = MagicMock()
        tool.folder_var.get.return_value = "/mock/folder"

        walk_return = [("/mock/folder", [], ["img1.jpg", "._img1.jpg", "img2.arw", "._img2.arw"])]
        with patch("os.walk", return_value=walk_return):
            with patch("photo_selector_toolbox.exif.reader.SUPPORTED_EXTENSIONS", {".jpg", ".arw"}):
                tool._load_folder_contents("/mock/folder")

                # Check sorted_files and candidates ignore dot_underscore
                assert len(tool.sorted_files) == 2
                assert len(tool.candidates) == 2
                filenames = {f.name for f in tool.candidates}
                assert filenames == {"img1.jpg", "img2.arw"}


def test_throttled_listbox_updates():
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool
    from pathlib import Path

    parent = MagicMock()
    parent.register = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
    ):
        tool = SharpnessTool(parent)
        tool.parent = MagicMock()
        tool.candidate_listbox = MagicMock()
        tool.candidates = [Path("img1.jpg"), Path("img2.jpg")]
        tool._get_candidate_listbox_text = MagicMock(return_value="mock_text")
        tool._get_group_info_map = MagicMock(return_value={})

        # Test that calling update buffers the path and schedules flush only once
        path1 = Path("img1.jpg")
        path2 = Path("img2.jpg")

        res1 = MagicMock()
        res1.path = path1
        res2 = MagicMock()
        res2.path = path2

        tool._update_candidate_listbox_ui(res1)
        tool._update_candidate_listbox_ui(res2)

        assert path1 in tool.pending_listbox_updates
        assert path2 in tool.pending_listbox_updates
        assert len(tool.pending_listbox_updates) == 2
        assert tool.listbox_update_loop_active is True

        # parent.after should have been called exactly once to schedule the loop
        tool.parent.after.assert_called_once_with(250, tool._flush_listbox_updates)

        # Now mock the listbox calls
        tool.candidate_listbox.curselection.return_value = ()

        # Call flush
        tool._flush_listbox_updates()

        # The pending updates should be processed and cleared
        assert len(tool.pending_listbox_updates) == 0
        assert tool.candidate_listbox.delete.call_count == 2
        assert tool.candidate_listbox.insert.call_count == 2


def test_sorting_flat_list():
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool
    from photo_selector_toolbox.core.models import ScanResult
    from pathlib import Path

    parent = MagicMock()
    parent.register = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
    ):
        tool = SharpnessTool(parent)
        tool.candidate_listbox = MagicMock()
        tool.folder_var = MagicMock()
        tool.folder_var.get.return_value = "/mock"

        path1 = Path("img1.jpg")
        path2 = Path("img2.jpg")
        path3 = Path("img3.jpg")

        tool.sorted_files = [path1, path2, path3]
        tool.files_map = {
            path1: ScanResult(path=path1, score=150.0),
            path2: ScanResult(path=path2, score=500.0),
            path3: ScanResult(path=path3, score=300.0),
        }

        # Test Descending order (default for Sharpness Score)
        tool.sort_by_var.set("Sharpness Score")
        tool.sort_order_var.set("Descending")
        tool.apply_grouping_and_refresh()

        # Should be sorted: path2 (500.0), path3 (300.0), path1 (150.0)
        assert tool.candidates == [path2, path3, path1]

        # Test Ascending order
        tool.sort_order_var.set("Ascending")
        tool.apply_grouping_and_refresh()

        # Should be sorted: path1 (150.0), path3 (300.0), path2 (500.0)
        assert tool.candidates == [path1, path3, path2]


def test_sorting_na_scores():
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool
    from photo_selector_toolbox.core.models import ScanResult
    from pathlib import Path

    parent = MagicMock()
    parent.register = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
    ):
        tool = SharpnessTool(parent)
        tool.candidate_listbox = MagicMock()
        tool.folder_var = MagicMock()
        tool.folder_var.get.return_value = "/mock"

        path1 = Path("img1.jpg")
        path2 = Path("img2.jpg")
        path3 = Path("img3.jpg")

        tool.sorted_files = [path1, path2, path3]
        tool.files_map = {
            path1: ScanResult(path=path1, score="N/A"),
            path2: ScanResult(path=path2, score=500.0),
            path3: ScanResult(path=path3, score=300.0),
        }

        # Test Descending order - N/A should go to the end
        tool.sort_by_var.set("Sharpness Score")
        tool.sort_order_var.set("Descending")
        tool.apply_grouping_and_refresh()

        # Should be: path2 (500.0), path3 (300.0), path1 (N/A)
        assert tool.candidates == [path2, path3, path1]

        # Test Ascending order - N/A should still go to the end
        tool.sort_order_var.set("Ascending")
        tool.apply_grouping_and_refresh()

        # Should be: path3 (300.0), path2 (500.0), path1 (N/A)
        assert tool.candidates == [path3, path2, path1]


def test_sorting_grouped_list():
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool
    from photo_selector_toolbox.core.models import ScanResult
    from pathlib import Path

    parent = MagicMock()
    parent.register = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
        patch("photo_selector_toolbox.gui.sharpness_tool.group_files_by_similarity") as mock_group,
    ):
        tool = SharpnessTool(parent)
        tool.candidate_listbox = MagicMock()
        tool.group_similar_var.set(True)

        path1 = Path("img1.jpg")
        path2 = Path("img2.jpg")
        path3 = Path("img3.jpg")
        path4 = Path("img4.jpg")

        tool.sorted_files = [path1, path2, path3, path4]
        tool.files_map = {
            path1: ScanResult(path=path1, score=100.0), # Group A
            path2: ScanResult(path=path2, score=400.0), # Group A
            path3: ScanResult(path=path3, score=500.0), # Group B
            path4: ScanResult(path=path4, score=200.0), # Group B
        }

        # Group A has path1 & path2
        # Group B has path3 & path4
        mock_group.return_value = [[path1, path2], [path3, path4]]

        # Sort by Sharpness Score, Descending
        tool.sort_by_var.set("Sharpness Score")
        tool.sort_order_var.set("Descending")

        tool.apply_grouping_and_refresh()

        # 1. Group A internally: path2 (400.0) first, path1 (100.0) second. Rep is path2.
        # 2. Group B internally: path3 (500.0) first, path4 (200.0) second. Rep is path3.
        # 3. Sort groups themselves: Group B (rep 500.0) before Group A (rep 400.0).
        # Since not expanded, candidates should just be the representatives of the sorted groups: path3, path2.
        assert tool.candidates == [path3, path2]

        # Let's expand both groups to check internal sorting
        tool.image_groups[0].expanded = True # Group B
        tool.image_groups[1].expanded = True # Group A
        tool.apply_grouping_and_refresh()

        # Candidates should be:
        # Group B: rep (path3), followed by other member (path4)
        # Group A: rep (path2), followed by other member (path1)
        assert tool.candidates == [path3, path4, path2, path1]










def test_cancel_scan():
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool

    parent = MagicMock()
    parent.register = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.setup_ui"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.setup_focus_ui"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
    ):
        tool = SharpnessTool(parent)

        # Mock dependencies
        tool.scan_controller = MagicMock()
        tool.log = MagicMock()

        # Action
        tool.cancel_scan()

        # Assertions
        tool.scan_controller.cancel.assert_called_once()
        tool.log.assert_called_once_with("Stopping scan...")


def _make_tool():
    """Construct a SharpnessTool with the GUI setup patched out."""
    from photo_selector_toolbox.gui.sharpness_tool import SharpnessTool

    parent = MagicMock()
    parent.register = MagicMock()
    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.tk.Toplevel"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.setup_ui"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.setup_focus_ui"),
        patch("photo_selector_toolbox.gui.sharpness_tool.SharpnessTool.bind_all"),
    ):
        return SharpnessTool(parent)


def _group_fixture(tool):
    """Set up candidates/groups: expanded A[a1,a2,a3], collapsed B[b1,b2], single C[c1]."""
    from pathlib import Path
    from photo_selector_toolbox.gui.sharpness_tool import ImageGroup

    a1, a2, a3, b1, c1 = (Path(p) for p in ["a1", "a2", "a3", "b1", "c1"])
    tool.group_similar_var.set(True)  # enable grouping
    tool.candidates = [a1, a2, a3, b1, c1]
    tool.image_groups = [
        ImageGroup(representative=a1, files=[a1, a2, a3], expanded=True),
        ImageGroup(representative=b1, files=[b1, Path("b2")], expanded=False),
        ImageGroup(representative=c1, files=[c1], expanded=False),
    ]
    return a1, a2, a3, b1, c1


def test_current_group_bounds_confines_to_expanded_group():
    tool = _make_tool()
    _group_fixture(tool)

    # Inside the expanded group A -> contiguous block (0, 2).
    assert tool._current_group_bounds(0) == (0, 2)
    assert tool._current_group_bounds(1) == (0, 2)
    assert tool._current_group_bounds(2) == (0, 2)
    # Collapsed group B representative and single C fall back to flat nav.
    assert tool._current_group_bounds(3) is None
    assert tool._current_group_bounds(4) is None

    # With grouping disabled, everything is flat.
    tool.group_similar_var.set(False)
    assert tool._current_group_bounds(0) is None


def test_group_limited_nav_index_stops_at_group_boundaries():
    tool = _make_tool()
    _group_fixture(tool)
    tool.candidate_listbox = MagicMock()

    # From a1 (idx 0): next -> a2 (1); prev -> None (group start).
    tool.candidate_listbox.curselection.return_value = (0,)
    assert tool._group_limited_nav_index(1) == 1
    assert tool._group_limited_nav_index(-1) is None

    # From a3 (idx 2, group end): next -> None; prev -> a2 (1).
    tool.candidate_listbox.curselection.return_value = (2,)
    assert tool._group_limited_nav_index(1) is None
    assert tool._group_limited_nav_index(-1) == 1

    # From collapsed B representative (idx 3): flat nav across groups.
    tool.candidate_listbox.curselection.return_value = (3,)
    assert tool._group_limited_nav_index(1) == 4
    assert tool._group_limited_nav_index(-1) == 2


def test_scan_requested_during_grouping_is_queued_then_started():
    tool = _make_tool()
    tool.log = MagicMock()
    tool.update_scan_button_state = MagicMock()
    tool.folder_var.set("/mock/folder")

    # Grouping in progress: start_scan should queue rather than run.
    tool.is_grouping = True
    with patch("photo_selector_toolbox.gui.sharpness_tool.Path.exists", return_value=True):
        tool.start_scan()
    assert tool._pending_scan is True

    # When grouping completes, the queued scan is started automatically.
    tool.is_grouping = False
    started = []
    tool.start_scan = lambda: started.append(True)
    tool._start_pending_scan_if_any()
    assert started == [True]
    assert tool._pending_scan is False


def test_cancel_pending_scan_clears_queue():
    tool = _make_tool()
    tool.log = MagicMock()
    tool.update_scan_button_state = MagicMock()
    tool._pending_scan = True

    tool.cancel_pending_scan()
    assert tool._pending_scan is False


# ── Grouping requested while a scan is running (mirror of the above) ──


def _prepare_grouping_widgets(tool):
    for name in [
        "group_level_combo", "group_similar_chk", "group_progress_frame",
        "group_status_lbl", "candidate_listbox", "review_status_lbl",
    ]:
        setattr(tool, name, MagicMock())
    tool.group_progress_var = MagicMock()
    tool.log = MagicMock()
    tool.update_scan_button_state = MagicMock()
    tool.apply_grouping_and_refresh = MagicMock()


def test_grouping_change_during_scan_is_queued_not_dropped():
    tool = _make_tool()
    _prepare_grouping_widgets(tool)
    tool.is_scanning = True
    tool.group_similar_var.set(True)

    tool.on_group_similar_change()

    assert tool._pending_grouping is True
    # The heavy work must not have run while the scan is in flight.
    tool.apply_grouping_and_refresh.assert_not_called()
    tool.group_progress_frame.pack.assert_called()


def test_queued_grouping_is_applied_when_scan_finishes():
    tool = _make_tool()
    _prepare_grouping_widgets(tool)
    tool._pending_grouping = True

    applied = []
    tool.on_group_similar_change = lambda: applied.append(True)
    tool._apply_pending_grouping_if_any()

    assert applied == [True]
    assert tool._pending_grouping is False
    tool.group_progress_frame.pack_forget.assert_called()


def test_scan_finished_applies_queued_grouping():
    tool = _make_tool()
    _prepare_grouping_widgets(tool)
    tool.candidates = []
    tool.is_scanning = True
    tool._pending_grouping = True
    tool.switch_to_review_mode = MagicMock()
    tool.candidate_listbox.curselection.return_value = ()

    applied = []
    tool.on_group_similar_change = lambda: applied.append(True)

    with patch("photo_selector_toolbox.gui.sharpness_tool.messagebox.showinfo"):
        tool.notebook = MagicMock()
        tool.scan_finished()

    assert applied == [True]
    assert tool.is_scanning is False


def test_start_scan_leaves_grouping_controls_enabled():
    tool = _make_tool()
    _prepare_grouping_widgets(tool)
    tool.folder_var.set("/mock/folder")
    tool.group_similar_var.set(True)
    tool.scan_controller = MagicMock()
    tool.cache_manager = MagicMock()
    tool.log_text = MagicMock()
    tool.progress_var = MagicMock()
    tool.review_progress_var = MagicMock()
    tool.switch_to_review_mode = MagicMock()
    tool.after = MagicMock()
    tool.grid_size_var.set("4x4")

    with patch("photo_selector_toolbox.gui.sharpness_tool.Path.exists", return_value=True):
        tool.start_scan()

    # The checkbox must never be disabled — clicking it during a scan queues.
    disabled_calls = [
        c for c in tool.group_similar_chk.state.call_args_list
        if c.args and "disabled" in c.args[0]
    ]
    assert disabled_calls == []


def test_cancel_grouping_drops_a_queued_change_and_reverts_controls():
    tool = _make_tool()
    _prepare_grouping_widgets(tool)
    tool._pending_grouping = True
    tool._last_applied_group_similar = False
    tool._last_applied_group_level = "Time & Filename"
    tool.group_similar_var.set(True)

    tool.cancel_grouping()

    assert tool._pending_grouping is False
    assert tool.group_similar_var.get() is False
    tool.group_progress_frame.pack_forget.assert_called()


def _attach_focus_labels(tool):
    """Attach the focus-mode overlay labels the metadata writer updates."""
    for name in [
        "meta_lbl", "focus_score_lbl", "focus_noise_lbl", "focus_hl_lbl",
        "focus_sd_lbl", "focus_cat_lbl", "focus_filename_lbl", "focus_meta_lbl",
        "focus_aesthetic_lbl",
    ]:
        setattr(tool, name, MagicMock())


def test_focus_mode_shows_aesthetic_score_when_present():
    from pathlib import Path

    tool = _make_tool()
    _attach_focus_labels(tool)

    res = MagicMock()
    res.score = 7.0
    res.noise_score = "N/A"
    res.scores = {
        "aesthetic": 7.5,
        "aesthetic_analysis": "Great Lighting",
        "highlight_clipping": "N/A",
        "shadow_clipping": "N/A",
    }

    tool._set_metadata_labels(Path("a1.jpg"), None, res)

    # The focus-mode aesthetic label is populated and shown.
    assert tool.focus_aesthetic_lbl.config.called
    text = tool.focus_aesthetic_lbl.config.call_args.kwargs.get("text", "")
    assert "Aesthetic Score" in text
    assert tool.focus_aesthetic_lbl.pack.called


def test_focus_mode_hides_aesthetic_score_when_absent():
    from pathlib import Path

    tool = _make_tool()
    _attach_focus_labels(tool)

    res = MagicMock()
    res.score = 7.0
    res.noise_score = "N/A"
    res.scores = {"highlight_clipping": "N/A", "shadow_clipping": "N/A"}

    tool._set_metadata_labels(Path("a1.jpg"), None, res)

    # No aesthetic value -> the label is hidden (pack_forget), never packed.
    assert tool.focus_aesthetic_lbl.pack_forget.called
    assert not tool.focus_aesthetic_lbl.pack.called


def test_load_folder_contents_immediate_display(tmp_path):
    from unittest.mock import MagicMock, patch

    # Create dummy images
    img1 = tmp_path / "img1.jpg"
    img2 = tmp_path / "img2.jpg"
    img1.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
    img2.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    tool = _make_tool()
    tool.candidate_listbox = MagicMock()
    tool.switch_to_review_mode = MagicMock()
    tool.on_candidate_select = MagicMock()
    tool._preload_all_metadata_and_dhashes = MagicMock()

    with (
        patch("photo_selector_toolbox.gui.sharpness_tool.ScoreCache"),
        patch("photo_selector_toolbox.exif.reader.SUPPORTED_EXTENSIONS", {".jpg"}),
    ):
        tool._load_folder_contents(str(tmp_path))

    assert len(tool.candidates) == 2
    assert tool.switch_to_review_mode.called
    assert tool.candidate_listbox.selection_set.called


def test_refresh_folder(tmp_path):
    tool = _make_tool()
    tool.folder_var = MagicMock()
    tool.folder_var.get.return_value = str(tmp_path)
    tool._load_folder_contents = MagicMock()

    tool.refresh_folder()
    tool._load_folder_contents.assert_called_once_with(str(tmp_path))


def test_modern_metadata_card_badges():
    from pathlib import Path
    from unittest.mock import MagicMock, patch
    from photo_selector_toolbox.core.models import ScanResult

    tool = _make_tool()
    tool.meta_lbl = MagicMock()
    tool.meta_file_lbl = MagicMock()
    tool.meta_expo_lbl = MagicMock()
    tool.meta_chips_frame = MagicMock()
    tool.meta_chips_frame.winfo_children.return_value = []

    p = Path("test_shot.jpg")
    res = ScanResult(path=p)
    res.scores = {
        "sharpness": 8.4,
        "noise": 2.1,
        "highlight_clipping": "N/A",
        "shadow_clipping": 4.5,
        "aesthetic": 7.8,
    }
    tool.files_map = {p: res}

    with patch("photo_selector_toolbox.gui.sharpness_tool.ttk.Label") as mock_label:
        tool.update_metadata_label(p)
        assert tool.meta_file_lbl.config.called
        assert tool.meta_expo_lbl.config.called
        # Check that badges were constructed for the valid metrics (sharpness, noise, shadow, aesthetic)
        badge_texts = [call.kwargs.get("text", "") for call in mock_label.call_args_list]
        assert any("Sharpness" in t for t in badge_texts)
        assert any("Noise" in t for t in badge_texts)
        assert any("Shadow" in t for t in badge_texts)
        assert any("AI" in t for t in badge_texts)
        # Highlight is N/A, so no Highlight badge should be constructed
        assert not any("High" in t for t in badge_texts)

