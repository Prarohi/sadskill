# Reference: Improving Codebase Architecture (Matt Pocock Patterns)

Origin: Matt Pocock Architectural Refactoring  
License: MIT  

## Diagnostic Smells

1. **Circular Dependencies**: Module A imports Module B, which imports Module A. Break cycles by introducing a shared interface or third domain module.
2. **God Files**: Modules exceeding 800+ lines that manage state, UI, networking, and storage simultaneously. Split along business capabilities, not technical layers (e.g. `billing/` instead of `controllers/`).
3. **Leaky Abstractions**: Callers must know about the underlying database engine, socket connection, or specific serialization format to use a service.
4. **Pass-Through Modules**: Modules that only forward method calls to a child dependency without transforming, validating, or enriching data.

## Refactoring Strategy

- **Small Verifiable Steps**: Never rewrite an entire architecture in a single mega-commit.
- **Strangler Fig Pattern**: Introduce the new architecture alongside the old one. Gradually migrate call sites one by one with green tests. Deprecate and remove old code only after 100% of traffic uses the new implementation.
