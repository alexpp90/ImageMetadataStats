## 2024-08-24 - Tkinter ttk widget cursor styling
**Learning:** In Tkinter, setting the `cursor` property via `ttk.Style().configure` is silently ignored for many widgets because it is treated as a widget-level option, not a style option.
**Action:** To apply a cursor globally to `ttk` interactive elements (like TButton, TCheckbutton, TRadiobutton), use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`).
