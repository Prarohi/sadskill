# Mode: `/sad-design`

Design mode crafts production-grade, accessible, and aesthetically distinctive web and mobile interfaces while preventing generic AI styling tropes.

---

## 🎨 Execution Pipeline

### Phase 1: Design Memory Audit & Context
1. Read `.sad/design-memory.md` if present:
   - Note approved color palettes, font pairings, and component tokens.
   - Strictly avoid styles, layouts, or components explicitly rejected in past reviews.
2. If `~/.sadskill/profile.md` contains design guidance, apply those defaults.
3. Consult [protocols/research.md](../protocols/research.md) if authorized for external creative inspiration and visual references.

### Phase 2: Surface Mode Classification
Identify the surface's primary mode:
- **Persuade**: Landing pages, conversion funnels, launch announcements. Expressive typography, bold hierarchy, strong focal points.
- **Operate**: Dashboards, control planes, data tables, settings. Scanability, dense information hierarchy, keyboard navigation, predictable layout.
- **Read**: Technical documentation, long-form articles. Optimal line length (55–75 characters), comfortable line-height (1.5–1.7), low eye fatigue.
- **Experience**: Showcases, creative portfolios, product unveilings. Fluid motion, interactive canvas, high sensory polish.

### Phase 3: Craft Floor Requirements (Non-Negotiable)
Before shipping any UI code, verify these accessibility and craft requirements:
1. **Touch & Click Targets**: Preferred 44×44px interactive target area (while meeting WCAG 2.2 SC 2.5.8 minimum 24×24px requirement).
2. **Zero-Lift Hover Rule**: Card/button hover `translateY(-...)` float is prohibited as a style floor (preventing generic AI floating-card jitter); use `scale(0.97)` micro-compression on click. (Legitimate entrance and positional transitions like slide-in drawers, bottom sheets, toasts, and tooltips remain permitted).
3. **Layout Stability**: Maintain Cumulative Layout Shift (CLS < 0.1) on hover, active states, modal toggles, or dynamic data loading. Always reserve space for images and skeleton loaders.
4. **Contrast & Readability**: Minimum 4.5:1 contrast ratio for body text; 3:1 for large headers and interface components (WCAG 2.2 AA SC 1.4.3 & SC 1.4.11).
5. **Motion Safety**: Wrap all animations and transitions in `@media (prefers-reduced-motion: reduce)`.
6. **Keyboard & Focus**: Never set `outline: none` without providing a distinct `:focus-visible` ring.
7. **Optical Typography**: Set explicit tracking (e.g. tighter for large titles, looser for uppercase labels) and proportional leading.

### Phase 4: Self-Critique & Polish
Review the created UI against [checklists/ui-polish-20-tips.md](../checklists/ui-polish-20-tips.md) and [checklists/site-production.md](../checklists/site-production.md).

### Phase 5: Design Memory Logging
Log key design decisions to `.sad/design-memory.md`:
- Palette tokens (background, surface, primary, accent, border, text).
- Font stack and scale.
- Notable custom components and user feedback.

---

## 🔗 Vendor Synergies
- **Impeccable**: [impeccable/craft-floor.ref.md](../vendor/impeccable/craft-floor.ref.md) and [impeccable/modes.ref.md](../vendor/impeccable/modes.ref.md).
- **Taste & Aesthetic**: [taste/taste-vocabulary.ref.md](../vendor/taste/taste-vocabulary.ref.md).
- **Component Patterns**: [shadcn/component-patterns.ref.md](../vendor/shadcn/component-patterns.ref.md).
- **Vercel Best Practices**: [vercel/web-design-guidelines.ref.md](../vendor/vercel/web-design-guidelines.ref.md).
- **Motion Polish**: [animation/apple-design.ref.md](../vendor/animation/apple-design.ref.md) and [animation/animate-fundamentals.ref.md](../vendor/animation/animate-fundamentals.ref.md).
