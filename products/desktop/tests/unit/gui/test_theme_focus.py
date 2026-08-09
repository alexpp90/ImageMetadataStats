"""The dark theme must never cost keyboard users their focus indicator.

`clam` drops the focus ring unless `focuscolor` is declared in both
`style.configure` and `style.map`. That has regressed three times, so it is
asserted here for every interactive widget class the app styles.
"""

import tkinter as tk
from tkinter import ttk

import pytest

FOCUSABLE_STYLES = (
    "TButton",
    "Primary.TButton",
    "TCheckbutton",
    "TRadiobutton",
    "TEntry",
    "TCombobox",
    "TNotebook.Tab",
)


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as e:  # pragma: no cover - no display available
        pytest.skip(f"Tk unavailable: {e}")
    yield root
    try:
        root.destroy()
    except tk.TclError:  # pragma: no cover
        pass


@pytest.mark.parametrize("style_name", FOCUSABLE_STYLES)
def test_interactive_styles_declare_a_focus_colour(tk_root, style_name):
    from photo_selector_toolbox.gui.app import apply_dark_theme

    apply_dark_theme(tk_root)
    style = ttk.Style(tk_root)

    assert style.lookup(style_name, "focuscolor"), f"{style_name}: no configured focuscolor"
    assert style.map(style_name).get("focuscolor"), f"{style_name}: focus state not mapped"
