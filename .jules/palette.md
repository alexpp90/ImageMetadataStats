## 2025-02-23 - Tkinter ttk Widget Cursors
**Learning:** In Tkinter 'clam' themes, setting the `cursor` property via `ttk.Style().configure` is silently ignored because it is a widget-level option, not a style option.
**Action:** To apply a cursor globally to `ttk` interactive widgets (like buttons and checkboxes), use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`).
## 2025-02-23 - Tkinter ttk Widget Cursors
**Learning:** In Tkinter 'clam' themes, setting the `cursor` property via `ttk.Style().configure` is silently ignored because it is a widget-level option, not a style option.
**Action:** To apply a cursor globally to `ttk` interactive widgets (like buttons and checkboxes), use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`).
