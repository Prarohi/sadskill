# Reference: OWASP Top 10 Web Application Security Risks

Origin: OWASP Foundation (Updated for OWASP Top 10:2025 Standard)  
Official Standard: https://top10.owasp.org/2025/  
License: CC-BY-SA 4.0  

## Web Application Vulnerability Vectors (OWASP Top 10:2025)

1. **A01: Broken Access Control**:
   - Failing to enforce least privilege; IDOR permitting access to unauthorized records; CORS misconfiguration.
   - Mitigation: Enforce server-side record ownership checks on every request.
2. **A02: Cryptographic Failures**:
   - Transmitting sensitive data over HTTP; storing passwords in plain text or with weak hashing (MD5/SHA1); hardcoded crypto keys.
   - Mitigation: TLS 1.3, Argon2id/bcrypt password hashing, automated secret rotation.
3. **A03: Injection & Input Validation Failures**:
   - SQL, NoSQL, OS command, and template injection.
   - Mitigation: Use parameterized queries/ORMs; validate and sanitize all inputs.
4. **A04: Insecure Design**:
   - Missing business logic rate limits, credential stuffing susceptibility.
   - Mitigation: Threat modeling during planning phase (`/sad-plan`).
5. **A05: Security Misconfiguration**:
   - Default accounts/passwords, unhandled error stack traces sent to client, unnecessary open ports.
6. **A06: Vulnerable and Outdated Components**:
   - Unpatched third-party npm/pip packages containing known CVEs.
7. **A07: Identification and Authentication Failures**:
   - Permitting weak passwords, lack of brute force protection, session fixation.
8. **A08: Software and Data Integrity Failures**:
   - Deserialization of untrusted data, unverified plugins/dependencies, CI/CD supply chain risks.
9. **A09: Security Logging and Monitoring Failures**:
   - Insufficient auditing of security-critical actions (login, password change, billing edits).
10. **A10: Server-Side Request Forgery (SSRF)**:
    - Fetching arbitrary user-supplied URLs without restricting private IP ranges (`127.0.0.1`, `10.0.0.0/8`, `169.254.169.254`).

*(Note: Distinct from the OWASP API Security Top 10 which addresses Broken Object Level Authorization, Broken Authentication, Broken Object Property Level Authorization, and Unrestricted Resource Consumption).*
