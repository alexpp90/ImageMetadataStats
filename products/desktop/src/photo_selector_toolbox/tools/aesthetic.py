"""
Aesthetic scoring for the desktop app.

Historically the aesthetic score came exclusively from a local Ollama vision
language model (LLaVA). That approach is heavy (multi-GB model, seconds per
image, high battery/CPU cost) and non-deterministic — a very large generative
model used to produce a single scalar.

This module introduces a lightweight, purpose-built scoring stack and keeps
Ollama available as an optional *advanced* engine:

* ``apple_vision`` — Apple's on-device Vision aesthetics request
  (``VNCalculateImageAestheticsScoresRequest``, macOS 15+). Neural-Engine
  accelerated, ~milliseconds per image, no model to ship. Primary on modern
  macOS.
* ``nima_onnx`` — a small NIMA (MobileNet) regressor run via ONNX Runtime.
  Deterministic, dependency-light, portable to older macOS / Linux / Windows.
* ``ollama`` — the original LLaVA VLM, retained as an opt-in "deep critique"
  engine for users who already run Ollama.

The engine is chosen by the ``aesthetic_engine`` config key. In ``auto`` mode
the best available engine is selected at runtime, and the stack degrades
gracefully to Ollama so existing setups keep working until the new engines are
provisioned.

Native/model-backed paths (PyObjC Vision bridge, ONNX Runtime, model files)
cannot be exercised in a headless CI sandbox — they are guarded behind
availability checks and unit-tested at the pure-logic level (score mapping,
distribution→score, engine selection). Verify the live engines on a Mac /
target machine.
"""

import importlib
import logging
import platform
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from photo_selector_toolbox.tools.registry import AnalysisTool, ToolRegistry
from photo_selector_toolbox.core.config import DEFAULT_CONFIG, load_config

logger = logging.getLogger(__name__)

# Engine identifiers (also the accepted values of the ``aesthetic_engine`` key).
ENGINE_AUTO = "auto"
ENGINE_APPLE_VISION = "apple_vision"
ENGINE_NIMA_ONNX = "nima_onnx"
ENGINE_OLLAMA = "ollama"

VALID_ENGINES = (ENGINE_AUTO, ENGINE_APPLE_VISION, ENGINE_NIMA_ONNX, ENGINE_OLLAMA)


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested without any native dependency)
# --------------------------------------------------------------------------- #

def _clamp10(value: float) -> float:
    """Clamp a score into the app's canonical 1.0-10.0 range."""
    return max(1.0, min(10.0, value))


def map_apple_score_to_10(overall_score: float) -> float:
    """Map Apple Vision's ``overallScore`` onto the app's 1.0-10.0 scale.

    Apple documents ``overallScore`` as a float in ``[-1.0, 1.0]``, higher
    being more aesthetically pleasing. That documented range is mapped
    linearly onto ``[1.0, 10.0]``; the mapping is monotone, so it preserves
    Vision's ordering, which is what ranking a library needs.

    An earlier version assumed an *effective* range of ``[-0.5, 0.5]`` on the
    grounds that real photos cluster there. Measurement contradicts it: 84 real
    JPEGs scored with ``VNCalculateImageAestheticsScoresRequest``
    (pyobjc-framework-Vision 12.2.1, macOS 26.6, M4 Air) gave min -0.042,
    median 0.565, p90 0.720, max 0.915 — under the narrow mapping 59 of those
    84 images (70%) clamped to exactly 10.0, leaving 15 distinct values in the
    whole library. Over the documented range the same corpus pins nothing and
    spreads across 23 distinct values in 5.3-9.6. That corpus is a Lightroom
    "saved photos" export (keepers only) and therefore biased upward, so it is
    used to reject the narrow range rather than to fit a bespoke curve to it.
    """
    # Map [-1.0, 1.0] -> [0, 1]. Clamping only guards against out-of-contract
    # values; in practice nothing reaches the endpoints.
    normalized = (float(overall_score) + 1.0) / 2.0
    return round(_clamp10(1.0 + normalized * 9.0), 1)


def nima_distribution_to_score(probs: Sequence[float]) -> float:
    """Convert a NIMA rating distribution to a single aesthetic score.

    NIMA outputs a probability distribution over the discrete ratings 1..10.
    The score is the expected value (mean) of that distribution, matching the
    original NIMA paper.
    """
    if probs is None or len(probs) == 0:
        raise ValueError("empty NIMA distribution")
    total = float(sum(probs))
    if total <= 0:
        raise ValueError("invalid NIMA distribution (non-positive sum)")
    mean = sum((i + 1) * float(p) for i, p in enumerate(probs)) / total
    return round(_clamp10(mean), 1)


# --------------------------------------------------------------------------- #
# Availability probes
# --------------------------------------------------------------------------- #

def _macos_version_tuple() -> Optional[Tuple[int, ...]]:
    if platform.system() != "Darwin":
        return None
    try:
        parts = platform.mac_ver()[0].split(".")
        return tuple(int(p) for p in parts if p != "")
    except Exception:
        return None


# Import probes are the expensive part of the availability checks (a failed
# import walks the whole sys.path, a successful one loads a PyObjC framework),
# and they are re-run for every scored image. Their answer cannot change within
# a process, so memoise it behind a lock — the scan runs on a thread pool.
# The *config* is deliberately not cached: the user can switch engines mid
# session and must not have to restart.
_PROBE_LOCK = threading.Lock()
_PROBE_CACHE: Dict[str, bool] = {}


def _module_importable(module_name: str) -> bool:
    """True when ``import <module_name>`` succeeds. Memoised per process."""
    with _PROBE_LOCK:
        cached = _PROBE_CACHE.get(module_name)
        if cached is not None:
            return cached
    try:
        importlib.import_module(module_name)
        ok = True
    except Exception:
        ok = False
    with _PROBE_LOCK:
        _PROBE_CACHE[module_name] = ok
    return ok


def reset_availability_probe_cache() -> None:
    """Forget the memoised import probes (tests, and after installing extras)."""
    with _PROBE_LOCK:
        _PROBE_CACHE.clear()


def apple_vision_unavailable_reason() -> Optional[str]:
    """Why Apple Vision cannot be used here, or ``None`` when it can.

    The string is user-facing: it is what the settings dialog shows to explain
    an ``auto`` decision.
    """
    ver = _macos_version_tuple()
    if ver is None:
        return "not macOS"
    if ver[0] < 15:
        pretty = ".".join(str(p) for p in ver) or "unknown"
        return f"macOS {pretty} is older than macOS 15"
    if not _module_importable("Vision"):
        return (
            "pyobjc-framework-Vision not importable "
            "(install the optional 'apple' extra)"
        )
    return None


def apple_vision_available() -> bool:
    """True when the Apple Vision aesthetics request can be used (macOS 15+ with
    the PyObjC Vision bridge importable)."""
    return apple_vision_unavailable_reason() is None


def onnxruntime_available() -> bool:
    return _module_importable("onnxruntime")


def _nima_model_path(config: Dict[str, Any]) -> str:
    return str(config.get("nima_model_path") or DEFAULT_CONFIG.get("nima_model_path", "") or "")


def _nima_unavailable_reason(
    config: Dict[str, Any], onnx_ok: bool, nima_model_exists: bool
) -> Optional[str]:
    """Why the NIMA ONNX engine cannot be used, or ``None`` when it can."""
    if not onnx_ok:
        return "onnxruntime not installed (install the optional 'nima' extra)"
    if nima_model_exists:
        return None
    model_path = _nima_model_path(config)
    if not model_path:
        return "no model configured (set 'nima_model_path' in settings.json)"
    return f"model file not found: {model_path}"


def select_engine_with_reason(
    config: Dict[str, Any],
    *,
    apple_ok: Optional[bool] = None,
    onnx_ok: Optional[bool] = None,
    nima_model_exists: Optional[bool] = None,
) -> Tuple[str, str]:
    """Resolve which engine to use, and say why.

    An explicit ``aesthetic_engine`` other than ``auto`` is honoured verbatim.
    In ``auto`` mode we prefer Apple Vision, then a NIMA ONNX model (only if a
    model file is present), and finally fall back to Ollama so existing
    installs keep working.

    That last fallback is the dangerous one — Ollama costs seconds per image
    where Apple Vision costs milliseconds, so an install that silently lands on
    it looks like a slow, bad feature rather than a missing optional
    dependency. The second element of the return value is a human-readable
    explanation of the decision, intended for logs and for the settings dialog.

    The availability flags are injectable purely so this decision can be
    unit-tested without native dependencies.

    Returns:
        ``(engine, reason)`` where ``engine`` is one of :data:`VALID_ENGINES`
        minus ``auto``, and ``reason`` is a non-empty, user-presentable string.
    """
    raw_engine = str(config.get("aesthetic_engine", ENGINE_AUTO) or ENGINE_AUTO)
    engine = raw_engine
    prefix = ""
    if engine not in VALID_ENGINES:
        logger.warning("Unknown aesthetic_engine '%s'; falling back to auto.", engine)
        engine = ENGINE_AUTO
        prefix = f"unknown aesthetic_engine '{raw_engine}', resolved automatically: "
    if engine != ENGINE_AUTO:
        return engine, f"{prefix}explicitly configured as '{engine}'"

    if apple_ok is None:
        apple_reason = apple_vision_unavailable_reason()
        apple_ok = apple_reason is None
    else:
        apple_reason = None if apple_ok else "reported unavailable"
    if onnx_ok is None:
        onnx_ok = onnxruntime_available()
    if nima_model_exists is None:
        mp = _nima_model_path(config)
        nima_model_exists = bool(mp) and Path(mp).is_file()

    if apple_ok:
        return ENGINE_APPLE_VISION, f"{prefix}auto: apple_vision available"

    nima_reason = _nima_unavailable_reason(config, onnx_ok, nima_model_exists)
    if nima_reason is None:
        return (
            ENGINE_NIMA_ONNX,
            f"{prefix}auto: apple_vision unavailable: {apple_reason}; "
            f"using nima_onnx",
        )

    return (
        ENGINE_OLLAMA,
        f"{prefix}auto: apple_vision unavailable: {apple_reason}; "
        f"nima_onnx unavailable: {nima_reason}; falling back to ollama",
    )


def select_engine(
    config: Dict[str, Any],
    *,
    apple_ok: Optional[bool] = None,
    onnx_ok: Optional[bool] = None,
    nima_model_exists: Optional[bool] = None,
) -> str:
    """Resolve which engine to use.

    Thin wrapper over :func:`select_engine_with_reason` for callers that only
    need the decision. See that function for the selection rules.
    """
    return select_engine_with_reason(
        config,
        apple_ok=apple_ok,
        onnx_ok=onnx_ok,
        nima_model_exists=nima_model_exists,
    )[0]


# --------------------------------------------------------------------------- #
# Engines
# --------------------------------------------------------------------------- #

class AppleVisionAestheticEngine:
    """On-device aesthetics via Apple's Vision framework (macOS 15+).

    Requires the PyObjC ``Vision`` framework. Returns ``(score, tag)`` where the
    tag flags "utility" images (screenshots, receipts, documents) which are not
    memorable photos even if technically clean.
    """

    def analyze(self, filepath: Path, **kwargs: Any) -> Tuple[float, str]:
        try:
            import Vision
            from Foundation import NSURL
        except Exception as e:  # pragma: no cover - requires macOS + PyObjC
            raise RuntimeError(
                "Apple Vision engine unavailable (needs macOS 15+ and "
                f"pyobjc-framework-Vision): {e}"
            )

        url = NSURL.fileURLWithPath_(str(filepath))
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {})
        request = Vision.VNCalculateImageAestheticsScoresRequest.alloc().init()

        success, error = handler.performRequests_error_([request], None)
        if not success:
            raise RuntimeError(f"Vision aesthetics request failed: {error}")

        results = request.results()
        if not results:
            raise RuntimeError("Vision returned no aesthetics observation")

        obs = results[0]
        overall = float(obs.overallScore())
        try:
            is_utility = bool(obs.isUtility())
        except Exception:
            is_utility = False

        score = map_apple_score_to_10(overall)
        tag = "Utility/Screenshot" if is_utility else "N/A"
        return score, tag


class NimaOnnxAestheticEngine:
    """Small NIMA (MobileNet) aesthetic regressor via ONNX Runtime.

    The model is not bundled; provide a path via the ``nima_model_path`` setting
    (a NIMA model exported to ONNX that outputs a 10-way rating distribution).
    """

    _session = None
    _session_path: Optional[str] = None

    def _get_session(self, model_path: str):  # pragma: no cover - needs onnxruntime
        import onnxruntime

        if self._session is None or self._session_path != model_path:
            self._session = onnxruntime.InferenceSession(
                model_path, providers=onnxruntime.get_available_providers()
            )
            self._session_path = model_path
        return self._session

    def analyze(self, filepath: Path, **kwargs: Any) -> Tuple[float, str]:
        config = load_config()
        model_path = _nima_model_path(config)
        if not model_path or not Path(model_path).is_file():
            raise RuntimeError(
                "NIMA ONNX model not found. Set 'nima_model_path' in settings.json "
                "to a NIMA model exported to ONNX."
            )
        try:  # pragma: no cover - needs numpy + onnxruntime + a model
            import numpy as np
        except Exception as e:
            raise RuntimeError(f"numpy is required for the NIMA engine: {e}")

        from photo_selector_toolbox.core.utils import load_image_preview

        img = load_image_preview(filepath, max_size=(224, 224))
        if img is None:
            raise RuntimeError("failed to load image for NIMA scoring")

        img = img.convert("RGB").resize((224, 224))
        arr = np.asarray(img).astype("float32") / 255.0
        # ImageNet normalisation (typical for MobileNet-based NIMA exports).
        mean = np.array([0.485, 0.456, 0.406], dtype="float32")
        std = np.array([0.229, 0.224, 0.225], dtype="float32")
        arr = (arr - mean) / std
        session = self._get_session(model_path)
        input_info = session.get_inputs()[0]
        input_name = input_info.name
        input_shape = input_info.shape

        # The image array is currently HWC (224, 224, 3).
        # Check if the model expects NCHW (channels at index 1) or NHWC.
        if len(input_shape) >= 4 and input_shape[1] == 3:
            # NCHW batch of 1
            arr = np.transpose(arr, (2, 0, 1))[None, ...]
        else:
            # NHWC batch of 1
            arr = arr[None, ...]

        outputs = session.run(None, {input_name: arr})
        probs = np.asarray(outputs[0]).reshape(-1).tolist()
        score = nima_distribution_to_score(probs)
        return score, "N/A"


# --------------------------------------------------------------------------- #
# Dispatcher tool (the single registered "aesthetic" tool)
# --------------------------------------------------------------------------- #

def describe_active_engine() -> Tuple[str, str]:
    """Resolve the engine for the *current* settings and explain the choice.

    Convenience entry point for the GUI (settings dialog) so it does not have
    to load the config itself. Returns ``(engine, reason)``.
    """
    return select_engine_with_reason(load_config())


_LAST_DECISION_LOCK = threading.Lock()
_last_logged_decision: Optional[Tuple[str, str]] = None


def _log_engine_decision(engine: str, reason: str) -> None:
    """Log the engine choice at INFO, once per distinct decision.

    Scoring runs per image on a thread pool; repeating an identical line for
    every photo would bury the one message that matters (that we silently
    degraded to a much slower engine).
    """
    global _last_logged_decision
    with _LAST_DECISION_LOCK:
        first_time = _last_logged_decision != (engine, reason)
        _last_logged_decision = (engine, reason)
    if first_time:
        logger.info("Aesthetic scoring engine: %s (%s)", engine, reason)
    else:
        logger.debug("Aesthetic scoring engine: %s (%s)", engine, reason)

@ToolRegistry.register
class AestheticTool(AnalysisTool):
    """Aesthetic scoring tool that delegates to the configured engine."""

    name = "aesthetic"
    display_name = "AI Aesthetic Evaluation"

    def analyze(self, filepath: Path, **kwargs: Any) -> Tuple[float, str]:
        # The config is re-read per image on purpose: the user may switch
        # engines mid-session. Only the import probes behind it are memoised.
        config = load_config()
        engine, reason = select_engine_with_reason(config)
        _log_engine_decision(engine, reason)

        if engine == ENGINE_APPLE_VISION:
            return AppleVisionAestheticEngine().analyze(filepath, **kwargs)
        if engine == ENGINE_NIMA_ONNX:
            return NimaOnnxAestheticEngine().analyze(filepath, **kwargs)

        # Default / advanced fallback: the original Ollama VLM.
        from photo_selector_toolbox.tools.ollama import OllamaAestheticTool

        return OllamaAestheticTool().analyze(filepath, **kwargs)
