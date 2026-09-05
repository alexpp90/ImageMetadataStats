## 2025-02-12 - Tkinter Global Cursors for Interactive Widgets
**Learning:** Setting the `cursor` property via `ttk.Style().configure` is silently ignored for widget-level options. Applying cursors to container widgets introduces severe UX regressions because child widgets inherit the cursor.
**Action:** Always use the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`) to apply cursors to specific interactive leaf widgets globally.
