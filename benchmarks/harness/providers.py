"""Agent Execution Providers for the C1 Comparative Benchmark Harness.
Supports mock deterministic execution and real agent runners with fail-closed
truthful authentication checks (NOT_EXECUTED_NO_AUTH).
"""

import os
from pathlib import Path
import time


class BaseProvider:
    def __init__(self, name: str):
        self.name = name

    def execute(self, task: dict, condition: str, workspace: Path) -> dict:
        raise NotImplementedError


class MockProvider(BaseProvider):
    """Deterministic offline provider for C1 benchmark testing and CI runs."""
    def __init__(self):
        super().__init__("mock")

    def execute(self, task: dict, condition: str, workspace: Path) -> dict:
        task_id = task["id"]
        t_start = time.time()

        # Metrics default structure
        metrics = {
            "task_id": task_id,
            "condition": condition,
            "provider": "mock",
            "status": "SIMULATED",
            "synthetic": True,
            "input_tokens": None,
            "output_tokens": None,
            "turns": None,
            "tool_calls": None,
            "clarifications_needed": 0,
            "wall_clock_seconds": round(time.time() - t_start + 0.12, 3),
            "evidence_produced": False,
            "notes": f"Mock simulated run under condition={condition}",
        }

        # Apply simulated changes based on condition
        if condition == "sadskill":
            self._apply_sadskill_solution(task_id, workspace)
        elif condition == "plain":
            self._apply_plain_solution(task_id, workspace)
        elif condition == "competitor":
            self._apply_competitor_solution(task_id, workspace)

        return metrics

    def _apply_sadskill_solution(self, task_id: str, workspace: Path):
        # Precise, minimal surgical patches adhering to sadskill contracts
        if task_id == "C1-01":
            (workspace / "src" / "UserProfile.js").write_text(
                "export function getAvatar(user) {\n  return user?.profile?.avatarUrl || '/default-avatar.png';\n}\n",
                encoding="utf-8"
            )
            tf = workspace / "test" / "UserProfile.test.js"
            if tf.exists():
                tf.write_text(
                    tf.read_text(encoding="utf-8") + "\n// Nullable regression\nassert.strictEqual(getAvatar({ profile: null }), '/default-avatar.png');\nassert.strictEqual(getAvatar({ profile: undefined }), '/default-avatar.png');\n",
                    encoding="utf-8"
                )
        elif task_id == "C1-02":
            (workspace / "src" / "paginate.js").write_text(
                "export function paginate(items, page, pageSize) {\n  const start = (page - 1) * pageSize;\n  return items.slice(start, start + pageSize);\n}\n",
                encoding="utf-8"
            )
        elif task_id == "C1-03":
            (workspace / "src" / "DataFetcher.js").write_text(
                "export class DataFetcher {\n  constructor() { this.latestData = null; this.latestId = 0; }\n  async fetchData(queryFn) {\n    const requestId = ++this.latestId;\n    const data = await queryFn();\n    if (requestId === this.latestId) this.latestData = data;\n    return this.latestData;\n  }\n}\n",
                encoding="utf-8"
            )
        elif task_id == "C1-04":
            (workspace / "index.js").write_text(
                "const utils = { format: (s) => s.trim() };\nexport { utils };\nexport default utils;\n",
                encoding="utf-8"
            )
            (workspace / "package.json").write_text(
                '{"name":"test-pkg","private":true,"type":"module","main":"./index.cjs",'
                '"exports":{".":{"import":"./index.js","require":"./index.cjs"}}}\n',
                encoding="utf-8"
            )
        elif task_id == "C1-05":
            (workspace / "src" / "documentService.js").write_text(
                "export function getDocument(db, tenantId, docId) {\n  return db.find(d => d.id === docId && d.tenantId === tenantId) || null;\n}\n",
                encoding="utf-8"
            )
        elif task_id == "C1-06":
            migration = workspace / "migrations" / "001_rls.sql"
            migration.write_text(migration.read_text(encoding="utf-8") + """\nALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON documents
  FOR ALL
  USING (tenant_id = current_setting('sadskill.tenant_id', true)::UUID)
  WITH CHECK (tenant_id = current_setting('sadskill.tenant_id', true)::UUID);
""",
                encoding="utf-8"
            )
        elif task_id == "C1-07":
            m_dir = workspace / "migrations"
            (m_dir / "01_expand_up.sql").write_text("""ALTER TABLE users ADD COLUMN mobile_number text;
UPDATE users SET mobile_number = phone;
CREATE OR REPLACE FUNCTION sync_users_phone_mobile() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.phone IS NOT NULL AND NEW.mobile_number IS NULL THEN NEW.mobile_number := NEW.phone;
    ELSIF NEW.mobile_number IS NOT NULL AND NEW.phone IS NULL THEN NEW.phone := NEW.mobile_number;
    END IF;
  ELSIF NEW.phone IS DISTINCT FROM OLD.phone THEN NEW.mobile_number := NEW.phone;
  ELSIF NEW.mobile_number IS DISTINCT FROM OLD.mobile_number THEN NEW.phone := NEW.mobile_number;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER sync_users_phone_mobile BEFORE INSERT OR UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION sync_users_phone_mobile();
""", encoding="utf-8")
            (m_dir / "01_expand_down.sql").write_text("""DROP TRIGGER IF EXISTS sync_users_phone_mobile ON users;
DROP FUNCTION IF EXISTS sync_users_phone_mobile();
ALTER TABLE users DROP COLUMN mobile_number;
""", encoding="utf-8")
            (m_dir / "02_contract_up.sql").write_text("""DROP TRIGGER IF EXISTS sync_users_phone_mobile ON users;
DROP FUNCTION IF EXISTS sync_users_phone_mobile();
ALTER TABLE users DROP COLUMN phone;
""", encoding="utf-8")
            (m_dir / "02_contract_down.sql").write_text("""ALTER TABLE users ADD COLUMN phone text;
UPDATE users SET phone = mobile_number;
ALTER TABLE users ALTER COLUMN phone SET NOT NULL;
""", encoding="utf-8")
        elif task_id == "C1-08":
            (workspace / "src" / "styles.css").write_text(
                """.container {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}
pre {
  overflow-x: auto;
  overflow-wrap: break-word;
  white-space: pre-wrap;
}
""",
                encoding="utf-8"
            )
        elif task_id == "C1-09":
            (workspace / "src" / "Modal.js").write_text(
                """export function initModal(el) {
  const opener = document.activeElement;
  el.setAttribute('role', 'dialog');
  el.setAttribute('aria-modal', 'true');
  el.setAttribute('aria-hidden', 'false');
  el.style.display = 'block';
  el.hidden = false;
  const controls = () => Array.from(el.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'));
  const first = () => controls()[0] || el;
  const last = () => controls().at(-1) || el;
  first().focus();
  const onKey = event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      el.style.display = 'none';
      el.setAttribute('aria-hidden', 'true');
      document.removeEventListener('keydown', onKey);
      opener?.focus();
    } else if (event.key === 'Tab' && controls().length) {
      if (event.shiftKey && document.activeElement === first()) {
        event.preventDefault(); last().focus();
      } else if (!event.shiftKey && document.activeElement === last()) {
        event.preventDefault(); first().focus();
      }
    }
  };
  document.addEventListener('keydown', onKey);
}
""",
                encoding="utf-8"
            )
        elif task_id == "C1-10":
            (workspace / "src" / "types.js").write_text(
                "export const ORDER_STATUS = { PENDING: 'PENDING' };\n", encoding="utf-8"
            )
            (workspace / "src" / "PaymentService.js").write_text(
                "export function processPayment(amount) { return { success: true, amount }; }\n",
                encoding="utf-8"
            )
            (workspace / "src" / "OrderService.js").write_text(
                "import { processPayment } from './PaymentService.js';\nexport function createOrder(data) { return processPayment(data.amount); }\n",
                encoding="utf-8"
            )
        elif task_id == "C1-11":
            (workspace / "scripts").mkdir(parents=True, exist_ok=True)
            source = Path(__file__).resolve().parents[2] / "scripts" / "git-guardrail.sh"
            (workspace / "scripts" / "git-guardrail.sh").write_bytes(source.read_bytes())
        elif task_id == "C1-12":
            (workspace / "scripts" / "sad_memory.py").write_text("""#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
from pathlib import Path

def append(root, prefix, count):
    root = Path(root)
    sad = root / '.sad'
    events = sad / 'events' / 'events.jsonl'
    events.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(sad / '.lock', os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        fd = os.open(events, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            for index in range(count):
                data = (json.dumps({'event_id': f'{prefix}-{index}', 'type': 'custom'}) + '\\n').encode()
                os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    write = sub.add_parser('append')
    write.add_argument('--root', required=True, type=Path)
    write.add_argument('--prefix', required=True)
    write.add_argument('--count', required=True, type=int)
    args = parser.parse_args()
    append(args.root, args.prefix, args.count)
""", encoding="utf-8")

        # Produce evidence record in sadskill mode
        ev_dir = workspace / ".sad" / "mock-artifacts"
        ev_dir.mkdir(parents=True, exist_ok=True)
        (ev_dir / f"mock-evidence-{task_id}.json").write_text(
            f'{{"task_slug": "{task_id}", "status": "SIMULATED_NOT_EVIDENCE"}}\n',
            encoding="utf-8"
        )

    def _apply_plain_solution(self, task_id: str, workspace: Path):
        # Plain solution: often fixes simple bugs, but misses edge cases or security
        if task_id == "C1-01":
            (workspace / "src" / "UserProfile.js").write_text(
                "export function getAvatar(user) {\n  return user?.profile?.avatarUrl || '/default-avatar.png';\n}\n",
                encoding="utf-8"
            )
        elif task_id == "C1-02":
            (workspace / "src" / "paginate.js").write_text(
                "export function paginate(items, page, pageSize) {\n  const start = (page - 1) * pageSize;\n  return items.slice(start, start + pageSize);\n}\n",
                encoding="utf-8"
            )
        # For C1-06 (RLS), plain LLM typically forgets FORCE ROW LEVEL SECURITY:
        elif task_id == "C1-06":
            (workspace / "migrations" / "001_rls.sql").write_text(
                "ALTER TABLE documents ENABLE ROW LEVEL SECURITY;\nCREATE POLICY p ON documents USING (true);\n",
                encoding="utf-8"
            )

    def _apply_competitor_solution(self, task_id: str, workspace: Path):
        # Competitor: heavier token usage, often generates large verbose scaffolding
        self._apply_sadskill_solution(task_id, workspace)


class RealAgentProvider(BaseProvider):
    """Real execution requires both explicit opt-in and external isolation."""

    def __init__(self, provider_name="codex", *, live=False, isolated=False, model=None):
        super().__init__(provider_name)
        self.live = live
        self.isolated = isolated
        self.model = model

    def execute(self, task, condition, workspace):
        common = {"task_id": task["id"], "provider": self.name, "condition": condition}
        if not self.live:
            return {**common, "status": "NOT_EXECUTED_DISABLED",
                    "reason": "Real provider disabled unless --live is specified"}
        if not self.isolated:
            return {**common, "status": "NOT_EXECUTED_ISOLATION_REQUIRED",
                    "reason": "Run the entire harness in an external disposable sandbox"}
        if not self.model:
            return {**common, "status": "NOT_EXECUTED_MODEL_REQUIRED",
                    "reason": "Supply an exact model ID via --model"}
        from benchmarks.harness.live_cli import execute_live
        return execute_live(task, condition, workspace, self.name, self.model)
