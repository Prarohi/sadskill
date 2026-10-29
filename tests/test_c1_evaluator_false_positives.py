"""Adversarial fixtures must not pass C1 merely by containing keywords/files."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from benchmarks.harness.evaluators import (
    EVALUATORS,
    EvaluationUnavailable,
    _validate_guardrail_regression_script,
)
from benchmarks.harness.tasks import C1_TASKS


class C1EvaluatorFalsePositiveTests(unittest.TestCase):
    def assert_rejected(self, task_id, files):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            if "package.json" not in files:
                (root / "package.json").write_text('{"private":true,"type":"module"}\n', encoding="utf-8")
            try:
                result = EVALUATORS[task_id](root)
            except EvaluationUnavailable as exc:
                # CI must exercise every grader. Local environments may lack
                # optional browser/PostgreSQL runtimes, but must report a skip.
                if os.environ.get("SADSKILL_REQUIRE_C1_GRADERS") == "1":
                    self.fail(f"Required {task_id} grader unavailable in CI: {exc}")
                self.skipTest(f"{task_id} grader unavailable: {exc}")
        self.assertFalse(result[0], f"{task_id} accepted an invalid implementation: {result[3]}")
        return result

    def test_c1_01_missing_required_regression_test_is_not_a_pass(self):
        self.assert_rejected("C1-01", {
            "src/UserProfile.js": "export function getAvatar(user) { return user?.profile?.avatarUrl ?? '/default-avatar.png'; }\n",
        })

    def test_c1_01_comments_and_unrelated_assertions_are_not_a_regression_test(self):
        self.assert_rejected("C1-01", {
            "src/UserProfile.js": "export function getAvatar(user) { return user?.profile?.avatarUrl ?? '/default-avatar.png'; }\n",
            "test/UserProfile.test.js": """import assert from 'node:assert';
import { getAvatar } from '../src/UserProfile.js';
// TODO assert null and undefined profiles with getAvatar
assert.strictEqual(1, 1);
""",
        })

    def test_c1_02_correct_keywords_do_not_replace_pagination_behavior(self):
        self.assert_rejected("C1-02", {
            "src/paginate.js": "export function paginate(items, page, pageSize) { return items; }\n",
        })

    def test_c1_03_request_id_comment_does_not_prove_stale_result_protection(self):
        self.assert_rejected("C1-03", {
            "src/DataFetcher.js": """export class DataFetcher {
  constructor() { this.latestData = null; }
  // requestId sequencing should be used here
  async fetchData(queryFn) { const data = await queryFn(); this.latestData = data; return data; }
}
""",
        })

    def test_c1_04_export_reexport_to_missing_module_does_not_pass(self):
        self.assert_rejected("C1-04", {
            "package.json": '{"name":"test-pkg","private":true,"type":"module","main":"./index.cjs","exports":{".":{"import":"./index.js","require":"./index.cjs"}}}\n',
            "index.js": "export { utils } from './missing-utils.js';\n",
            "index.cjs": "module.exports = { format: s => s.trim() };\n",
        })

    def test_c1_05_tenant_parameter_without_tenant_predicate_does_not_pass(self):
        self.assert_rejected("C1-05", {
            "src/documentService.js": """export function getDocument(db, tenantId, docId) {
  return db.find(d => d.id === docId) || null;
}
""",
        })

    def test_c1_06_permissive_rls_policy_is_rejected(self):
        self.assert_rejected("C1-06", {
            "migrations/001_rls.sql": """CREATE TABLE documents (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  content text NOT NULL
);
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents USING (true) WITH CHECK (true);
""",
        })

    def test_c1_06_policy_hardcoded_to_one_tenant_is_rejected(self):
        self.assert_rejected("C1-06", {
            "migrations/001_rls.sql": """CREATE TABLE documents (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  content text NOT NULL
);
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_a_only ON documents
  USING (tenant_id = '10000000-0000-0000-0000-000000000001'::UUID)
  WITH CHECK (tenant_id = '10000000-0000-0000-0000-000000000001'::UUID);
""",
        })

    def test_c1_06_update_that_transfers_ownership_is_rejected(self):
        result = self.assert_rejected("C1-06", {
            "migrations/001_rls.sql": """CREATE TABLE documents (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  content text NOT NULL
);
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_select ON documents FOR SELECT
  USING (tenant_id = current_setting('sadskill.tenant_id', true)::uuid OR current_query() ILIKE '%SET tenant_id%');
CREATE POLICY tenant_insert ON documents FOR INSERT
  WITH CHECK (tenant_id = current_setting('sadskill.tenant_id', true)::uuid);
CREATE POLICY tenant_update ON documents FOR UPDATE
  USING (tenant_id = current_setting('sadskill.tenant_id', true)::uuid)
  WITH CHECK (true);
CREATE POLICY tenant_delete ON documents FOR DELETE
  USING (tenant_id = current_setting('sadskill.tenant_id', true)::uuid);
""",
        })
        self.assertIn("transferred its own document", result[3])

    def test_c1_07_empty_migration_files_do_not_pass(self):
        self.assert_rejected("C1-07", {
            "migrations/01_expand_up.sql": "-- empty\n",
            "migrations/01_expand_down.sql": "-- empty\n",
            "migrations/02_contract_up.sql": "-- empty\n",
            "migrations/02_contract_down.sql": "-- empty\n",
        })

    def test_c1_07_insert_only_dual_write_does_not_pass(self):
        self.assert_rejected("C1-07", {
            "migrations/01_expand_up.sql": """ALTER TABLE users ADD COLUMN mobile_number text;
UPDATE users SET mobile_number = phone;
CREATE OR REPLACE FUNCTION sync_users_phone_mobile() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.phone IS NOT NULL AND NEW.mobile_number IS NULL THEN NEW.mobile_number := NEW.phone;
  ELSIF NEW.mobile_number IS NOT NULL AND NEW.phone IS NULL THEN NEW.phone := NEW.mobile_number;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER sync_users_phone_mobile BEFORE INSERT ON users
FOR EACH ROW EXECUTE FUNCTION sync_users_phone_mobile();
""",
            "migrations/01_expand_down.sql": """DROP TRIGGER IF EXISTS sync_users_phone_mobile ON users;
DROP FUNCTION IF EXISTS sync_users_phone_mobile();
ALTER TABLE users DROP COLUMN mobile_number;
""",
            "migrations/02_contract_up.sql": """DROP TRIGGER IF EXISTS sync_users_phone_mobile ON users;
DROP FUNCTION IF EXISTS sync_users_phone_mobile();
ALTER TABLE users DROP COLUMN phone;
""",
            "migrations/02_contract_down.sql": """ALTER TABLE users ADD COLUMN phone text;
UPDATE users SET phone = mobile_number;
ALTER TABLE users ALTER COLUMN phone SET NOT NULL;
""",
        })

    def test_c1_08_responsive_keywords_outside_broken_selectors_do_not_pass(self):
        self.assert_rejected("C1-08", {
            "src/styles.css": """.container { width: 600px; }
pre { white-space: pre; }
.unrelated { max-width: 100%; word-break: break-word; }
""",
        })

    def test_c1_09_comments_with_a11y_keywords_do_not_pass(self):
        self.assert_rejected("C1-09", {
            "src/Modal.js": """export function initModal(el) {
  // Escape key, role='dialog', aria-modal='true', focus trap
  el.style.display = 'block';
}
""",
        })

    def test_c1_10_double_quoted_cycle_does_not_pass(self):
        self.assert_rejected("C1-10", {
            "src/OrderService.js": 'import { processPayment } from "./PaymentService.js"; export function createOrder(data) { return processPayment(data.amount); }\n',
            "src/PaymentService.js": 'import { getOrder } from "./OrderService.js"; export function processPayment(amount) { return { success: true, amount }; }\n',
            "src/types.js": "export const ORDER_STATUS = { PENDING: 'PENDING' };\n",
        })

    def test_c1_11_missing_workspace_hook_does_not_fall_back_to_product_hook(self):
        self.assert_rejected("C1-11", {
            "scripts/test-bypass.sh": "#!/bin/sh\nexit 0\n",
        })

    def test_c1_11_keywords_in_comments_do_not_make_a_regression_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            regression = root / "scripts" / "test-bypass.sh"
            regression.parent.mkdir()
            regression.write_text(
                "#!/bin/bash\n# env sudo bash -c git reset --hard\nexit 0\n",
                encoding="utf-8",
            )
            reason = _validate_guardrail_regression_script(regression, root)
        self.assertIn("reference control-flow shape", reason)

    def test_c1_11_reference_regression_script_matches_the_static_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            regression = root / "scripts" / "test-bypass.sh"
            regression.parent.mkdir()
            regression.write_text(
                C1_TASKS["C1-11"]["setup_files"]["scripts/test-bypass.sh"],
                encoding="utf-8",
            )
            reason = _validate_guardrail_regression_script(regression, root)
        self.assertEqual("", reason)

    def test_c1_11_dead_code_and_quoted_decoys_do_not_satisfy_regression_suite(self):
        reference = C1_TASKS["C1-11"]["setup_files"]["scripts/test-bypass.sh"]
        decoys = (
            f"if false; then\n{reference}\nfi\n",
            "payload=" + json.dumps(reference) + "\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            regression = root / "scripts" / "test-bypass.sh"
            regression.parent.mkdir()
            for decoy in decoys:
                with self.subTest(decoy=decoy[:20]):
                    regression.write_text(decoy, encoding="utf-8")
                    reason = _validate_guardrail_regression_script(regression, root)
                    self.assertIn("control-flow shape", reason)

    def test_c1_12_readme_only_is_not_concurrent_memory(self):
        self.assert_rejected("C1-12", {
            ".sad/README.md": "# memory\n",
        })


if __name__ == "__main__":
    unittest.main()
