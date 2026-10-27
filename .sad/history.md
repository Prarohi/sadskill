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

### [2026-10-28] v0.2.1 Competitive Hardening & Benchmark Harness
- **Cursor YAML Fix**: Quoted globs (`globs: "*"`) in generated `.cursor/rules/sadskill.mdc` to eliminate YAML ScannerError.
- **Packaged Hook**: Placed executable guardrail inside skill payload at `skills/sadskill/hooks/git-guardrail.sh` with robust command tokenization (preventing bypasses like `git -C <path>`, chained commands `&&`, and force refspecs `+main`).
- **Claude Hook Auto-Wiring**: Added automatic `.claude/hooks/git-guardrail.sh` deployment in `install.sh`.
- **Zero-Lift Nuance**: Refined Zero-Lift hover rule to explicitly permit slide-in drawers, sheets, tooltips, and toasts while banning generic card-hover float jitter.
- **Independent Evidence Verifier**: Added `scripts/verify-evidence.py` to validate `.sad/evidence/*.json` records against git state.
- **Reproducible Benchmark Suite**: Added `benchmarks/tasks.json` and `benchmarks/runner.py` with 100% pass rate.
- **Node Matrix CI**: Added Node 20 & 22 matrix in `.github/workflows/ci.yml`.

### [2026-10-28] v0.3.0 Technical Audit Resolution & Hardened Verifier
- **Safe Evidence Verifier**: Eliminated `shell=True` arbitrary command execution in `scripts/verify-evidence.py`; enforced strict project path containment (rejecting path traversal `..` and external symlinks); added per-command timeout and safe argv dispatch.
- **Truthful Provenance States**: Defined exact verification states (`reported`, `schema_valid`, `retested`, `ci_attested`, `failed`) and stopped unqualified `VERIFIED` claims on unexecuted self-reports.
- **Contract & Policy Smoke Suite**: Hardened `benchmarks/runner.py` with registry dispatch, immediate failure on unknown task IDs, dynamic pass rate computation, and evaluation of declared criteria.
- **Real Behavioral Fixture**: Added `benchmarks/fixtures/tenant-isolation/` with actual behavioral unit tests and grader (`grader.py`).
- **Installation Manifest & Reversibility**: Added `~/.sadskill/install-manifest.json` tracking installed files and backups, along with `uninstall.sh --restore-previous` for automated restoration.
- **Defense-in-Depth Safety Model**: Clarified hook boundaries (`protocols/safety.md`), distinguishing Claude PreToolUse from Git pre-push and documenting lifecycle states (`HOOK_AVAILABLE`, `HOOK_REGISTERED`, `HOOK_ACTIVE`).
- **Version Alignment**: Unified `v0.3.0` across `SKILL.md`, `README.md`, `install.sh`, and `uninstall.sh`.
- **Expanded Verification Suite**: Expanded `scripts/verify.py` to 87 automated tests covering evidence safety, path traversal, shell chaining rejection, and fixture graders.
