## 2025-02-19 - Global Cursor Configuration in Tkinter
**Learning:** In Tkinter, setting the cursor property via `ttk.Style().configure` is silently ignored for many widgets because it's a widget-level option, not a style option.
**Action:** To apply a cursor globally to `ttk` widgets like buttons, checkboxes, and notebooks, use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`).
