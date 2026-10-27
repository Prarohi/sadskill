# Project History: `sadskill`

Chronological record of high-level accomplishments, architectural transitions, and major releases.

---

### [2026-10-27] v0.1.0 Initial Release
- Unified 5 core workflows under one roof: `/sad-plan`, `/sad-design`, `/sad-backend`, `/sad-sec`, and `/sad-analyze`.
- Implemented single discoverable skill constraint via YAML frontmatter neutralization (`*.ref.md`).
- Vendored 36 curated reference patterns across Matt Pocock, Superpowers, Impeccable, Taste, Shadcn, Vercel, Supabase, OWASP, and ECC.
- Authored initial multi-agent installer `install.sh` and verification test suite `scripts/verify.py`.

### [2026-10-28] v0.1.1 Hardening & Safety Expansion
- Vendored Claude-Octopus (`/octo:debate` and `/octo:discipline`), Addy Osmani (Web Vitals), and Integralist (Systems Design).
- Added destructive action guardrails protocol (`protocols/safety.md`).
- Safe query performance analysis in `/sad-backend` (`EXPLAIN (BUFFERS)` for write queries).

### [2026-10-28] v0.2.0 The Verified Agent Engineering System
- **skills.sh standard**: Promoted `npx skills add sadafbabu/sadskill` as primary installation standard.
- **Adaptive 2-Tier Planning**: Replaced rigid single-tier planning with Tier 1 (Surgical, minimal tokens) and Tier 2 (Deep Architectural Spec).
- **Dual-Record Verification Evidence**: Added `protocols/evidence.md` with structured logs in `.sad/evidence/` and 3-line terminal execution proof in chat.
- **Self-Contained Commands**: Rewrote `commands/claude/` and `commands/codex/` with `$ARGUMENTS` and embedded fallback instructions.
- **Executable Guardrails**: Added `scripts/git-guardrail.sh` hook intercepting destructive Git/SQL commands.
- **Cursor Target Packaging**: Added `--target <dir>` support in `install.sh` and generated valid `.cursor/rules/sadskill.mdc`.
- **Community Suite & CI**: Added `.github/workflows/ci.yml`, issue templates, and `SECURITY.md`.
