# Reference: Animation Fundamentals & Performance

Origin: Animation & Motion Community  
License: MIT  

## Performance Rules for Web Motion

1. **Only Animate Composite Properties**:
   - Strictly animate `transform` (`translate`, `scale`, `rotate`) and `opacity`.
   - Never animate layout properties like `width`, `height`, `top`, `left`, `margin`, or `padding`, which trigger costly layout reflows and browser paint cycles.
2. **GPU Acceleration**:
   - Use `will-change: transform` sparingly on active animating elements to promote them to their own compositor layer. Remove `will-change` once animation concludes.
3. **Reduced Motion Compliance**:
   - Always wrap CSS animations and JavaScript motion drivers in prefers-reduced-motion checks:
     ```css
     @media (prefers-reduced-motion: reduce) {
       *, ::before, ::after {
         animation-duration: 0.01ms !important;
         animation-iteration-count: 1 !important;
         transition-duration: 0.01ms !important;
       }
     }
     ```
