## 2025-02-28 - Tkinter ttk Widget Cursor Styling
**Learning:** In Tkinter 'clam' themes, applying `cursor` via `ttk.Style().configure` (e.g., to `TButton`) is silently ignored because it is a widget-level option, not a style option.
**Action:** To apply a cursor globally to ttk widgets, always use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`) on the root window.
