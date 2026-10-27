# Reference: Component Patterns (shadcn/ui Standards)

Origin: shadcn/ui  
License: MIT  

## Primitives & Design Architecture

1. **Unstyled Accessible Primitives (Radix UI)**:
   - Separate accessibility, keyboard focus, and ARIA state logic from visual styling.
   - Modals, dropdowns, popovers, and accordions must handle Tab, Escape, and focus restoration automatically.
2. **Tailwind CSS Token Mapping**:
   - Use CSS custom properties for theme colors (`bg-background`, `text-foreground`, `border-border`, `ring-ring`).
   - Enables seamless dark mode switching without manual class toggles.
3. **Compound Component Composition**:
   - Build components as composable primitives rather than monolithic components with 50 configuration props:
     ```tsx
     <Card>
       <CardHeader>
         <CardTitle>Usage Metrics</CardTitle>
         <CardDescription>Real-time compute cycles</CardDescription>
       </CardHeader>
       <CardContent>...</CardContent>
     </Card>
     ```
4. **CVA (Class Variance Authority)**:
   - Manage component variants, sizes, and states cleanly using `cva` to ensure type safety.
