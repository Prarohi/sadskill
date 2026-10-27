# Reference: Frontend Design Principles (Anthropic Guidelines)

Origin: anthropics/skills  
License: Apache-2.0  

## Directives for Polished UI

1. **Avoid Template Aesthetic**:
   - Do not default to boilerplate templates with three generic pricing cards and a generic purple gradient hero.
   - Ground visual metaphors in the specific domain (e.g. developer tools should feel precise, terminal-like; consumer apps should feel warm, physical).
2. **Accessible Form Layouts**:
   - Group related form fields logically with `<fieldset>` and `<legend>`.
   - Provide persistent label elements linked via `htmlFor`.
   - Announce validation errors via `aria-describedby` and `aria-live`.
3. **Responsive Typography**:
   - Use fluid font sizing (`clamp()`) for headlines so text scales smoothly between mobile phones and wide desktop monitors.
