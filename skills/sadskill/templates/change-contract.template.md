# Change Contract: `{{CONTRACT_ID}}`

> **Status:** `{{STATUS}}` (planned | executing | verified | partial | blocked)  
> **Risk Tier:** `{{RISK_TIER}}` (T0 | T1 | T2) — {{RISK_RATIONALE}}  
> **Created At:** `{{CREATED_AT}}`

---

## 1. Intent & Concrete Outcome
{{INTENT}}

## 2. Scope & Files Touched
- `{{TARGET_FILE_1}}` (MODIFY/CREATE)
- `{{TARGET_FILE_2}}` (TEST)

## 3. Risk Assessment & Tiering
- **Tier:** `{{RISK_TIER}}`
- **Blast Radius:** `{{BLAST_RADIUS}}`
- **Reversibility:** `{{REVERSIBILITY}}`
- **Data Sensitivity:** `{{DATA_SENSITIVITY}}`
- **Rationale:** `{{RISK_RATIONALE}}`

## 4. Contract-First AST Signatures
```typescript
// Explicit signatures of touched and created functions/interfaces
export interface {{INTERFACE_NAME}} {
  {{PROPERTY}}: {{TYPE}};
}

export function {{FUNCTION_NAME}}(arg: {{ARG_TYPE}}): {{RETURN_TYPE}};
```

## 5. Explicit Constraints & Invariants
- {{CONSTRAINT_1}}
- {{CONSTRAINT_2}}

## 6. Key Assumptions & Boundary Conditions
- {{ASSUMPTION_1}}
- {{ASSUMPTION_2}}

## 7. Verification Harness
| Check | Command | Expected Outcome | Verification Status |
|---|---|---|---|
| Automated Tests | `{{TEST_COMMAND}}` | Exit code 0, 0 failures | `pending` |
| Type Check | `{{TYPECHECK_COMMAND}}` | 0 errors | `pending` |

## 8. Rollback & Reversal Strategy
- **Strategy:** {{ROLLBACK_STRATEGY}} (e.g. `git stash pop`, `down.sql`, rollback branch)
- **Reversibility Assessment:** {{REVERSIBILITY}} (fully_reversible | data_migration_backup_required)
- **Step 1:** {{RECOVERY_STEP_1}}
