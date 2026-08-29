## 2023-08-29 - [Setting Tkinter Cursors Globally]
**Learning:** In Tkinter `clam` themes, setting the cursor property via `ttk.Style().configure('TButton', cursor='hand2')` is silently ignored because cursor is a widget-level option, not a style option.
**Action:** Always use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`) to apply cursor changes globally to `ttk` widgets like `TButton`.
