# sad-design

Execute the `design` workflow of `sadskill` on target UI surface: $ARGUMENTS

## Instructions
1. **Locate sadskill Configuration**:
   - Check local workspace: `./skills/sadskill/SKILL.md` (or global `~/.claude/skills/sadskill/SKILL.md`).
   - Check `.sad/design-memory.md` to prevent repeating rejected aesthetic anti-patterns.
   - Check local profile `~/.sadskill/profile.md` for personal design preferences.
2. **Design Craft Floor & Anti-Slop Rules**:
   - Touch targets >= 44×44px, zero layout shift (CLS < 0.1), WCAG AA contrast (4.5:1 text, 3:1 UI).
   - Zero-Lift Hover Rule: `translateY(-...)` on card/button hover is banned (preventing generic floating-card jitter); use `scale(0.97)` micro-compression on click. (Legitimate positioning and entrance transitions like slide-in drawers, sheets, toasts, and tooltips remain permitted).
   - Preserve natural image aspect ratios; never crop avatars or products into distorted shapes.
   - Classify surface mode: *Persuade* (landing), *Operate* (dashboard/settings), *Read* (docs), or *Experience* (creative).
3. **Execution & Polish**:
   - Compose accessible primitives (Radix/Shadcn style) with CSS variables.
   - Critique against 20 UI polish tips (layout, typography, contrast, motion safety).
   - Record approved palettes, typography, and lessons in `.sad/design-memory.md`.
