"""Aesthetic scoring settings — engine selection and per-engine configuration.

The aesthetic score can come from three very different engines, and the cost
difference between them is enormous: Apple Vision scores a photo on-device in a
fraction of a second, a local Ollama VLM takes seconds to tens of seconds for
the same photo. Before this dialog existed that choice was invisible — the
default ``auto`` mode could silently land on Ollama because an optional
dependency was missing, so the feature looked slow and bad rather than
under-provisioned.

Which engine actually runs is answered exclusively by
``tools.aesthetic.select_engine_with_reason``; this module never restates the
selection order. It turns that answer into wording a photographer can act on,
and offers the settings each engine needs.
"""

import ipaddress
import json
import logging
import socket
import threading
import tkinter as tk
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from photo_selector_toolbox.core.config import load_config, save_config
from photo_selector_toolbox.core.utils import (
    NoRedirectHandler,
    SafeSSRFHTTPHandler,
    SafeSSRFHTTPSHandler,
)
from photo_selector_toolbox.tools.aesthetic import (
    ENGINE_APPLE_VISION,
    ENGINE_AUTO,
    ENGINE_NIMA_ONNX,
    ENGINE_OLLAMA,
    apple_vision_available,
    apple_vision_unavailable_reason,
    onnxruntime_available,
    select_engine_with_reason,
)

logger = logging.getLogger(__name__)

# Dark theme palette (mirrors gui.app.ThemeColors; importing it here would be a
# circular import, app -> sharpness_tool -> aesthetic_settings).
BG_DARK = "#18181B"
BG_PANEL = "#27272A"
FG_LIGHT = "#F4F4F5"
FG_MUTED = "#A1A1AA"
ACCENT = "#6366F1"
COLOR_OK = "#22C55E"
COLOR_WARN = "#F59E0B"
COLOR_ERROR = "#EF4444"

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"

LEVEL_COLORS = {
    LEVEL_OK: COLOR_OK,
    LEVEL_WARN: COLOR_WARN,
    LEVEL_ERROR: COLOR_ERROR,
}


@dataclass(frozen=True)
class EngineOption:
    """One choice in the engine selector, described in the user's terms."""

    engine: str
    label: str
    blurb: str


# The order here is the order the radio buttons appear in, cheapest first after
# the recommended automatic choice.
ENGINE_OPTIONS: Tuple[EngineOption, ...] = (
    EngineOption(
        ENGINE_AUTO,
        "Automatic (recommended)",
        "Uses the fastest engine this computer can actually run, and says which one below.",
    ),
    EngineOption(
        ENGINE_APPLE_VISION,
        "Apple Vision — instant, nothing to install",
        "Scores a photo on this Mac in a fraction of a second. Needs macOS 15 or newer.",
    ),
    EngineOption(
        ENGINE_NIMA_ONNX,
        "NIMA model — fast, runs on any computer",
        "Also a fraction of a second per photo, but you have to supply the model file yourself.",
    ),
    EngineOption(
        ENGINE_OLLAMA,
        "Ollama (LLaVA) — slow, but writes a reason",
        "The only engine that explains its score, and hundreds of times slower than the others: "
        "seconds to tens of seconds per photo. Needs a local Ollama server.",
    ),
)

ENGINE_LABELS: Dict[str, str] = {
    ENGINE_APPLE_VISION: "Apple Vision",
    ENGINE_NIMA_ONNX: "NIMA model (ONNX)",
    ENGINE_OLLAMA: "Ollama (LLaVA)",
}

APPLE_REQUIREMENT = (
    "It needs macOS 15 or newer and the pyobjc-framework-Vision package (the optional 'apple' extra)."
)


@dataclass(frozen=True)
class EngineStatus:
    """What will actually run, and why — ready to be rendered.

    ``engine`` is whatever ``select_engine_with_reason`` resolved, so this
    object cannot disagree with the scan; ``reason`` is that function's own
    explanation, shown verbatim so the dialog and the log agree.
    """

    engine: str
    label: str
    headline: str
    detail: str
    reason: str
    level: str
    runnable: bool


def _nima_ready(
    config: Dict[str, Any], *, onnx_ok: bool, nima_model_exists: bool
) -> bool:
    """Whether the NIMA engine's prerequisites are met.

    Asked of the selector rather than restated here: with Apple Vision forced
    off, ``auto`` resolves to ``nima_onnx`` exactly when NIMA can run. Copying
    the condition into this module would be a second set of rules to keep in
    step with the first.
    """
    probe = dict(config)
    probe["aesthetic_engine"] = ENGINE_AUTO
    engine, _ = select_engine_with_reason(
        probe,
        apple_ok=False,
        onnx_ok=onnx_ok,
        nima_model_exists=nima_model_exists,
    )
    return engine == ENGINE_NIMA_ONNX


def _fast_engine_remedy(onnx_ok: bool) -> str:
    """How to get off the slow engine, worded so it is true on every platform."""
    if onnx_ok:
        return (
            "On macOS 15 or newer, install the optional 'apple' extra to get the instant "
            "Apple Vision engine; otherwise point 'NIMA model' below at an .onnx model file."
        )
    return (
        "On macOS 15 or newer, install the optional 'apple' extra to get the instant "
        "Apple Vision engine; otherwise install ONNX Runtime (the optional 'nima' extra) "
        "and point 'NIMA model' below at an .onnx model file."
    )


def describe_engine_status(
    config: Dict[str, Any],
    *,
    apple_ok: Optional[bool] = None,
    onnx_ok: Optional[bool] = None,
    nima_model_exists: Optional[bool] = None,
) -> EngineStatus:
    """Resolve the engine for ``config`` and explain the consequence.

    The decision itself comes from ``select_engine_with_reason``; everything
    added here is presentation. The availability flags are injectable so this
    can be unit-tested without macOS, ONNX Runtime or a model file.
    """
    if apple_ok is None:
        apple_ok = apple_vision_available()
    if onnx_ok is None:
        onnx_ok = onnxruntime_available()
    if nima_model_exists is None:
        model_path = str(config.get("nima_model_path") or "")
        nima_model_exists = bool(model_path) and Path(model_path).is_file()

    engine, reason = select_engine_with_reason(
        config,
        apple_ok=apple_ok,
        onnx_ok=onnx_ok,
        nima_model_exists=nima_model_exists,
    )
    label = ENGINE_LABELS.get(engine, engine)

    # Anything the selector does not recognise is treated by it as automatic;
    # mirror that here so the wording matches the decision.
    requested = str(config.get("aesthetic_engine") or ENGINE_AUTO)
    automatic = requested not in ENGINE_LABELS

    runnable = True
    if automatic:
        headline = f"Will run: {label} (chosen automatically)"
        if engine == ENGINE_APPLE_VISION:
            level = LEVEL_OK
            detail = (
                "Apple Vision is available on this computer, so scoring is near-instant "
                "and needs no setup."
            )
        elif engine == ENGINE_NIMA_ONNX:
            level = LEVEL_OK
            detail = (
                "Apple Vision is not available on this computer, so your NIMA model is used "
                "instead. It is also fast."
            )
        else:
            level = LEVEL_WARN
            detail = (
                "This is the slow engine: expect seconds to tens of seconds per photo instead "
                "of a fraction of a second. It was chosen only because no faster engine is set "
                "up. " + _fast_engine_remedy(onnx_ok)
            )
    else:
        headline = f"Will run: {label}"
        if engine == ENGINE_APPLE_VISION:
            if apple_ok:
                level = LEVEL_OK
                detail = "Apple Vision is ready on this computer and scores a photo in a fraction of a second."
            else:
                level = LEVEL_ERROR
                runnable = False
                detail = (
                    "Apple Vision cannot run on this computer, so aesthetic scoring will fail. "
                    + APPLE_REQUIREMENT
                    + " Switch to Automatic to fall back to an engine that works here."
                )
        elif engine == ENGINE_NIMA_ONNX:
            if _nima_ready(config, onnx_ok=onnx_ok, nima_model_exists=nima_model_exists):
                level = LEVEL_OK
                detail = (
                    "The NIMA model was found and ONNX Runtime is installed. Scoring takes a "
                    "fraction of a second per photo."
                )
            elif not onnx_ok:
                level = LEVEL_ERROR
                runnable = False
                detail = (
                    "ONNX Runtime is not installed, so aesthetic scoring will fail. Install it "
                    "(the optional 'nima' extra), then reopen this dialog."
                )
            else:
                level = LEVEL_ERROR
                runnable = False
                detail = (
                    "No NIMA model file was found, so aesthetic scoring will fail. Choose an "
                    ".onnx model under 'NIMA model' below."
                )
        else:
            level = LEVEL_WARN
            detail = (
                "Ollama writes a short reason for every score and is by far the slowest engine: "
                "seconds to tens of seconds per photo, against a fraction of a second for the "
                "others. Check the server under 'Ollama server' below."
            )

    return EngineStatus(
        engine=engine,
        label=label,
        headline=headline,
        detail=detail,
        reason=reason,
        level=level,
        runnable=runnable,
    )


# --------------------------------------------------------------------------- #
# Ollama connection probe (pure: takes strings, returns strings — safe to run
# on a worker thread, which is why it takes no Tkinter variables)
# --------------------------------------------------------------------------- #

def _is_forbidden_ip(ip_str: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        if ip_obj.is_link_local:
            return True
        if ip_obj.is_unspecified:
            return True
        mapped = getattr(ip_obj, "ipv4_mapped", None)
        if mapped is not None and mapped.is_link_local:
            return True
        if mapped is not None and mapped.is_unspecified:
            return True
        return False
    except ValueError:
        return False


def _fetch_ollama_models(url: str) -> List[str]:
    """List the models a local Ollama server has pulled (SSRF-guarded)."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    hostname = urlparse(url).hostname or ""
    clean_hostname = hostname.strip("[]")

    if _is_forbidden_ip(clean_hostname):
        raise ValueError("SSRF Protection: Cloud metadata IPs are not allowed.")

    try:
        addr_info = socket.getaddrinfo(clean_hostname, None)
    except socket.gaierror as e:
        raise ValueError(f"SSRF Protection: Could not resolve hostname {clean_hostname}: {e}")

    safe_ips = []
    for res in addr_info:
        ip_str = res[4][0]
        if _is_forbidden_ip(ip_str):
            raise ValueError("SSRF Protection: Cloud metadata IPs are not allowed.")
        safe_ips.append(ip_str)

    opener = urllib.request.build_opener(
        NoRedirectHandler,
        SafeSSRFHTTPHandler(safe_ips),
        SafeSSRFHTTPSHandler(safe_ips),
    )
    req = urllib.request.Request(f"{url.rstrip('/')}/api/tags")
    with opener.open(req, timeout=2.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m["name"] for m in data.get("models", [])]


def probe_ollama(url: str, model: str) -> Tuple[str, str]:
    """Check an Ollama server and report ``(message, level)``."""
    try:
        models = _fetch_ollama_models(url)
    except Exception as e:
        return (
            f"Cannot connect to Ollama at '{url}'.\n"
            "Is the service running? Install it from https://ollama.com.\n"
            f"Error: {e}",
            LEVEL_ERROR,
        )

    # "llava" matches "llava:latest" and "llava:7b".
    matched = any(m == model or m.split(":")[0] == model for m in models)
    if matched:
        return (
            f"Success! Model '{model}' is running locally and ready for analysis.",
            LEVEL_OK,
        )

    available = ", ".join(models) if models else "none"
    return (
        f"Connected to Ollama, but model '{model}' is not pulled.\n"
        f"Available models: {available}\n"
        f"Please run 'ollama pull {model}' in your terminal.",
        LEVEL_WARN,
    )


# --------------------------------------------------------------------------- #
# Dialog
# --------------------------------------------------------------------------- #

class AestheticSettingsDialog(tk.Toplevel):
    """Choose the aesthetic scoring engine and configure the one that runs.

    Progressive disclosure: the per-engine settings live in a notebook whose
    tab follows the *resolved* engine (so ``auto`` shows what it actually
    picked), while every tab stays clickable — an existing Ollama user must
    still be able to reach their prompt.
    """

    MIN_WIDTH = 600
    MIN_HEIGHT = 640

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Aesthetic Scoring Settings")
        self.configure(bg=BG_DARK)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        self.config_data = load_config()

        # The import probes cannot change while the dialog is open, and they are
        # the expensive half of the availability check — ask once.
        self._apple_ok = apple_vision_available()
        self._onnx_ok = onnxruntime_available()
        self._apple_reason = apple_vision_unavailable_reason()

        engine = str(self.config_data.get("aesthetic_engine") or ENGINE_AUTO)
        if engine not in {opt.engine for opt in ENGINE_OPTIONS}:
            engine = ENGINE_AUTO
        self.engine_var = tk.StringVar(value=engine)
        self.nima_path_var = tk.StringVar(value=str(self.config_data.get("nima_model_path") or ""))
        self.url_var = tk.StringVar(value=str(self.config_data.get("ollama_url") or ""))
        self.model_var = tk.StringVar(value=str(self.config_data.get("ollama_model") or ""))
        self.status: Optional[EngineStatus] = None

        content = ttk.Frame(self, padding=15)
        content.pack(fill="both", expand=True)

        ttk.Label(
            content,
            text="🎨 Aesthetic Scoring",
            font=("Helvetica", 12, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        self._build_engine_chooser(content)
        self._build_status_panel(content)
        # Save/Cancel claim their space before the notebook, so a window that
        # ends up shorter than requested (small screen) shrinks the tab area
        # instead of clipping the buttons off the bottom edge.
        self._build_action_buttons(content)
        self._build_engine_settings(content)

        self._refresh_status(select_tab=True)
        self.nima_path_var.trace_add("write", self._on_nima_path_changed)

        self._finalize_geometry(parent)
        self.bind("<Escape>", lambda e: self.destroy())

    # ── construction ────────────────────────────────────────────────
    def _build_engine_chooser(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Scoring engine", padding=10)
        box.pack(fill="x")

        self.engine_radios = {}
        for option in ENGINE_OPTIONS:
            row = ttk.Frame(box)
            row.pack(fill="x", pady=(0, 6))
            radio = ttk.Radiobutton(
                row,
                text=option.label,
                value=option.engine,
                variable=self.engine_var,
                command=self._on_engine_changed,
            )
            radio.pack(anchor="w")
            self.engine_radios[option.engine] = radio
            ttk.Label(
                row,
                text=option.blurb,
                style="Muted.TLabel",
                wraplength=520,
                justify="left",
            ).pack(anchor="w", padx=(22, 0))

    def _build_status_panel(self, parent) -> None:
        panel = ttk.Frame(parent, style="MetaPanel.TFrame", padding=10)
        panel.pack(fill="x", pady=10)

        self.status_headline = ttk.Label(
            panel,
            text="",
            style="MetaPanel.TLabel",
            font=("Helvetica", 10, "bold"),
            wraplength=520,
            justify="left",
        )
        self.status_headline.pack(anchor="w")

        self.status_detail = ttk.Label(
            panel,
            text="",
            style="MetaPanel.TLabel",
            wraplength=520,
            justify="left",
        )
        self.status_detail.pack(anchor="w", pady=(4, 0))

        self.status_reason = ttk.Label(
            panel,
            text="",
            style="MetaPanel.TLabel",
            foreground=FG_MUTED,
            font=("Helvetica", 8),
            wraplength=520,
            justify="left",
        )
        self.status_reason.pack(anchor="w", pady=(4, 0))

    def _build_engine_settings(self, parent) -> None:
        self.settings_nb = ttk.Notebook(parent)
        self.settings_nb.pack(fill="both", expand=True)

        self.apple_tab = ttk.Frame(self.settings_nb, padding=12)
        self.nima_tab = ttk.Frame(self.settings_nb, padding=12)
        self.ollama_tab = ttk.Frame(self.settings_nb, padding=12)

        self.settings_nb.add(self.apple_tab, text="Apple Vision")
        self.settings_nb.add(self.nima_tab, text="NIMA model")
        self.settings_nb.add(self.ollama_tab, text="Ollama server")

        self.engine_tabs = {
            ENGINE_APPLE_VISION: self.apple_tab,
            ENGINE_NIMA_ONNX: self.nima_tab,
            ENGINE_OLLAMA: self.ollama_tab,
        }

        self._build_apple_tab(self.apple_tab)
        self._build_nima_tab(self.nima_tab)
        self._build_ollama_tab(self.ollama_tab)

    def _build_apple_tab(self, parent) -> None:
        ttk.Label(
            parent,
            text="Nothing to configure — Apple Vision scores photos on-device.",
            wraplength=520,
            justify="left",
        ).pack(anchor="w")

        if self._apple_ok:
            text = "Available on this computer."
            color = COLOR_OK
        else:
            text = f"Not available here ({self._apple_reason}). {APPLE_REQUIREMENT}"
            color = COLOR_WARN
        ttk.Label(
            parent, text=text, foreground=color, wraplength=520, justify="left"
        ).pack(anchor="w", pady=(8, 0))

    def _build_nima_tab(self, parent) -> None:
        ttk.Label(
            parent,
            text="A small scoring model you supply yourself (a NIMA network exported to ONNX).",
            wraplength=520,
            justify="left",
        ).pack(anchor="w")

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(8, 0))
        ttk.Label(row, text="📦 Model file:", width=14, anchor="w").pack(side="left")
        self.nima_entry = ttk.Entry(row, textvariable=self.nima_path_var)
        self.nima_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.nima_browse_btn = ttk.Button(
            row, text="📁 Browse...", command=self._browse_nima_model
        )
        self.nima_browse_btn.pack(side="right")

        if not self._onnx_ok:
            ttk.Label(
                parent,
                text="ONNX Runtime is not installed on this computer (the optional 'nima' extra).",
                foreground=COLOR_WARN,
                wraplength=520,
                justify="left",
            ).pack(anchor="w", pady=(8, 0))

    def _build_ollama_tab(self, parent) -> None:
        url_row = ttk.Frame(parent)
        url_row.pack(fill="x")
        ttk.Label(url_row, text="🌐 Ollama URL:", width=14, anchor="w").pack(side="left")
        ttk.Entry(url_row, textvariable=self.url_var).pack(side="left", fill="x", expand=True)

        model_row = ttk.Frame(parent)
        model_row.pack(fill="x", pady=(6, 0))
        ttk.Label(model_row, text="🤖 Model Name:", width=14, anchor="w").pack(side="left")
        ttk.Entry(model_row, textvariable=self.model_var).pack(side="left", fill="x", expand=True)

        # Packed before the prompt so the "Test Connection" button keeps its
        # space when the tab area is squeezed; the prompt box absorbs the loss.
        status_frame = ttk.LabelFrame(parent, text="Connection Status", padding=8)
        status_frame.pack(side="bottom", fill="x", pady=(8, 0))

        self.ollama_status_lbl = ttk.Label(
            status_frame,
            text="Click 'Test Connection' to check setup.",
            foreground=FG_MUTED,
            wraplength=480,
            justify="left",
        )
        self.ollama_status_lbl.pack(fill="x", pady=5)

        self.test_btn = ttk.Button(
            status_frame, text="🔌 Test Connection", command=self._start_connection_test
        )
        self.test_btn.pack(anchor="e")

        prompt_frame = ttk.Frame(parent)
        prompt_frame.pack(fill="both", expand=True, pady=(6, 0))
        ttk.Label(prompt_frame, text="📝 Prompt:", anchor="w").pack(anchor="w", pady=(0, 2))

        self.prompt_text = tk.Text(
            prompt_frame,
            height=5,
            wrap="word",
            font=("Helvetica", 10),
            bg=BG_PANEL,
            fg=FG_LIGHT,
            insertbackground=FG_LIGHT,
            highlightbackground=BG_PANEL,
            highlightcolor=ACCENT,
            borderwidth=1,
            relief="flat",
        )
        self.prompt_text.pack(fill="both", expand=True)
        self.prompt_text.insert("1.0", str(self.config_data.get("ollama_prompt") or ""))

    def _build_action_buttons(self, parent) -> None:
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Button(
            btn_frame, text="💾 Save Settings", command=self.save_settings, style="Primary.TButton"
        ).pack(side="left", expand=True, padx=5)
        ttk.Button(btn_frame, text="❌ Cancel", command=self.destroy).pack(
            side="right", expand=True, padx=5
        )

    def _finalize_geometry(self, parent) -> None:
        self.update_idletasks()
        width = max(self.MIN_WIDTH, int(self.winfo_reqwidth()))
        height = max(self.MIN_HEIGHT, int(self.winfo_reqheight()))
        height = min(height, max(400, int(self.winfo_screenheight()) - 100))

        top = parent.winfo_toplevel()
        x = top.winfo_rootx() + (top.winfo_width() - width) // 2
        y = top.winfo_rooty() + (top.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min(width, self.MIN_WIDTH), min(height, self.MIN_HEIGHT))
        self.resizable(True, True)

    # ── state ───────────────────────────────────────────────────────
    def pending_config(self) -> Dict[str, Any]:
        """The config as the dialog currently stands (unsaved edits included)."""
        config = dict(self.config_data)
        config["aesthetic_engine"] = self.engine_var.get()
        config["nima_model_path"] = self.nima_path_var.get().strip()
        return config

    def _on_engine_changed(self) -> None:
        # Only an explicit engine change moves the notebook, so that typing a
        # model path cannot yank the tab out from under the user.
        self._refresh_status(select_tab=True)

    def _on_nima_path_changed(self, *_args) -> None:
        self._refresh_status()

    def _refresh_status(self, select_tab: bool = False) -> None:
        config = self.pending_config()
        model_path = str(config.get("nima_model_path") or "")
        status = describe_engine_status(
            config,
            apple_ok=self._apple_ok,
            onnx_ok=self._onnx_ok,
            nima_model_exists=bool(model_path) and Path(model_path).is_file(),
        )
        self.status = status

        self.status_headline.config(
            text=status.headline, foreground=LEVEL_COLORS.get(status.level, FG_LIGHT)
        )
        self.status_detail.config(text=status.detail)
        self.status_reason.config(text=f"Decision: {status.reason}")

        if select_tab:
            tab = self.engine_tabs.get(status.engine)
            if tab is not None:
                self.settings_nb.select(tab)

    # ── actions ─────────────────────────────────────────────────────
    def _browse_nima_model(self) -> None:
        current = self.nima_path_var.get().strip()
        initial = str(Path(current).parent) if current else ""
        path = filedialog.askopenfilename(
            parent=self,
            title="Select NIMA ONNX model",
            initialdir=initial or None,
            filetypes=[("ONNX model", "*.onnx"), ("All files", "*.*")],
        )
        if path:
            self.nima_path_var.set(path)

    def _start_connection_test(self) -> None:
        # Tkinter variables are read here, on the main thread, and passed to the
        # worker as plain strings.
        url = self.url_var.get().strip()
        model = self.model_var.get().strip()
        self._set_ollama_status("Connecting to Ollama...", ACCENT)
        threading.Thread(
            target=self._run_connection_test, args=(url, model), daemon=True
        ).start()

    def _run_connection_test(self, url: str, model: str) -> None:
        message, level = probe_ollama(url, model)
        color = LEVEL_COLORS.get(level, FG_MUTED)
        try:
            self.after(0, lambda: self._set_ollama_status(message, color))
        except Exception:  # pragma: no cover - dialog closed mid-test
            logger.debug("Ollama test result dropped: dialog no longer exists.")

    def _set_ollama_status(self, message: str, color: str) -> None:
        try:
            if self.ollama_status_lbl.winfo_exists():
                self.ollama_status_lbl.config(text=message, foreground=color)
        except Exception:  # pragma: no cover - dialog closed mid-test
            pass

    def save_settings(self) -> None:
        # Load-mutate-save: writing only the touched keys would wipe every other
        # setting, since save_config replaces the file wholesale.
        config = load_config()
        config["aesthetic_engine"] = self.engine_var.get()
        config["nima_model_path"] = self.nima_path_var.get().strip()
        config["ollama_url"] = self.url_var.get().strip()
        config["ollama_model"] = self.model_var.get().strip()
        config["ollama_prompt"] = self.prompt_text.get("1.0", "end-1c").strip()
        save_config(config)
        self.destroy()
