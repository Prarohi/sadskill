# Reference: Code Review (Matt Pocock Patterns)

Origin: Matt Pocock Dual-Axis Code Review  
License: MIT  

## Dual-Axis Review Method

Review pull requests and code changes along two independent axes:

### Axis 1: Standards Compliance
- Does the code adhere to established repo conventions and linting rules?
- Are variables, functions, and types clearly and descriptively named?
- Are error conditions handled explicitly rather than swallowed?
- Does the diff maintain consistency with surrounding code?

### Axis 2: Specification Fidelity
- Does the code actually implement the requirements specified in the issue/ticket?
- Does it address the edge cases mentioned in the spec?
- Are there unintended side effects or regressions introduced in unrelated modules?
- Does the PR introduce unrequested scope creep or premature abstractions?
