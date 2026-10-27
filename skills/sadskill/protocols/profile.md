# Protocol: Local User Profile (`~/.sadskill/profile.md`)

`sadskill` separates shared project standards from personal developer preferences through the Local Profile mechanism.

---

## 🔒 Isolation Guarantees

1. **Repository Neutrality**:
   - Zero machine paths, usernames, or developer-specific quirks are committed to any project repository.
   - The repository operates on strict, neutral industry standards by default.

2. **Workstation Location**:
   - Local preferences reside strictly in `~/.sadskill/profile.md` on the developer's workstation.
   - This file is never committed or pushed to any repository.

---

## ⚙️ How Agents Evaluate Profiles

1. **Dynamic Check**:
   - At the beginning of a session, check if `~/.sadskill/profile.md` exists.
   - If present: Load and apply personal guidelines (e.g. preferred communication language, keybindings, favorite test frameworks).
   - If absent: Proceed strictly with neutral repository defaults.
2. **Conflict Resolution**:
   - Explicit project standards (such as ESLint configs, CONTRIBUTING.md, or `.sad/decisions.md`) always take precedence over personal workstation profiles.
