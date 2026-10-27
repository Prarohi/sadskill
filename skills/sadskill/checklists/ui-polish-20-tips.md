# Checklist: UI Polish 20-Tips

A curated checklist for polishing web interfaces from functional to world-class.

---

## 📐 Layout & Spacing
1. **Consistent Spacing Scale**: Use a strict 4px/8px geometric scale (4, 8, 12, 16, 24, 32, 48, 64px). Never use arbitrary ad-hoc margins.
2. **Alignment Rigor**: Align elements along a shared visual baseline or axis. Misalignment by even 2px registers as subconscious sloppiness.
3. **Breathing Room**: When in doubt, increase whitespace around dense elements. Crowded interfaces feel stressful.
4. **Content-Aware Containers**: Wrap dynamic text containers with reasonable `max-w-*` to prevent awkward single-word wrapping or mile-long lines.

## 🔤 Typography & Contrast
5. **Optical Tracking**: Apply negative tracking (`-0.02em` to `-0.04em`) to large display headers; apply neutral or slight positive tracking (`+0.01em` to `+0.02em`) to small uppercase badges.
6. **Proportional Leading**: Headlines need tight line-height (`1.1` to `1.25`); body copy needs comfortable line-height (`1.5` to `1.7`).
7. **Color Hierarchy**: Restrict pure black (`#000000`) and pure white (`#ffffff`). Use rich neutrals with subtle hue undertones.
8. **Text Muting**: Use muted colors for secondary metadata, but maintain at least 4.5:1 WCAG contrast against the background.

## 🖱️ Interaction & Feedback
9. **Interactive Touch Targets**: Guarantee minimum 44×44px hit areas on all mobile tap targets.
10. **Immediate Hover & Active States**: Provide instantaneous visual feedback on `:hover`, `:focus-visible`, and `:active`.
11. **Focus Ring Visibility**: Always style `:focus-visible` with a distinct, accessible offset ring. Never leave `outline: none` uncompensated.
12. **Cursor Accuracy**: Use `cursor: pointer` only on interactive buttons and links. Never on unclickable cards or non-interactive containers.

## ⚡ Motion & Polish
13. **Subtle Transitions**: Keep standard UI state transitions snappy (150ms–200ms) with `cubic-bezier(0.16, 1, 0.3, 1)`.
14. **Motion Preference**: Always honor `@media (prefers-reduced-motion: reduce)`.
15. **Skeleton Shimmers**: Replace jarring layout pop-ins with proportional skeleton placeholders to prevent CLS.
16. **Smooth Scrolling**: Ensure scrollable containers avoid abrupt snap jumps unless explicitly requested.

## 🛡️ Edge Cases & Empty States
17. **Empty State Design**: Every list, table, or feed must render an intentional, helpful empty state with a call to action.
18. **Long String Truncation**: Gracefully handle unexpected 100-character strings with `truncate` or intentional wrapping.
19. **Error Messaging**: Position field validation errors adjacent to the offending input, paired with accessible ARIA descriptions.
20. **Dark Mode Cohesion**: Ensure borders, drop shadows, and glassmorphic surfaces adjust their opacity and blend modes across color schemes.
