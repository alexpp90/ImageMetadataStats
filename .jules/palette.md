## 2024-08-15 - Add Hand Cursors to Buttons
**Learning:** In Tkinter, setting the `cursor` property via `ttk.Style().configure('TButton', cursor='hand2')` is silently ignored because `cursor` is a widget-level option, not a style option. To apply a cursor globally to ttk widgets, use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`).
**Action:** Apply the cursor using `root.option_add` for all ttk button interactions to provide visual feedback and improve discoverability of clickable elements.
