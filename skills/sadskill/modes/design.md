# Mode: `/sad-design`

Design mode crafts accessible, production-grade, and brand-adaptive user interfaces. It enforces rigorous engineering craft across typography, layout, interaction, and accessibility, avoiding generic AI tropes while respecting the host application's existing design system.

---

## 🎨 The Adaptive Craft Floor Philosophy

1. **Brand-Adaptive, Not Style-Dogmatic**:
   - Never impose a generic or foreign aesthetic onto an existing application.
   - Inspect the codebase first: discover Tailwind configs, CSS variables, design tokens, component libraries (Shadcn, Radix, MUI), and existing brand guidelines.
   - Zero-Lift hover rules and click compression are **craft defaults and anti-slop protections** designed to prevent floating-card jitter, not inflexible universal laws. If an established project utilizes subtle elevation, respect its design tokens.
2. **Eight Facets of Interface Quality**:
   Every interface is evaluated across eight distinct dimensions:
   1. **Visual Hierarchy**: Clear focal point, intentional scan paths, distinct primary vs secondary actions.
   2. **Typography**: Optical sizing, proportional leading (1.4–1.7), controlled line length (55–75 characters), explicit tracking.
   3. **Spatial Rhythm & Layout**: Consistent 4px/8px grid, proportional padding, alignment discipline.
   4. **Responsive Adaptability**: Seamless behavior across mobile (360/390px), tablet (768px), and desktop (1280/1440px) breakpoints; zero horizontal overflow.
   5. **Accessibility (WCAG 2.2 AA)**: Normative contrast compliance, keyboard focus rings, semantic HTML, screen reader labels.
   6. **Interactive Feedback**: Hover, focus-visible, active micro-states, disabled indicators.
   7. **State Completeness**: Graceful handling of empty states, loading skeletons, partial data, and error boundaries.
   8. **Motion Purpose**: Fluid, interruptible transitions with reduced-motion alternatives.
3. **Objective Standards vs. Subjective Taste**:
   - Explicitly separate normative accessibility failures (e.g. text contrast < 4.5:1, missing focus rings) from aesthetic critiques (e.g. color palette balance, corner radius preferences).
4. **Truthful Visual Verification & Tooling Disclosure**:
   - When the agent host provides visual tooling (e.g. Chrome DevTools MCP, Puppeteer, browser preview), perform real visual inspection and capture screenshots.
   - When browser tools are unavailable, explicitly qualify guidance as code-level CSS/HTML inspection and **never claim a screenshot or live browser test occurred**.

---

## 🛠️ Execution Pipeline

### Phase 1: Brand & Design Memory Discovery
1. **Inspect Existing Tokens**:
   - Check `tailwind.config.*`, CSS custom properties (`:root`), font declarations, and component primitives.
2. **Audit Project Design Memory (`.sad/design-memory.md`)**:
   - Review past approved colors, font choices, component rules, and rejected visual anti-patterns.
3. **Workstation Profile (`~/.sadskill/profile.md`)**:
   - Apply any personal designer preferences if present.
4. **External Research (When Authorized)**:
   - If permitted under [protocols/research.md](../protocols/research.md), consult design systems or inspiration references.

### Phase 2: Surface Mode Classification
Identify the primary surface mode to tailor density and tone:
- **Persuade**: Landing pages, conversion funnels, launch banners. Expressive typography, bold hierarchy, strong visual anchors.
- **Operate**: Dashboards, data tables, control panels, developer settings. Scanability, compact spatial rhythm, keyboard shortcuts, predictable layout.
- **Read**: Documentation, long-form content, technical guides. Comfortable line length (55–75ch), comfortable line height (1.5–1.7), low contrast eye fatigue.
- **Experience**: Creative showcases, interactive portfolios, product unveilings. Fluid motion, rich media, tactile sensory polish.

### Phase 3: Core Craft Floor Invariants

Before shipping frontend UI code, verify these baseline craft standards:
1. **Interactive Target Sizing**:
   - Minimum 24×24px per WCAG 2.2 SC 2.5.8; preferred 44×44px for primary touch controls and mobile navigation.
2. **Anti-Slop Hover & Interaction Floor**:
   - **Zero-Lift Default**: Card and container hover `translateY(-...)` float is prohibited as a style default (preventing jittery AI floating cards); prefer border highlight, subtle contrast shift, or `scale(0.97)` click micro-compression.
   - **Legitimate Transitions Permitted**: Positional animations for slide-in sheets, drawers, toasts, accordions, and tooltips are fully supported with purposeful timing.
3. **Layout Stability (CLS < 0.1)**:
   - Reserve explicit dimensions for images, videos, and dynamic data slots using aspect ratios and skeleton loaders.
4. **Contrast & Color Semantics (WCAG 2.2 AA)**:
   - Minimum 4.5:1 contrast ratio for normal body text (SC 1.4.3).
   - Minimum 3:1 contrast ratio for large text (>= 18pt or bold >= 14pt) and interface components/borders (SC 1.4.11).
5. **Focus & Keyboard Navigation**:
   - Never set `outline: none` without providing an unobstructed `:focus-visible` ring with at least 3:1 contrast against adjacent backgrounds.
6. **Motion Safety**:
   - Wrap all CSS keyframe animations, Framer Motion transitions, and GSAP timelines in `@media (prefers-reduced-motion: reduce)`.
7. **Complete State Coverage**:
   - Never leave empty states as blank white cards; provide an icon, explanatory heading, and clear call-to-action.
   - Provide skeleton loaders that mirror actual content geometry.

### Phase 4: Self-Critique & Checklist Review
Audit the rendered component against:
- [checklists/ui-polish-20-tips.md](../checklists/ui-polish-20-tips.md)
- [checklists/site-production.md](../checklists/site-production.md)

### Phase 5: Design Memory Logging
Log new approved design tokens to `.sad/design-memory.md`:
- Palette tokens (background, surface, primary, border, text).
- Font pairings and scale ratios.
- Custom component patterns and user feedback.

---

## 🔗 Vendor Synergies
- **Chart and data-visualization work**: Load [Bklit UI guidance](../references/bklit-ui.md) when relevant; preserve the current framework and verify data meaning and accessibility.
- **Impeccable**: [impeccable/craft-floor.ref.md](../vendor/impeccable/craft-floor.ref.md) and [impeccable/modes.ref.md](../vendor/impeccable/modes.ref.md).
- **Taste & Aesthetic**: [taste/taste-vocabulary.ref.md](../vendor/taste/taste-vocabulary.ref.md).
- **Component Patterns**: [shadcn/component-patterns.ref.md](../vendor/shadcn/component-patterns.ref.md).
- **Vercel Best Practices**: [vercel/web-design-guidelines.ref.md](../vendor/vercel/web-design-guidelines.ref.md).
- **Motion Polish**: [animation/apple-design.ref.md](../vendor/animation/apple-design.ref.md).
