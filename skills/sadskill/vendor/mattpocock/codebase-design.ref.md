# Reference: Codebase Design & Deep Modules (Matt Pocock)

> Source: `mattpocock` (MIT License) · Neutralized Reference

---

## 🏛️ Deep Modules

- **Deep vs Shallow**: A deep module provides a simple, narrow interface that hides substantial implementation complexity. A shallow module has an interface that is almost as complex as its implementation.
- **Seams**: Position interfaces where natural boundaries occur (e.g. database access, external HTTP APIs, state serialization).
- **Encapsulation**: Internal data structures and helper utilities should never leak into external callers. Keep call sites clean and uncluttered.
- **AI Navigability**: Clear module boundaries allow coding agents to read and modify isolated units without having to pull the entire repository into context.
