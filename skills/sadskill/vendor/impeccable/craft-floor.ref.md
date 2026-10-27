# Reference: The Craft Floor (Impeccable)

> Source: `pbakaus/impeccable` (MIT License) · Neutralized Reference

---

## 🛠️ The Non-Negotiable Craft Floor

1. **Touch Targets**: 44×44px minimum for any clickable or interactive element on mobile screens.
2. **Layout Shift Prevention**: Every image, video, and dynamic container must have defined dimensions or aspect-ratio reservations to guarantee CLS = 0.
3. **Contrast Compliance**: WCAG AA standards (4.5:1 for body copy, 3:1 for large display text and interface bounds).
4. **Accessible Focus**: Always style `:focus-visible` with high-contrast outlines and clear offsets.
5. **Reduced Motion**: All CSS transitions and animations must be conditionally wrapped in `@media (prefers-reduced-motion: reduce)`.
