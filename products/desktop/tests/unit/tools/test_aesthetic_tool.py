"""Unit tests for the pure logic of the aesthetic scoring dispatcher.

Native/model-backed engines (Apple Vision, ONNX) are not exercised here — they
require macOS/PyObjC or an ONNX model and are verified on-device. These tests
cover the deterministic pieces: score mapping, distribution reduction, and
engine selection.
"""

import pytest

import types
from unittest.mock import patch

from photo_selector_toolbox.tools.aesthetic import (
    ENGINE_APPLE_VISION,
    ENGINE_NIMA_ONNX,
    ENGINE_OLLAMA,
    apple_vision_available,
    apple_vision_unavailable_reason,
    map_apple_score_to_10,
    nima_distribution_to_score,
    reset_availability_probe_cache,
    select_engine,
    select_engine_with_reason,
)


@pytest.fixture(autouse=True)
def _clear_probe_cache():
    """The import probes are memoised per process; tests patch them."""
    reset_availability_probe_cache()
    yield
    reset_availability_probe_cache()


def test_map_apple_score_endpoints_and_midpoint():
    # Apple documents overallScore in [-1.0, 1.0]; that maps onto [1, 10].
    assert map_apple_score_to_10(-1.0) == 1.0
    assert map_apple_score_to_10(1.0) == 10.0
    assert map_apple_score_to_10(0.0) == 5.5


def test_map_apple_score_is_clamped():
    assert map_apple_score_to_10(-5.0) == 1.0
    assert map_apple_score_to_10(5.0) == 10.0


def test_map_apple_score_is_monotone():
    values = [-1.0, -0.5, -0.042, 0.0, 0.39, 0.565, 0.72, 0.915, 1.0]
    mapped = [map_apple_score_to_10(v) for v in values]
    assert mapped == sorted(mapped)
    assert all(a < b for a, b in zip(mapped, mapped[1:]))


def test_map_apple_score_does_not_pin_realistic_photos_to_ten():
    """Regression guard for the range defect.

    Measured on 84 real JPEGs (macOS 26.6, pyobjc-framework-Vision 12.2.1):
    overallScore ran min -0.042 / median 0.565 / p90 0.720 / max 0.915. Under
    the old [-0.5, 0.5] assumption 59 of the 84 (70%) clamped to exactly 10.0,
    so the score could not rank anything. Over the documented range nothing
    pins and the ordering survives.
    """
    realistic = [0.50, 0.565, 0.62, 0.68, 0.72, 0.80, 0.86, 0.915]
    scores = [map_apple_score_to_10(v) for v in realistic]

    assert len(set(scores)) == len(scores), f"scores collapsed: {scores}"
    assert all(s < 10.0 for s in scores), f"scores pinned at the ceiling: {scores}"


def test_nima_distribution_expected_value():
    # All mass on rating 10 -> score 10; uniform -> 5.5.
    peaked = [0.0] * 9 + [1.0]
    assert nima_distribution_to_score(peaked) == 10.0
    uniform = [0.1] * 10
    assert nima_distribution_to_score(uniform) == 5.5


def test_nima_distribution_normalises_unnormalised_input():
    # Weights need not sum to 1; the mean is still well defined.
    assert nima_distribution_to_score([0, 0, 0, 0, 0, 0, 0, 0, 0, 2]) == 10.0


def test_nima_distribution_rejects_bad_input():
    with pytest.raises(ValueError):
        nima_distribution_to_score([])
    with pytest.raises(ValueError):
        nima_distribution_to_score([0.0, 0.0])


def test_select_engine_honours_explicit_choice():
    assert select_engine({"aesthetic_engine": "ollama"}) == ENGINE_OLLAMA
    assert select_engine({"aesthetic_engine": "apple_vision"}) == ENGINE_APPLE_VISION
    assert select_engine({"aesthetic_engine": "nima_onnx"}) == ENGINE_NIMA_ONNX


def test_select_engine_auto_prefers_apple_vision():
    engine = select_engine(
        {"aesthetic_engine": "auto"},
        apple_ok=True,
        onnx_ok=True,
        nima_model_exists=True,
    )
    assert engine == ENGINE_APPLE_VISION


def test_select_engine_auto_uses_nima_when_no_apple_and_model_present():
    engine = select_engine(
        {"aesthetic_engine": "auto"},
        apple_ok=False,
        onnx_ok=True,
        nima_model_exists=True,
    )
    assert engine == ENGINE_NIMA_ONNX


def test_select_engine_auto_falls_back_to_ollama():
    # No Apple Vision, and no usable NIMA model -> stay on Ollama.
    engine = select_engine(
        {"aesthetic_engine": "auto"},
        apple_ok=False,
        onnx_ok=True,
        nima_model_exists=False,
    )
    assert engine == ENGINE_OLLAMA


def test_select_engine_unknown_value_falls_back_to_auto_resolution():
    engine = select_engine(
        {"aesthetic_engine": "bogus"},
        apple_ok=False,
        onnx_ok=False,
        nima_model_exists=False,
    )
    assert engine == ENGINE_OLLAMA


def test_apple_vision_available_true():
    with patch("photo_selector_toolbox.tools.aesthetic._macos_version_tuple", return_value=(15, 0)):
        mock_vision = types.ModuleType("Vision")
        with patch.dict("sys.modules", {"Vision": mock_vision}):
            assert apple_vision_available() is True

def test_apple_vision_available_false_old_os():
    with patch("photo_selector_toolbox.tools.aesthetic._macos_version_tuple", return_value=(14, 5)):
        assert apple_vision_available() is False

def test_apple_vision_available_false_not_mac():
    with patch("photo_selector_toolbox.tools.aesthetic._macos_version_tuple", return_value=None):
        assert apple_vision_available() is False

def test_apple_vision_available_false_import_error():
    with patch("photo_selector_toolbox.tools.aesthetic._macos_version_tuple", return_value=(15, 0)):
        with patch.dict("sys.modules", {"Vision": None}):
            assert apple_vision_available() is False


def test_import_probe_is_memoised():
    """The probe runs per scored image; it must not re-walk sys.path each time."""
    with patch("photo_selector_toolbox.tools.aesthetic._macos_version_tuple", return_value=(15, 0)):
        with patch(
            "photo_selector_toolbox.tools.aesthetic.importlib.import_module"
        ) as mock_import:
            mock_import.return_value = types.ModuleType("Vision")
            assert apple_vision_available() is True
            assert apple_vision_available() is True
            assert apple_vision_available() is True
            assert mock_import.call_count == 1


# --------------------------------------------------------------------------- #
# Why an engine was chosen — the settings dialog and the logs show this string.
# --------------------------------------------------------------------------- #

def test_reason_for_an_explicit_engine():
    engine, reason = select_engine_with_reason({"aesthetic_engine": "ollama"})
    assert engine == ENGINE_OLLAMA
    assert reason == "explicitly configured as 'ollama'"


def test_reason_for_auto_apple_vision():
    engine, reason = select_engine_with_reason(
        {"aesthetic_engine": "auto"}, apple_ok=True
    )
    assert engine == ENGINE_APPLE_VISION
    assert reason == "auto: apple_vision available"


def test_reason_for_auto_nima():
    engine, reason = select_engine_with_reason(
        {"aesthetic_engine": "auto", "nima_model_path": "/models/nima.onnx"},
        apple_ok=False,
        onnx_ok=True,
        nima_model_exists=True,
    )
    assert engine == ENGINE_NIMA_ONNX
    assert "apple_vision unavailable" in reason
    assert reason.endswith("using nima_onnx")


def test_reason_for_auto_ollama_names_both_missing_engines():
    engine, reason = select_engine_with_reason(
        {"aesthetic_engine": "auto"},
        apple_ok=False,
        onnx_ok=True,
        nima_model_exists=False,
    )
    assert engine == ENGINE_OLLAMA
    assert "apple_vision unavailable" in reason
    assert "nima_onnx unavailable: no model configured" in reason
    assert "falling back to ollama" in reason


def test_reason_for_auto_ollama_without_onnxruntime():
    _, reason = select_engine_with_reason(
        {"aesthetic_engine": "auto"},
        apple_ok=False,
        onnx_ok=False,
        nima_model_exists=False,
    )
    assert "nima_onnx unavailable: onnxruntime not installed" in reason


def test_reason_for_auto_ollama_with_a_missing_model_file():
    _, reason = select_engine_with_reason(
        {"aesthetic_engine": "auto", "nima_model_path": "/nope/nima.onnx"},
        apple_ok=False,
        onnx_ok=True,
        nima_model_exists=False,
    )
    assert "nima_onnx unavailable: model file not found: /nope/nima.onnx" in reason


def test_reason_names_the_missing_pyobjc_bridge():
    """The defect this exists for: the Vision extra is simply not installed."""
    with patch("photo_selector_toolbox.tools.aesthetic._macos_version_tuple", return_value=(26, 6)):
        with patch.dict("sys.modules", {"Vision": None}):
            engine, reason = select_engine_with_reason({"aesthetic_engine": "auto"})

    assert engine == ENGINE_OLLAMA
    assert "pyobjc-framework-Vision not importable" in reason


def test_reason_names_an_old_macos():
    with patch("photo_selector_toolbox.tools.aesthetic._macos_version_tuple", return_value=(14, 5)):
        assert apple_vision_unavailable_reason() == "macOS 14.5 is older than macOS 15"


def test_reason_names_a_non_mac_platform():
    with patch("photo_selector_toolbox.tools.aesthetic._macos_version_tuple", return_value=None):
        assert apple_vision_unavailable_reason() == "not macOS"


def test_reason_for_an_unknown_engine_value():
    engine, reason = select_engine_with_reason(
        {"aesthetic_engine": "bogus"},
        apple_ok=False,
        onnx_ok=False,
        nima_model_exists=False,
    )
    assert engine == ENGINE_OLLAMA
    assert reason.startswith("unknown aesthetic_engine 'bogus', resolved automatically:")


def test_select_engine_still_returns_a_bare_string():
    """The pre-existing single-return API must keep working for its callers."""
    result = select_engine({"aesthetic_engine": "auto"}, apple_ok=True)
    assert isinstance(result, str)
    assert result == ENGINE_APPLE_VISION
