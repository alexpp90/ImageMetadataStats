## 2024-05-28 - [Accessible Compose List Items]
**Learning:** In Jetpack Compose, having a clickable Row that contains a Switch or RadioButton can create confusing duplicate focus targets for screen readers.
**Action:** When building list items with interactive controls (like Switch or RadioButton), apply `toggleable` or `selectable` to the parent Row with the appropriate `Role` (e.g. `Role.Switch`), and `Modifier.semantics(mergeDescendants = true) {}`. Then, set the inner control's event handler (e.g., `onCheckedChange`) to `null` so it doesn't act as a separate focusable element.
