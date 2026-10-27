# Security Audit Report: [Project Name]

- **Date**: YYYY-MM-DD
- **Target File**: `.sad/reports/security-YYYY-MM-DD.md`
- **Auditor**: `sadskill` `/sad-sec`
- **Scope**: Web, APIs, Authentication, Secrets, Dependencies

---

## 1. Executive Summary

| Severity | Count | Status |
|---|---|---|
| Critical | 0 | Action Required |
| High | 0 | Action Required |
| Medium | 0 | Review Needed |
| Low / Info | 0 | Informational |

---

## 2. Findings & Vulnerability Details

### [SEC-01] [Finding Title]
- **Severity**: Critical | High | Medium | Low
- **OWASP Category**: [e.g. A01:2021 - Broken Access Control]
- **Location**: `path/to/file.ext:line_number`
- **Description**: [Technical description of vulnerability and impact]
- **Proof of Concept / Evidence**:
  ```text
  [Code snippet or request/response trace]
  ```
- **Remediation**:
  [Concrete code fix or architectural correction]

---

## 3. Dependency Audit Summary
```text
[Output from npm audit, pip audit, cargo audit, or govulncheck]
```

---

## 4. Security Headers & Cookie Audit
- [ ] `Content-Security-Policy`
- [ ] `Strict-Transport-Security` (HSTS)
- [ ] `X-Content-Type-Options: nosniff`
- [ ] `X-Frame-Options: DENY`
- [ ] Cookies flagged with `Secure`, `HttpOnly`, `SameSite`

---

## 5. Remediation Plan & Approval Gate
- **Immediate Fixes**: [Ordered list of steps]
- **Approval Status**: Awaiting user confirmation before code changes.
