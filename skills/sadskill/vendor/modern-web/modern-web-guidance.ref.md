# Reference: Modern Web Guidance & Native Web APIs

Origin: Modern Web Guidance Community  
License: MIT  

## Prefer Native Web Platform Primitives

1. **Native Dialogs (`<dialog>`)**:
   - Use `<dialog>` and `.showModal()` instead of building custom modal trap loops.
   - Provides native `::backdrop`, escape key handling, and top-layer rendering out of the box.
2. **Native Popover API (`popover="auto"`)**:
   - Use native HTML `popover` for tooltips, menus, and dropdowns without third-party positioning libraries.
3. **Modern CSS Selectors**:
   - `:has()` for parent styling based on child state (`form:has(:user-invalid) button { opacity: 0.5; }`).
   - `:focus-visible` for keyboard-only focus rings.
   - Container Queries (`@container`) over Media Queries for reusable component-driven responsive layouts.
