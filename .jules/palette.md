## 2024-05-19 - Hand Cursor on Interactive Elements
**Learning:** In Tkinter, setting the `cursor` property via `ttk.Style().configure('TButton', cursor='hand2')` is silently ignored because it is a widget-level option, not a style option. To apply a cursor globally to `ttk` widgets, use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`).
**Action:** Apply hand2 cursors globally using root.option_add for all standard interactive widgets (TButton, TCheckbutton, TRadiobutton, TCombobox).
