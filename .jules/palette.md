## 2024-08-16 - Tkinter Interactive Hover Feedback
**Learning:** Tkinter `ttk` styles silently ignore `cursor` configuration because it is a widget-level option, often leading to a lack of visual feedback (no pointer cursor) when hovering over interactive elements.
**Action:** Apply hand cursors globally to interactive elements (like buttons and checkboxes) using the Tk option database (e.g., `root.option_add('*TButton.cursor', 'hand2')`).
