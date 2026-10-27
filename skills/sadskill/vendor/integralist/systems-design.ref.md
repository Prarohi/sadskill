# Reference: Systems Design & Clean Architecture (Integralist)

> **Source**: [Integralist/agent-skills](https://github.com/Integralist/agent-skills) (Apache-2.0 License)  
> **Status**: Neutralized Reference for `sadskill`

---

## 🏛️ Systems Design Principles

1. **Explicit Domain Boundaries**:
   - Keep business logic decoupled from transport protocols (HTTP/REST, gRPC, GraphQL) and persistence mechanisms (PostgreSQL, Redis).
   - Use dependency injection to pass storage adapters to domain services.
2. **Resilience & Fallback Strategies**:
   - Wrap external network calls with configurable timeouts and circuit breakers.
   - Implement exponential backoff with jitter for retries on transient network errors.
   - Never let an external service outage crash internal critical paths; provide graceful fallback degradation.
3. **Observability by Design**:
   - Structured JSON logging with correlation IDs passed through all async hops.
   - Emit high-cardinality metrics (latency distributions, error counts) at boundaries.
