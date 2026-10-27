# Reference: Domain Modeling (Matt Pocock Patterns)

Origin: Matt Pocock Domain Modeling Vocabulary  
License: MIT  

## Core Principles

1. **Ubiquitous Language**:
   - Establish a shared vocabulary between technical implementation and business concepts.
   - Maintain a project `GLOSSARY.md` if domain terms conflict or carry non-obvious meanings.
2. **Make Illegal States Unrepresentable**:
   - Use tagged unions / algebraic data types so invalid domain states cannot be constructed.
   - Example (TypeScript):
     ```typescript
     // Bad: Can be loading and have an error and data simultaneously
     type State = { loading: boolean; error?: string; data?: User };

     // Good: Mutually exclusive domain states
     type State =
       | { status: 'idle' }
       | { status: 'loading' }
       | { status: 'success'; data: User }
       | { status: 'error'; error: Error };
     ```
3. **Parse, Don't Validate**:
   - Validate data at system boundaries (incoming HTTP, file reads, user input) and transform into strongly typed domain objects.
   - Downstream domain code should never have to re-check if input is valid.
