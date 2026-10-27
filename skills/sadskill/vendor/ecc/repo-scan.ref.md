# Reference: Repository Asset & Dependency Scan (ECC Standards)

Origin: ECC Community  
License: MIT  

## Source Code Asset Audit

1. **First-Party vs Third-Party Code**:
   - Differentiate first-party application logic from embedded vendor libraries, generated code, and vendored packages.
2. **Dead Weight Detection**:
   - Detect orphaned files, unreferenced image assets, abandoned prototypes, and stale migration scripts.
3. **Monorepo Boundary Audit**:
   - Verify that workspace packages maintain clear dependency graphs without circular imports or unlisted workspace dependencies.
