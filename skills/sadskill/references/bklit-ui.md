# Bklit UI chart tasks

Use for charts and data visualization when Bklit UI is requested or fits a real visualization need. Inspect existing charts, design tokens, framework, package manager, and component ownership first. Reuse a suitable existing chart before adding another library.

## Choose an integration that fits the stack

For React projects, check current Bklit installation/component docs and the existing shadcn configuration. Add only the needed registry component. Review generated source and the entire dependency/lockfile diff, including utilities installed transitively; use the project's package manager and reproducible dependency versions.

For vanilla HTML/CSS/JS, retain that stack. Adapt useful visual ideas with existing CSS, SVG or Canvas patterns rather than introducing React/shadcn to display a chart. Apply the project's own component and asset rules.

Use Context7 for `@bklit/ui` when available. If it is unavailable, use the official documentation directly; continue without changing MCP configuration or installing a new plugin.

## Verify the chart's meaning and behavior

- Preserve units, timezones, scales and denominators. Distinguish zero, missing data, partial data and loading; avoid invented metrics or implying precision the data does not support.
- Check empty, single-point, constant, negative and large-value series as applicable, along with long labels and narrow screens. Keep axes, legends and tooltips readable without clipping or misleading truncation.
- Provide keyboard-accessible information and a text summary or table alternative. Color alone must not convey the only distinction; honor reduced-motion preferences.
- Verify real rendering at relevant sizes and inspect the console. Report code-only inspection as such when browser access is unavailable. Measure bundle/rendering impact when the new chart creates a concrete performance concern.

## Official sources

Reviewed 2026-10-28; refresh component APIs before implementation.

- [Bklit UI documentation](https://ui.bklit.com/docs)
- [Installation and registry](https://ui.bklit.com/docs/installation)
- [Design workflow](../modes/design.md)
