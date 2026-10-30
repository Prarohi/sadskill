# Security Policy

## Supported Versions

| Version | Maintenance status |
| ------- | ------------------ |
| 0.5.0 source candidate | Unreleased; not a published security-update channel |
| 0.4.0 | Unpublished draft; not a published security-update channel |
| 0.3.x | Latest published release line; report suspected vulnerabilities privately |
| 0.2.x and earlier | Legacy releases; upgrade recommended |

This table distinguishes released artifacts from source candidates. It does **not**
promise a fixed support lifetime or that every report can be patched
immediately. Confirm the latest published release on GitHub before upgrading.

---

## Reporting a Vulnerability

Security is a foundational pillar of `sadskill`. If you discover a vulnerability—including security guardrail bypasses, credential exposure risks, or malicious payload execution vectors:

1. **Do NOT open a public GitHub issue.**
2. Send an advisory report via GitHub Private Security Advisories:
   - Navigate to the [Security Advisories](https://github.com/Prarohi/sadskill/security/advisories) tab on GitHub.
   - Click **"Report a vulnerability"**.
3. Include:
   - A description of the issue and affected files/protocols.
   - Steps to reproduce or a minimal proof-of-concept (PoC).
   - Any proposed remediation diff.

We aim to acknowledge security reports promptly and coordinate a tested fix with the reporter before public disclosure. Response time and remediation depend on the severity and available maintainers.
