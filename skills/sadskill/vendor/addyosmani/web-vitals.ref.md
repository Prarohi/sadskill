# Reference: Core Web Vitals & Real-World Performance (Addy Osmani)

> **Source**: [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) (Apache-2.0 License)  
> **Status**: Neutralized Reference for `sadskill`

---

## ⚡ The Three Core Metrics

1. **LCP (Largest Contentful Paint)**: Target `< 2.5s`
   - Preload hero images: `<link rel="preload" as="image" href="..." fetchpriority="high">`.
   - Avoid client-side JS rendering for above-the-fold content; server-render critical markup.
   - Serve modern image formats (WebP, AVIF) with explicit `width` and `height` dimensions.
2. **CLS (Cumulative Layout Shift)**: Target `< 0.1`
   - Reserve space for images, embeds, and dynamic widgets using `aspect-ratio` or CSS min-height placeholders.
   - Never inject content above existing rendered elements without user interaction.
   - Use `font-display: optional` or size-adjusted fallback fonts to prevent layout shift during web font swaps.
3. **INP (Interaction to Next Paint)**: Target `< 200ms`
   - Break up long JavaScript tasks (> 50ms) using `scheduler.yield()` or `requestAnimationFrame`.
   - Debounce expensive operations and avoid layout thrashing (interleaving DOM reads and writes).
   - Use CSS animations for UI feedback rather than heavy JS animation loops.
