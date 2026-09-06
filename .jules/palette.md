## 2024-09-06 - Tkinter Cursor Styling
**Learning:** Applying cursors globally to containers like `TNotebook` causes UX regressions because child elements inherit them if not explicitly overridden. Also, `ttk.Style().configure` ignores the cursor property.
**Action:** Apply cursors via `root.option_add` specifically to interactive leaf widgets (`*TButton.cursor`, etc.) and use `pointinghand` instead of `hand2` on macOS.
