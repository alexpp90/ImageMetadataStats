## 2024-08-06 - Global Tkinter Button Cursors
**Learning:** In Tkinter, setting the `cursor` property via `ttk.Style().configure` is ignored because it's a widget-level option. To apply a cursor globally to ttk widgets, the Tk option database must be used (`root.option_add`).
**Action:** Always use the Tk option database to apply global widget properties that aren't supported by ttk themes.
