"""Tests for the aesthetic scoring settings dialog.

The dialog's whole reason to exist is that ``auto`` could silently degrade to
the slowest engine, so the important assertions here are behavioural: whatever
``tools.aesthetic.select_engine`` decides for a given set of availability
flags is what the dialog must announce. The exact sentences are free to change;
the agreement is not.
"""

import json
import tkinter as tk
from itertools import product
from unittest.mock import patch

import pytest

from photo_selector_toolbox.core import config as config_mod
from photo_selector_toolbox.gui import aesthetic_settings as mod
from photo_selector_toolbox.gui.aesthetic_settings import (
    AestheticSettingsDialog,
    ENGINE_LABELS,
    ENGINE_OPTIONS,
    LEVEL_ERROR,
    LEVEL_OK,
    LEVEL_WARN,
    describe_engine_status,
    probe_ollama,
)
from photo_selector_toolbox.tools.aesthetic import (
    ENGINE_APPLE_VISION,
    ENGINE_AUTO,
    ENGINE_NIMA_ONNX,
    ENGINE_OLLAMA,
    select_engine,
)

ALL_ENGINES = (ENGINE_AUTO, ENGINE_APPLE_VISION, ENGINE_NIMA_ONNX, ENGINE_OLLAMA)
FLAGS = (True, False)


@pytest.fixture
def temp_config(tmp_path):
    """Point the config module at a throwaway settings.json."""
    with patch.object(config_mod, "CONFIG_DIR", tmp_path), \
         patch.object(config_mod, "CONFIG_FILE", tmp_path / "settings.json"):
        yield tmp_path / "settings.json"


def _read(settings_file):
    return json.loads(settings_file.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# describe_engine_status — the regression guard for the silent fallback
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "requested,apple_ok,onnx_ok,model_exists",
    list(product(ALL_ENGINES, FLAGS, FLAGS, FLAGS)),
)
def test_status_engine_always_matches_the_selector(requested, apple_ok, onnx_ok, model_exists):
    """What the dialog announces is what the scan will actually run."""
    config = {"aesthetic_engine": requested, "nima_model_path": "/models/nima.onnx"}
    expected = select_engine(
        config, apple_ok=apple_ok, onnx_ok=onnx_ok, nima_model_exists=model_exists
    )

    status = describe_engine_status(
        config, apple_ok=apple_ok, onnx_ok=onnx_ok, nima_model_exists=model_exists
    )

    assert status.engine == expected
    # The headline names the engine that will run, and no other engine.
    assert ENGINE_LABELS[expected] in status.headline
    for engine, label in ENGINE_LABELS.items():
        if engine != expected:
            assert label not in status.headline
    assert status.reason  # the selector's own explanation is carried through


def test_auto_falling_back_to_ollama_is_flagged_not_silent():
    """The measured defect: auto lands on the slow engine with nothing said."""
    config = {"aesthetic_engine": ENGINE_AUTO, "nima_model_path": ""}

    status = describe_engine_status(
        config, apple_ok=False, onnx_ok=False, nima_model_exists=False
    )

    assert status.engine == ENGINE_OLLAMA
    assert status.level == LEVEL_WARN
    assert status.runnable is True
    # The fallback is presented as a fallback, with a way out.
    assert "automatically" in status.headline
    assert "nima" in status.detail.lower() or "NIMA" in status.detail


def test_auto_prefers_apple_vision_and_says_so_positively():
    config = {"aesthetic_engine": ENGINE_AUTO, "nima_model_path": ""}

    status = describe_engine_status(
        config, apple_ok=True, onnx_ok=False, nima_model_exists=False
    )

    assert status.engine == ENGINE_APPLE_VISION
    assert status.level == LEVEL_OK
    assert status.runnable is True


def test_explicit_apple_vision_without_support_is_reported_as_unrunnable():
    config = {"aesthetic_engine": ENGINE_APPLE_VISION, "nima_model_path": ""}

    status = describe_engine_status(
        config, apple_ok=False, onnx_ok=True, nima_model_exists=True
    )

    assert status.engine == ENGINE_APPLE_VISION
    assert status.level == LEVEL_ERROR
    assert status.runnable is False
    assert "macOS 15" in status.detail  # the remedy is stated


def test_explicit_nima_without_a_model_is_reported_as_unrunnable():
    config = {"aesthetic_engine": ENGINE_NIMA_ONNX, "nima_model_path": ""}

    status = describe_engine_status(
        config, apple_ok=True, onnx_ok=True, nima_model_exists=False
    )

    assert status.engine == ENGINE_NIMA_ONNX
    assert status.level == LEVEL_ERROR
    assert status.runnable is False


def test_explicit_nima_without_onnxruntime_is_reported_as_unrunnable():
    config = {"aesthetic_engine": ENGINE_NIMA_ONNX, "nima_model_path": "/models/nima.onnx"}

    status = describe_engine_status(
        config, apple_ok=True, onnx_ok=False, nima_model_exists=True
    )

    assert status.engine == ENGINE_NIMA_ONNX
    assert status.level == LEVEL_ERROR
    assert status.runnable is False


def test_explicit_nima_with_model_and_runtime_is_ready():
    config = {"aesthetic_engine": ENGINE_NIMA_ONNX, "nima_model_path": "/models/nima.onnx"}

    status = describe_engine_status(
        config, apple_ok=True, onnx_ok=True, nima_model_exists=True
    )

    assert status.level == LEVEL_OK
    assert status.runnable is True


def test_unknown_engine_value_is_described_as_automatic():
    config = {"aesthetic_engine": "banana", "nima_model_path": ""}

    status = describe_engine_status(
        config, apple_ok=True, onnx_ok=False, nima_model_exists=False
    )

    assert status.engine == ENGINE_APPLE_VISION
    assert "automatically" in status.headline


def test_status_probes_the_machine_when_no_flags_are_injected(tmp_path):
    model = tmp_path / "nima.onnx"
    model.write_bytes(b"not-a-real-model")
    config = {"aesthetic_engine": ENGINE_AUTO, "nima_model_path": str(model)}

    with patch.object(mod, "apple_vision_available", return_value=False), \
         patch.object(mod, "onnxruntime_available", return_value=True):
        status = describe_engine_status(config)

    assert status.engine == ENGINE_NIMA_ONNX
    assert status.level == LEVEL_OK


def test_every_engine_option_is_offered_exactly_once():
    offered = [opt.engine for opt in ENGINE_OPTIONS]
    assert offered == list(ALL_ENGINES)
    assert all(opt.blurb for opt in ENGINE_OPTIONS)


# --------------------------------------------------------------------------- #
# probe_ollama
# --------------------------------------------------------------------------- #

def test_probe_ollama_reports_success_for_a_pulled_model():
    with patch.object(mod, "_fetch_ollama_models", return_value=["llava:7b"]):
        message, level = probe_ollama("http://localhost:11434", "llava")
    assert level == LEVEL_OK
    assert "llava" in message


def test_probe_ollama_reports_a_missing_model_with_the_pull_command():
    with patch.object(mod, "_fetch_ollama_models", return_value=["mistral:latest"]):
        message, level = probe_ollama("http://localhost:11434", "llava")
    assert level == LEVEL_WARN
    assert "ollama pull llava" in message


@pytest.mark.parametrize(
    "candidate,forbidden",
    [
        ("169.254.169.254", True),          # cloud metadata
        ("::ffff:169.254.169.254", True),   # IPv4-mapped IPv6 bypass
        ("::ffff:0.0.0.0", True),
        ("0.0.0.0", True),
        ("127.0.0.1", False),
        ("192.168.1.10", False),
        ("localhost", False),               # not an IP literal
    ],
)
def test_forbidden_ip_check_survived_the_move(candidate, forbidden):
    assert mod._is_forbidden_ip(candidate) is forbidden


def test_fetch_rejects_a_non_http_scheme():
    with pytest.raises(ValueError, match="http"):
        mod._fetch_ollama_models("ftp://localhost:11434")


def test_fetch_rejects_a_metadata_ip_literal():
    with pytest.raises(ValueError, match="SSRF"):
        mod._fetch_ollama_models("http://169.254.169.254")


def test_fetch_rejects_a_hostname_resolving_to_a_metadata_ip():
    resolved = [(2, 1, 6, "", ("169.254.169.254", 0))]
    with patch.object(mod.socket, "getaddrinfo", return_value=resolved):
        with pytest.raises(ValueError, match="SSRF"):
            mod._fetch_ollama_models("http://metadata.example")


def test_fetch_reports_unresolvable_hostnames():
    with patch.object(mod.socket, "getaddrinfo", side_effect=mod.socket.gaierror("nope")):
        with pytest.raises(ValueError, match="resolve"):
            mod._fetch_ollama_models("http://nowhere.example")


def test_probe_ollama_reports_connection_failure():
    with patch.object(mod, "_fetch_ollama_models", side_effect=OSError("refused")):
        message, level = probe_ollama("http://localhost:11434", "llava")
    assert level == LEVEL_ERROR
    assert "refused" in message


# --------------------------------------------------------------------------- #
# The dialog itself
# --------------------------------------------------------------------------- #

@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as e:  # pragma: no cover - no display available
        pytest.skip(f"Tk unavailable: {e}")
    root.geometry("800x600+0+0")
    yield root
    try:
        root.destroy()
    except tk.TclError:  # pragma: no cover
        pass


@pytest.fixture
def dialog(tk_root, temp_config):
    """A dialog whose availability probes are pinned (no macOS/ONNX needed)."""
    with patch.object(mod, "apple_vision_available", return_value=False), \
         patch.object(mod, "onnxruntime_available", return_value=False), \
         patch.object(mod, "apple_vision_unavailable_reason", return_value="not macOS"):
        dlg = AestheticSettingsDialog(tk_root)
    yield dlg
    try:
        if dlg.winfo_exists():
            dlg.destroy()
    except tk.TclError:  # pragma: no cover
        pass


@pytest.mark.parametrize("engine", ALL_ENGINES)
def test_selector_persists_every_engine_value(dialog, temp_config, engine):
    dialog.engine_var.set(engine)
    dialog.save_settings()

    assert _read(temp_config)["aesthetic_engine"] == engine


def test_saving_persists_the_nima_path_and_ollama_fields(dialog, temp_config):
    dialog.engine_var.set(ENGINE_NIMA_ONNX)
    dialog.nima_path_var.set("/models/nima.onnx")
    dialog.url_var.set("http://localhost:11434")
    dialog.model_var.set("llava:7b")
    dialog.prompt_text.delete("1.0", "end")
    dialog.prompt_text.insert("1.0", "Rate this photo.")

    dialog.save_settings()

    saved = _read(temp_config)
    assert saved["nima_model_path"] == "/models/nima.onnx"
    assert saved["ollama_url"] == "http://localhost:11434"
    assert saved["ollama_model"] == "llava:7b"
    assert saved["ollama_prompt"] == "Rate this photo."


def test_saving_does_not_wipe_unrelated_settings(dialog, temp_config):
    stored = config_mod.load_config()
    stored["selection_folder"] = "/photos/Keepers"
    config_mod.save_config(stored)

    dialog.engine_var.set(ENGINE_APPLE_VISION)
    dialog.save_settings()

    assert _read(temp_config)["selection_folder"] == "/photos/Keepers"


def test_dialog_announces_the_engine_the_selector_resolves(dialog):
    dialog.engine_var.set(ENGINE_AUTO)
    dialog._on_engine_changed()

    # Neither Apple Vision nor ONNX Runtime is available in this fixture.
    assert dialog.status.engine == ENGINE_OLLAMA
    assert dialog.status.level == LEVEL_WARN
    assert ENGINE_LABELS[ENGINE_OLLAMA] in dialog.status_headline.cget("text")
    assert dialog.status_detail.cget("text") == dialog.status.detail
    assert dialog.status.reason in dialog.status_reason.cget("text")


def test_choosing_ollama_reveals_the_ollama_fields(dialog):
    dialog.engine_var.set(ENGINE_OLLAMA)
    dialog._on_engine_changed()

    assert dialog.settings_nb.select() == str(dialog.ollama_tab)


def test_choosing_nima_reveals_the_model_path_field(dialog):
    dialog.engine_var.set(ENGINE_NIMA_ONNX)
    dialog._on_engine_changed()

    assert dialog.settings_nb.select() == str(dialog.nima_tab)


def test_choosing_apple_vision_reveals_the_apple_group(dialog):
    dialog.engine_var.set(ENGINE_APPLE_VISION)
    dialog._on_engine_changed()

    assert dialog.settings_nb.select() == str(dialog.apple_tab)


def test_ollama_settings_stay_reachable_from_another_engine(dialog):
    """An existing Ollama user must still be able to reach their prompt."""
    dialog.engine_var.set(ENGINE_APPLE_VISION)
    dialog._on_engine_changed()

    tabs = [dialog.settings_nb.tab(t, "state") for t in dialog.settings_nb.tabs()]
    assert all(state == "normal" for state in tabs)
    assert str(dialog.ollama_tab) in dialog.settings_nb.tabs()


def test_editing_the_model_path_updates_the_status_without_moving_the_tab(dialog, tmp_path):
    dialog.engine_var.set(ENGINE_OLLAMA)
    dialog._on_engine_changed()
    assert dialog.settings_nb.select() == str(dialog.ollama_tab)

    model = tmp_path / "nima.onnx"
    model.write_bytes(b"not-a-real-model")
    dialog.nima_path_var.set(str(model))
    dialog.update_idletasks()

    # Ollama is still the explicit choice, and the user was not thrown onto
    # another tab mid-typing.
    assert dialog.status.engine == ENGINE_OLLAMA
    assert dialog.settings_nb.select() == str(dialog.ollama_tab)


def test_browse_sets_the_model_path(dialog):
    with patch.object(mod.filedialog, "askopenfilename", return_value="/models/picked.onnx"):
        dialog._browse_nima_model()
    assert dialog.nima_path_var.get() == "/models/picked.onnx"


def test_browse_cancelled_leaves_the_model_path_alone(dialog):
    dialog.nima_path_var.set("/models/kept.onnx")
    with patch.object(mod.filedialog, "askopenfilename", return_value=""):
        dialog._browse_nima_model()
    assert dialog.nima_path_var.get() == "/models/kept.onnx"


def test_connection_test_updates_the_label_on_the_main_thread(dialog):
    with patch.object(mod, "probe_ollama", return_value=("all good", LEVEL_OK)):
        dialog._run_connection_test("http://localhost:11434", "llava")
        dialog.update()  # drain the after(0, ...) callback

    assert dialog.ollama_status_lbl.cget("text") == "all good"


def test_escape_dismisses_the_dialog(dialog):
    assert dialog.bind("<Escape>")  # the binding exists at all

    dialog.update()
    dialog.focus_force()
    dialog.event_generate("<Escape>", when="now")
    dialog.update()

    assert not dialog.winfo_exists()


def test_dialog_is_centred_on_its_parent(dialog, tk_root):
    dialog.update_idletasks()
    assert dialog.winfo_reqwidth() > 0
    # Geometry is expressed relative to the parent's root coordinates.
    geometry = dialog.winfo_geometry()
    assert "+" in geometry
