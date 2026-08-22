## 2024-05-14 - Global cursors for Tkinter ttk widgets
**Learning:** Setting the cursor property via ttk.Style().configure is ignored as it is a widget-level option. To apply a cursor globally to ttk widgets, the Tk option database must be used.
**Action:** Use root.option_add('*WidgetType.cursor', 'hand2') for interactive ttk widgets to improve discoverability and usability.
