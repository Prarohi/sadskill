# Reference: Accessibility (a11y) Debugging & Standards

Origin: Chrome DevTools & a11y Community  
License: MIT  

## Accessibility Verification Matrix

1. **Semantic Hierarchy**:
   - Exactly one `<h1>` per page. Heading levels (`<h2>`, `<h3>`, `<h4>`) must never skip levels.
2. **Keyboard Traversal**:
   - Can the entire page be navigated, read, and operated using only `Tab`, `Shift+Tab`, `Enter`, `Space`, and `Arrow` keys?
   - Focus must never get trapped inside an off-screen menu or hidden drawer.
3. **Screen Reader Attributes**:
   - Buttons without text (e.g. icon buttons) must specify `aria-label="Description"`.
   - Form inputs must link to `<label for="id">` or have `aria-labelledby`.
   - Decorative icons must have `aria-hidden="true"`.
4. **Color Contrast Ratios**:
   - Regular text: 4.5:1 minimum against background.
   - Large text (>18pt bold or >24pt regular): 3:1 minimum.
