# Reference: Test-Driven Development (Matt Pocock)

> Source: `mattpocock` (MIT License) · Neutralized Reference

---

## 🧪 Red-Green-Refactor Loop

1. **Write the Failing Test (Red)**:
   - Create a test reproducing the requirement, bug, or boundary case.
   - Run the test runner to prove it fails for the exact reason expected.
2. **Implement Minimal Fix (Green)**:
   - Write the simplest possible code to satisfy the test.
   - Do not anticipate hypothetical future features during this step.
3. **Refactor**:
   - Clean up structure, names, and duplication while ensuring all tests continue passing.
4. **Integration Testing Seams**:
   - Prefer tests that exercise real boundaries over mocking out internal functions. Mock external third-party network services, never your own internal domain models.
