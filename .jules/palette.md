## 2026-07-28 - Explicit Mapping of Focus Colors in Tkinter
**Learning:** Even when `focuscolor` is configured on a `ttk.Style` for a specific widget, it may still not correctly highlight during keyboard navigation in themes like 'clam' unless `focuscolor` is also explicitly mapped using `style.map('Widget', focuscolor=[('focus', color)])`. This was observed on multiple widgets (`TButton`, `Primary.TButton`, `TNotebook.Tab`, `TCombobox`, `TEntry`).
**Action:** Always verify keyboard accessibility by checking `ttk.Style().map('Widget').get('focuscolor')` and explicitly include `focuscolor` in the `style.map` function alongside other state-driven properties.

## 2026-07-28 - Interactive Cursor for Native Tkinter UI Widget Support
**Learning:** By default, Tkinter UI elements like buttons, checkboxes, and radio buttons do not change the mouse cursor to a recognizable interactive state (e.g. the hand cursor). This provides no affordance to the user that elements are clickable.
**Action:** Apply cursor="hand2" globally in Tkinter applications using `root.option_add("*TButton.cursor", "hand2")` (along with checkboxes, radiobuttons, etc.) to ensure interactive elements afford clickability. Wait to apply this setting *after* creating the root Tk window.
