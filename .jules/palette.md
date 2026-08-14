## 2024-08-14 - Global cursors for Tkinter ttk widgets
**Learning:** In Tkinter's ttk module, setting the `cursor` property via `ttk.Style().configure('TButton', cursor='hand2')` is silently ignored because `cursor` is a widget-level option, not a style option.
**Action:** To apply a cursor globally to ttk widgets like TButton, TCheckbutton, or TRadiobutton, use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`) when setting up the main application root.
