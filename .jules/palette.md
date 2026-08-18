## 2024-08-18 - Global Hand Cursors for ttk Widgets in Tkinter
**Learning:** Setting the `cursor` property via `ttk.Style().configure('TButton', cursor='hand2')` is silently ignored in Tkinter because `cursor` is a widget-level option, not a style option.
**Action:** Always apply cursor modifications globally to ttk widgets using the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`).
