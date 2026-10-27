# Reference: Security Review & Checklist (ECC Standards)

Origin: ECC Community  
License: MIT  

## Security Review Verification Steps

1. **Secrets Management**:
   - Verify zero hardcoded API keys, bearer tokens, or passwords in source code.
   - Confirm all secrets are loaded strictly from environment variables.
   - Ensure local env files (`.env`, `.env.local`) are excluded in `.gitignore`.
2. **Input Validation**:
   - Validate and sanitize all user input before passing to SQL queries, shell commands, or HTML templates.
3. **Session & Token Safety**:
   - Store session identifiers in `HttpOnly`, `Secure` cookies with `SameSite=Lax` or `SameSite=Strict`.
   - Invalidate server-side sessions on logout.
4. **Third-Party API Hygiene**:
   - Handle provider timeouts and errors gracefully without leaking raw internal tokens or private stack traces to clients.
