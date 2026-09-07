## 2024-03-24 - Tkinter Global Hand Cursor
**Learning:** In Tkinter, configuring a cursor via ttk.Style() is silently ignored because it is a widget-level option. Setting it globally via root.option_add on container widgets introduces UX regressions because children inherit it.
**Action:** Always use the Tk option database to apply cursors globally only to specific interactive leaf widgets (e.g., *TButton.cursor), and use pointinghand instead of hand2 on macOS for a native feel.
