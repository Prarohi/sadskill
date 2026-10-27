# Reference: Waza Engineering Craftsmanship

Origin: tw93/Waza  
License: MIT  

## The Craft of Autonomous Engineering

1. **Extreme Thoroughness**:
   - Never leave loose ends. If you create a new configuration option, update the documentation, the validation schema, and the test suite in the same pass.
2. **Minimalist Dependencies**:
   - Do not pull in heavy external packages for simple utility logic that can be written in 10 lines of standard library code.
3. **Calm Tooling**:
   - Build tools that work reliably and silently when successful, reporting only actionable errors when failures occur.
