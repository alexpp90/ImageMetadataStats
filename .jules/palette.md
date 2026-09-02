## 2024-05-24 - Global Cursors for ttk Widgets
**Learning:** In Tkinter, setting the `cursor` property via `ttk.Style().configure` is silently ignored because it is a widget-level option, not a style option. Furthermore, setting a global cursor on container widgets introduces severe UX regressions because child widgets inherit the cursor if they don't explicitly define one.
**Action:** Only apply cursors to specific interactive leaf widgets globally via the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`).
