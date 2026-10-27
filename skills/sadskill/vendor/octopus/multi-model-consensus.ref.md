# Reference: Multi-Model Consensus & Adversarial Debate (Claude-Octopus)

> **Source**: [nyldn/claude-octopus](https://github.com/nyldn/claude-octopus) (MIT License)  
> **Status**: Neutralized Reference for `sadskill`

---

## 🐙 The Consensus Protocol (`/octo:debate`)

When an architectural decision carries high blast radius (schema changes, breaking API modifications, state management refactors), single-model agents suffer from confirmation bias.

### 1. The Adversarial Persona Pattern
1. **The Proposer**: Drafts the optimal implementation plan with proposed abstractions and file mutations.
2. **The Red-Team Critic**: Actively looks for failure modes:
   - What happens when network latency spikes to 3000ms?
   - What happens under concurrent write collisions?
   - How does this break backwards compatibility for existing mobile or API clients?
   - Is this introducing unnecessary state complexity or premature abstraction?
3. **The Synthesizer (Lead Architect)**:
   - Resolves conflicts by comparing actual trade-offs.
   - Strips speculative features.
   - Commits to the simplest design that satisfies the invariants.

---

## 🛠️ Application in `/sad-plan`

- In **Phase 2 (Grilling on Ambiguity)**, invoke consensus evaluation before presenting options to the user.
- If two designs have equal merit, present both with explicit pros/cons and a default recommendation so the user can approve with a single `yes`.
