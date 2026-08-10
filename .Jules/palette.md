## 2024-08-10 - Global ttk cursors
**Learning:** In Tkinter, setting the `cursor` property via `ttk.Style().configure('TButton', cursor='hand2')` is silently ignored because `cursor` is a widget-level option, not a style option.
**Action:** To apply a cursor globally to ttk widgets, use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`).
