# Vendor Index: Situation to Reference Mapping

Use this index to look up targeted engineering and design patterns. Only load the specific reference required for the active sub-task to conserve context tokens.

| Situation / Task | Domain | Reference Document | Key Takeaway |
|---|---|---|---|
| **Architecting new modules or refactoring** | Architecture | [mattpocock/codebase-design.ref.md](mattpocock/codebase-design.ref.md) | Deep modules: small interfaces hiding high internal complexity. |
| **Test-driven feature development** | Testing | [mattpocock/tdd.ref.md](mattpocock/tdd.ref.md) | Red-green-refactor; test behavior, not implementation details. |
| **Designing complex domain types** | Type Systems | [mattpocock/domain-modeling.ref.md](mattpocock/domain-modeling.ref.md) | Make illegal states unrepresentable using tagged unions. |
| **Reviewing pull requests or diffs** | Code Review | [mattpocock/code-review.ref.md](mattpocock/code-review.ref.md) | Dual-axis review: standards compliance + specification fidelity. |
| **Refactoring large messy codebases** | Architecture | [mattpocock/improve-architecture.ref.md](mattpocock/improve-architecture.ref.md) | Break cycles, eliminate god files, use Strangler Fig pattern. |
| **Brainstorming multiple solutions** | Ideation | [superpowers/brainstorming.ref.md](superpowers/brainstorming.ref.md) | Contrast 2–3 viable paths before writing code. |
| **Authoring detailed specs** | Planning | [superpowers/writing-plans.ref.md](superpowers/writing-plans.ref.md) | Explicit file paths, symbol signatures, discrete testable phases. |
| **Orchestrating agent sub-tasks** | Multi-Agent | [superpowers/subagent-driven-development.ref.md](superpowers/subagent-driven-development.ref.md) | Non-overlapping worker file sets, independent verification. |
| **General coding & debugging discipline** | Core Engineering | [karpathy/guidelines.ref.md](karpathy/guidelines.ref.md) | Small verifiable changes, simplicity over cleverness, inspect data. |
| **Eliminating AI writing tropes** | Communication | [humanizer/humanizer-core.ref.md](humanizer/humanizer-core.ref.md) | Ban AI buzzwords, answer first, direct and natural tone. |
| **Structuring technical output** | Reader UX | [attention-span/attention-span.ref.md](attention-span/attention-span.ref.md) | Inverted pyramid, high-density bullets, scanability. |
| **Enforcing UI quality floor** | Frontend Quality | [impeccable/craft-floor.ref.md](impeccable/craft-floor.ref.md) | 44px hit targets, zero layout shift, contrast, reduced-motion. |
| **Classifying UI surfaces** | Frontend UX | [impeccable/modes.ref.md](impeccable/modes.ref.md) | Persuade vs Operate vs Read vs Experience. |
| **Fine-tuning typography & spacing** | Design Tokens | [impeccable/typography-and-spacing.ref.md](impeccable/typography-and-spacing.ref.md) | Optical tracking, proportional leading, 8px base grid. |
| **Aesthetic direction & anti-slop** | Creative Direction | [taste/taste-vocabulary.ref.md](taste/taste-vocabulary.ref.md) | Coherent visual world, avoid generic AI styling tropes. |
| **Accessible component architecture** | Components | [shadcn/component-patterns.ref.md](shadcn/component-patterns.ref.md) | Radix primitives, compound composition, Tailwind tokens. |
| **Modern responsive web design** | Frontend UX | [vercel/web-design-guidelines.ref.md](vercel/web-design-guidelines.ref.md) | Subtle elevation, mobile-first breakpoints, optimistic UI. |
| **React & Next.js App Router** | Full Stack | [vercel/react-next-patterns.ref.md](vercel/react-next-patterns.ref.md) | Server Components default, streaming Suspense, Server Actions. |
| **High-craft frontend design** | Frontend UX | [anthropic/frontend-design.ref.md](anthropic/frontend-design.ref.md) | Purposeful layouts, accessible forms, fluid typography. |
| **PostgreSQL schema & indexing** | Database | [supabase/postgres-best-practices.ref.md](supabase/postgres-best-practices.ref.md) | Strict data types, composite and partial indexes, EXPLAIN. |
| **Row Level Security & Migrations** | Database Security | [supabase/rls-and-migrations.ref.md](supabase/rls-and-migrations.ref.md) | Zero-trust RLS policies, reversible UP/DOWN migrations. |
| **Auditing web application vulnerabilities** | Security | [owasp/owasp-top-10.ref.md](owasp/owasp-top-10.ref.md) | Top 10 risks: injection, broken auth, SSRF, misconfig. |
| **Hardening API endpoints** | API Security | [owasp/api-security.ref.md](owasp/api-security.ref.md) | BOLA/IDOR prevention, mass assignment, rate limiting. |
| **Onboarding to unfamiliar repos** | Reconnaissance | [ecc/codebase-onboarding.ref.md](ecc/codebase-onboarding.ref.md) | Manifests, entry points, directory map, test health. |
| **Auditing repo assets & dead weight** | Code Health | [ecc/repo-scan.ref.md](ecc/repo-scan.ref.md) | First-party vs vendor, dead code, monorepo boundaries. |
| **Reviewing secrets & sensitive features** | Security | [ecc/security-review.ref.md](ecc/security-review.ref.md) | Secret hygiene, input validation, secure cookies. |
| **Fluid spring & physical motion** | Animation | [animation/apple-design.ref.md](animation/apple-design.ref.md) | Physical springs, interruptible gestures, spatial continuity. |
| **Performant web animation** | Animation | [animation/animate-fundamentals.ref.md](animation/animate-fundamentals.ref.md) | Composite properties only (transform/opacity), reduced motion. |
| **Scroll-driven storytelling** | Motion | [animation/gsap-framer-scroll.ref.md](animation/gsap-framer-scroll.ref.md) | GSAP ScrollTrigger scrubbing, Framer Motion useScroll. |
| **Modern HTML & CSS native features** | Web Standards | [modern-web/modern-web-guidance.ref.md](modern-web/modern-web-guidance.ref.md) | `<dialog>`, Popover API, `:has()`, Container Queries. |
| **Auditing accessibility & screen readers** | Accessibility | [modern-web/a11y-debugging.ref.md](modern-web/a11y-debugging.ref.md) | Heading hierarchy, keyboard traversal, ARIA labels. |
| **Writing high-converting landing pages** | Marketing | [marketing/landing-page-copy.ref.md](marketing/landing-page-copy.ref.md) | Above-the-fold hero, benefits over features, friction reducers. |
| **Edge compute, D1 & KV storage** | Edge & Serverless | [cloudflare/edge-workers-d1.ref.md](cloudflare/edge-workers-d1.ref.md) | V8 isolates, distributed D1 SQLite, edge caching. |
| **Structuring issues & task tracking** | Workflow | [linear/linear-issue-workflow.ref.md](linear/linear-issue-workflow.ref.md) | Actionable titles, explicit acceptance criteria, atomic scope. |
| **Automating iOS simulator testing** | Mobile QA | [ios/ios-simulator.ref.md](ios/ios-simulator.ref.md) | `xcrun simctl` automation, touch targets, safe area insets. |
| **Craftsmanship & minimalist tooling** | Engineering Culture | [waza/craftsmanship.ref.md](waza/craftsmanship.ref.md) | Extreme thoroughness, minimal dependencies, calm tooling. |
| **Multi-model consensus & debate** | Architecture | [octopus/multi-model-consensus.ref.md](octopus/multi-model-consensus.ref.md) | Adversarial red-teaming for high blast-radius trade-offs. |
| **Agent discipline & verification proof** | Verification | [octopus/discipline-mode.ref.md](octopus/discipline-mode.ref.md) | Zero-trust terminal execution proof before declaring fix. |
| **Core Web Vitals & real performance** | Frontend Performance | [addyosmani/web-vitals.ref.md](addyosmani/web-vitals.ref.md) | LCP < 2.5s, CLS < 0.1, INP < 200ms, preloads & yield. |
| **Systems design & fault tolerance** | Distributed Systems | [integralist/systems-design.ref.md](integralist/systems-design.ref.md) | Decoupled domain boundaries, circuit breakers, jitter retries. |
