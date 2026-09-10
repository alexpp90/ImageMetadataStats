## 2024-05-24 - Tkinter Cursor Inheritance
**Learning:** In Tkinter, setting a global cursor on container widgets (like `root.option_add('*TNotebook.cursor', 'hand2')`) introduces severe UX regressions because child widgets inherit the cursor if they don't explicitly define one, leading to the entire page incorrectly displaying a hand cursor.
**Action:** Only apply cursors to specific interactive leaf widgets (e.g., `TButton`, `TCheckbutton`) via the Tk option database, and use `pointinghand` for macOS to prevent crashes on Linux.
