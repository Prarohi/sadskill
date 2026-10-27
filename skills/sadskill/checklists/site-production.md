# Checklist: Production Site Launch Readiness

A comprehensive pre-flight checklist for web applications preparing for production release.

---

## 🚀 Performance & Core Web Vitals
- [ ] **LCP (Largest Contentful Paint)**: Hero images and critical above-the-fold content render within 2.5 seconds.
- [ ] **CLS (Cumulative Layout Shift)**: Layout shift score remains under 0.1 across dynamic loads and image renders.
- [ ] **INP (Interaction to Next Paint)**: User interactions respond within 200ms without blocking main thread loops.
- [ ] **Image Optimization**: WebP/AVIF formats utilized with explicit `width` and `height` dimensions.
- [ ] **Bundle Size**: Tree-shaking verified and unnecessary large libraries removed.

---

## ♿ Accessibility (WCAG 2.1 AA)
- [ ] **Keyboard Navigability**: Full application navigable via `Tab`, `Shift+Tab`, `Enter`, `Escape`, and arrow keys.
- [ ] **Semantic Landmarks**: Proper usage of `<header>`, `<nav>`, `<main>`, `<section>`, and `<footer>`.
- [ ] **Color Contrast**: 4.5:1 ratio for normal body copy; 3:1 for large headers and interface boundaries.
- [ ] **Screen Reader Support**: All meaningful images have descriptive `alt` attributes; icon buttons have `aria-label`.

---

## 📱 Responsive & Cross-Browser
- [ ] **Viewport Scaling**: Valid `<meta name="viewport" content="width=device-width, initial-scale=1.0">`.
- [ ] **Breakpoints**: Tested at 320px (mobile small), 768px (tablet), 1024px (desktop), and 1440px (wide screens).
- [ ] **Mobile Interactions**: Tap targets meet minimum 44×44px hit dimensions.

---

## 🔒 Security & Environment
- [ ] **Environment Separation**: No staging or local API keys deployed to production builds.
- [ ] **Headers**: HSTS, CSP, X-Frame-Options, and Referrer-Policy configured.
- [ ] **Error Handling**: Production error pages (404, 500) do not expose internal stack traces.
