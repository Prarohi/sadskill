# Reference: OWASP API Security Top 10

Origin: OWASP Foundation  
License: CC-BY-SA 4.0  

## API Security Checklist

1. **API1: Broken Object Level Authorization (BOLA)**:
   - Always validate that the logged-in user owns or has delegated access to the specific requested ID (`/api/invoices/:id`).
2. **API2: Broken Authentication**:
   - Issue signed JWTs with short expiry (15m) paired with refresh token rotation.
3. **API3: Broken Object Property Level Authorization (Mass Assignment)**:
   - Use strict DTOs / schemas. Never pass raw `req.body` directly into database update methods (e.g. preventing users from setting `is_admin: true`).
4. **API4: Unrestricted Resource Consumption**:
   - Enforce pagination limits (maximum `limit=100`) and rate limiting per IP / API key.
5. **API5: Broken Function Level Authorization**:
   - Protect administrative endpoints (`/api/admin/*`) with server-side role checks.
