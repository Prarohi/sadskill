# Reference: Cloudflare Edge Workers, D1 & KV Patterns

Origin: Cloudflare Skills  
License: MIT / Apache-2.0  

## Edge Compute & Distributed Storage

1. **Edge Workers (V8 Isolates)**:
   - Near-zero cold start latency (<5ms).
   - Stateless compute; bind state to KV, D1 (distributed SQLite), R2 (object storage), or Hyperdrive.
2. **D1 Relational Storage**:
   - Run standard SQL queries at the edge with automatic replication.
   - Use batch statements (`db.batch([...])`) to execute multiple queries in a single roundtrip.
3. **Cache API at the Edge**:
   - Cache responses using `caches.default` with explicit `s-maxage` to serve content directly from Cloudflare PoPs without hitting origin servers.
