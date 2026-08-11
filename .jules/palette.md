## 2024-08-11 - Add global hand cursor for Tkinter interactive elements
**Learning:** In Tkinter, setting the `cursor` property via `ttk.Style().configure('TButton', cursor='hand2')` is silently ignored because `cursor` is a widget-level option, not a style option. Adding hand cursors to interactive elements improves discoverability and provides better user feedback on hover states.
**Action:** Applied a global hand cursor to common interactive ttk widgets using `root.option_add('*<WidgetClass>.cursor', 'hand2')` instead of modifying individual widget styles.
