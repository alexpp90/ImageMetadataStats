## 2024-08-08 - Added accessible switch items
**Learning:** Using `Modifier.clickable` with an internal Switch widget makes the list item confusing for screen readers, announcing as a button instead of a toggle.
**Action:** Always use `Modifier.toggleable(role = Role.Switch)` with `Modifier.semantics(mergeDescendants = true) {}` on the parent row and set `onCheckedChange = null` on the child Switch widget to create a single cohesive accessible component.
