# Reference: Scroll Animations (GSAP & Framer Motion)

Origin: Animation & Motion Community  
License: MIT  

## Scroll-Linked Animation Patterns

1. **Framer Motion (`useScroll`, `useTransform`)**:
   - Tie transforms directly to scroll progress:
     ```tsx
     const { scrollYProgress } = useScroll({ target: containerRef, offset: ['start end', 'end start'] });
     const opacity = useTransform(scrollYProgress, [0, 0.5, 1], [0, 1, 0]);
     const scale = useTransform(scrollYProgress, [0, 0.5, 1], [0.8, 1, 0.9]);
     ```
2. **GSAP ScrollTrigger**:
   - Scrubbing: Set `scrub: 1` to smooth out scroll velocity jumps.
   - Pinning: Pin hero sections cleanly while child elements reveal. Always set `anticipatePin: 1` to eliminate pin stutter on fast trackpads.
3. **Mobile Restraint**:
   - Disable complex scroll-pinning on mobile viewports (<768px) where address bar resizing causes erratic layout recalculations.
