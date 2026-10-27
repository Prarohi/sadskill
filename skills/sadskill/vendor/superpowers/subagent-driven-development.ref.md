# Reference: Subagent-Driven Development (Superpowers Patterns)

Origin: obra/superpowers  
License: MIT  

## Delegation & Coordination Rules

When breaking a complex project across multiple subagents:
1. **Clear Task Boundaries**:
   - Assign distinct, non-overlapping file sets to each worker to prevent merge conflicts.
2. **Authoritative Specification**:
   - Provide each subagent with the exact feature spec and verification criteria.
3. **No Interim Chitchat**:
   - Workers should execute their assignment independently, run local tests, and deliver a comprehensive final report upon completion.
4. **Independent Review**:
   - Have a separate advisor or review agent verify the code against edge cases and tests before approving changes.
