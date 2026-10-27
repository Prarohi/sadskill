# Protocol: Safe MCP Tool Usage

Modern autonomous agents interface with external environments through the Model Context Protocol (MCP). `sadskill` establishes boundaries to ensure secure and predictable MCP usage.

---

## 🛡️ Usage Principles

1. **Leverage Available Tools**:
   - Utilize active MCP servers (e.g. database inspectors, browser automation, filesystem servers) when executing relevant workflows (`/sad-backend`, `/sad-sec`, `/sad-design`).
2. **Read-First Verification**:
   - Query schema definitions and runtime states via MCP read tools before generating migrations or tests.
3. **Configuration Immutability**:
   - Agents must NEVER modify `claude_desktop_config.json`, `codex_config.json`, or any MCP configuration file automatically.
   - Do not attempt automated installation of unverified MCP packages or external plugins without explicit user authorization.
4. **Credential Safety**:
   - Never pass plaintext API keys or credentials as arguments to MCP tools. MCP servers must source secrets from the local host environment.
