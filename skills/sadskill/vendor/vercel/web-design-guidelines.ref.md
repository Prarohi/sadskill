# Reference: Web Design Guidelines (Vercel Standards)

Origin: vercel-labs/agent-skills  
License: Apache-2.0  

## Modern Web Design Foundations

1. **Subtle Elevation & Borders**:
   - Prefer fine borders (`1px solid hsl(var(--border))`) over heavy box-shadows.
   - Use subtle backdrop blurs (`backdrop-blur-md bg-background/80`) for sticky headers and navigation bars.
2. **Speed as a Design Attribute**:
   - The interface must feel instantaneous.
   - Use optimistic UI updates for form submissions, likes, and state toggles before network responses return.
   - Skeleton states must match the exact dimensions of incoming content to prevent layout shifts.
3. **Responsive Breakpoints**:
   - Mobile-first CSS: base styles apply to mobile; scale up with `sm:`, `md:`, `lg:`, `xl:`.
   - Never allow horizontal scroll on mobile viewports (`overflow-x: hidden` on viewport boundaries).
