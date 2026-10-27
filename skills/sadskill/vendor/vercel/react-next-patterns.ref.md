# Reference: React & Next.js Patterns (Vercel Standards)

Origin: vercel-labs/agent-skills  
License: Apache-2.0  

## App Router Architecture

1. **Server Components by Default**:
   - Keep data fetching on the server. Do not add `'use client'` unless the component requires browser APIs (event handlers, `useState`, `useEffect`).
2. **Streaming & Suspense**:
   - Wrap slow asynchronous sections in `<Suspense fallback={<Skeleton />}>` to deliver fast First Contentful Paint (FCP).
3. **Server Actions for Mutations**:
   - Handle form submissions with Server Actions.
   - Revalidate cache tags immediately after mutation (`revalidateTag` or `revalidatePath`).
4. **Bundle Optimization**:
   - Lazy load heavy client libraries (e.g. charts, rich text editors) using `next/dynamic`.
