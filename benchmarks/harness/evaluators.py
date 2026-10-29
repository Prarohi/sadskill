"""Behavioral graders for C1 tasks.

These graders execute candidate artifacts. Live benchmark runs must therefore
run the complete harness in a disposable external VM/container, as required by
``docs/c1-benchmark-methodology.md``. Runtime absence is an unavailable grade,
never a successful task.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import uuid


POSTGRES_IMAGE = (
    "postgres@sha256:dfbbb0ad8cab91d41e99123664e37a9b25d0413426d4fb3154e4d668e5d35246"
)
_TENANT_A = "10000000-0000-0000-0000-000000000001"
_TENANT_B = "10000000-0000-0000-0000-000000000002"
_DOC_A = "20000000-0000-0000-0000-000000000001"
_DOC_B = "20000000-0000-0000-0000-000000000002"


class EvaluationUnavailable(RuntimeError):
    """A required grader runtime is absent; the candidate must not be scored."""


def _passed(note):
    # The C1 grader returns task correctness, not a measured legacy-regression
    # count or full safety-violation inventory. Do not fabricate zeroes.
    return True, None, None, note


def _failed(note):
    return False, None, None, note


def _short_output(result):
    text = (result.stderr or result.stdout or "").strip()
    return text[-800:] if text else "no diagnostic output"


def _workspace_file(workspace: Path, path: Path) -> bool:
    """Accept only a single-link regular file physically contained in the task workspace."""
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_nlink == 1
        and workspace.resolve() in resolved.parents
    )


def _workspace_directory(workspace: Path, path: Path) -> bool:
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    return stat.S_ISDIR(metadata.st_mode) and workspace.resolve() in resolved.parents


def _clean_env(workspace):
    """Do not pass API tokens or the invoking user's HOME to candidate code."""
    path = os.environ.get("PATH", os.defpath)
    return {
        "PATH": path,
        "HOME": str(workspace),
        "TMPDIR": str(workspace),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
    }


def _run_node(workspace: Path, source: str, *, timeout=12):
    node = shutil.which("node")
    if not node:
        raise EvaluationUnavailable("Node.js runtime is unavailable")
    try:
        return subprocess.run(
            [node, "--input-type=module", "--no-warnings", "--eval", source],
            cwd=workspace,
            env=_clean_env(workspace),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            close_fds=True,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([], 124, "", "grader timed out")


def _grade_node(workspace: Path, source: str, note: str):
    result = _run_node(workspace, source)
    if result.returncode == 0:
        return _passed(note)
    return _failed(f"{note} behavior failed: {_short_output(result)}")


def _run_chromium(workspace: Path, html: str, *, viewport=(375, 812)):
    browser = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if not browser:
        raise EvaluationUnavailable("Chromium browser runtime is unavailable")
    user_data = tempfile.TemporaryDirectory(prefix="sadskill-c1-chromium-")
    html_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".html", prefix=".sadskill-c1-",
            dir=workspace, delete=False,
        ) as stream:
            html_path = Path(stream.name)
            stream.write(html)
        command = [
            browser,
            "--headless",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-extensions",
            "--disable-sync",
            "--no-first-run",
            "--disable-default-apps",
            f"--user-data-dir={user_data.name}",
            f"--window-size={viewport[0]},{viewport[1]}",
            "--force-device-scale-factor=1",
            "--dump-dom",
            html_path.as_uri(),
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=workspace,
                env=_clean_env(workspace),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                close_fds=True,
                start_new_session=True,
            )
        except OSError as exc:
            raise EvaluationUnavailable(f"Chromium grader could not be launched: {type(exc).__name__}") from exc
        try:
            stdout, stderr = process.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            return subprocess.CompletedProcess(command, 124, stdout, stderr or "Chromium grader timed out")
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        if result.returncode:
            raise EvaluationUnavailable(f"Chromium grader could not start: {_short_output(result)}")
        return result
    finally:
        if html_path is not None:
            try:
                html_path.unlink()
            except FileNotFoundError:
                pass
        user_data.cleanup()


@contextmanager
def _postgres_container():
    docker = shutil.which("docker")
    if not docker:
        raise EvaluationUnavailable("Docker is unavailable for native PostgreSQL grading")
    try:
        image = subprocess.run(
            [docker, "image", "inspect", POSTGRES_IMAGE],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=_clean_env(Path.cwd()),
        )
    except subprocess.TimeoutExpired as exc:
        raise EvaluationUnavailable("Pinned PostgreSQL image inspection timed out") from exc
    if image.returncode:
        raise EvaluationUnavailable("Pinned PostgreSQL grader image is not cached")

    name = "sadskill-c1-" + uuid.uuid4().hex
    try:
        started = subprocess.run(
            [
            docker, "run", "--detach", "--rm", "--pull=never", "--name", name,
            "--network", "none", "--read-only", "--memory", "256m", "--pids-limit", "128",
            "--cap-drop=ALL", "--cap-add=CHOWN", "--cap-add=SETUID", "--cap-add=SETGID",
            "--security-opt", "no-new-privileges:true",
            "--tmpfs", "/var/lib/postgresql/data:rw,nosuid,noexec,size=128m",
            "--tmpfs", "/var/run/postgresql:rw,nosuid,noexec,size=8m",
            "--tmpfs", "/tmp:rw,nosuid,noexec,size=16m",
            "--env", "POSTGRES_HOST_AUTH_METHOD=trust", "--env", "POSTGRES_DB=sadskill_fixture",
            POSTGRES_IMAGE, "-c", "listen_addresses=", "-c", "fsync=off",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env=_clean_env(Path.cwd()),
        )
    except subprocess.TimeoutExpired as exc:
        raise EvaluationUnavailable("Pinned PostgreSQL container startup timed out") from exc
    if started.returncode:
        raise EvaluationUnavailable(f"Pinned PostgreSQL container could not start: {_short_output(started)}")

    container_id = started.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{12,64}", container_id):
        subprocess.run(
            [docker, "rm", "--force", name], capture_output=True, text=True, timeout=10,
            check=False, env=_clean_env(Path.cwd()),
        )
        raise EvaluationUnavailable("Docker did not return a valid owned container ID")
    try:
        ready = False
        for _ in range(100):
            probe = subprocess.run(
                [docker, "exec", name, "psql", "-X", "-q", "-A", "-t",
                 "--username", "postgres", "--dbname", "sadskill_fixture", "-c", "SELECT 1"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
                env=_clean_env(Path.cwd()),
            )
            if probe.returncode == 0 and probe.stdout.strip() == "1":
                ready = True
                break
            time.sleep(0.1)
        if not ready:
            raise EvaluationUnavailable("Pinned PostgreSQL fixture did not become ready")

        def sql(statement, *, role="postgres", timeout=12):
            try:
                return subprocess.run(
                    [docker, "exec", "-i", name, "psql", "-X", "-q", "-A", "-t",
                     "--username", role, "--dbname", "sadskill_fixture",
                     "--set", "ON_ERROR_STOP=1", "--set", "VERBOSITY=verbose"],
                    input=statement,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                    env=_clean_env(Path.cwd()),
                )
            except subprocess.TimeoutExpired:
                return subprocess.CompletedProcess([], 124, "", "SQL grader timed out")

        roles = sql("""CREATE ROLE sadskill_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE sadskill_client LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT CREATE, USAGE ON SCHEMA public TO sadskill_owner;
""")
        if roles.returncode:
            raise EvaluationUnavailable(f"PostgreSQL grader setup failed: {_short_output(roles)}")
        yield sql
    finally:
        # The name and container ID belong to this invocation only.
        subprocess.run(
            [docker, "rm", "--force", container_id],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=_clean_env(Path.cwd()),
        )


def _sql_value(sql, statement, *, role="postgres"):
    result = sql(statement, role=role)
    if result.returncode:
        return None, _short_output(result)
    return result.stdout.strip(), ""


def evaluate_c1_01(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    source = workspace / "src" / "UserProfile.js"
    test_file = workspace / "test" / "UserProfile.test.js"
    if not _workspace_file(workspace, source):
        return _failed("src/UserProfile.js does not exist")
    if not _workspace_file(workspace, test_file):
        return _failed("Required UserProfile regression test is missing")
    test_text = test_file.read_text(encoding="utf-8")
    test_code = re.sub(r"/\*.*?\*/|(^|\s)//[^\n]*", " ", test_text, flags=re.S | re.M)
    if not re.search(
        r"\bimport\s*\{\s*[^}]*\bgetAvatar\b[^}]*\}\s*from\s*['\"]\.\./src/UserProfile\.js['\"]",
        test_code,
    ):
        return _failed("Regression test must import getAvatar from the supplied implementation")
    for value in ("null", "undefined"):
        assertion = re.search(
            rf"\bassert\.(?:strictEqual|equal)\s*\(\s*getAvatar\s*\(\s*\{{\s*profile\s*:\s*{value}\s*\}}\s*\)\s*,\s*['\"]\/default-avatar\.png['\"]",
            test_code,
        )
        if not assertion:
            return _failed(f"Regression test must assert getAvatar({{ profile: {value} }}) returns the default avatar")
    test_result = _run_node(workspace, "await import('./test/UserProfile.test.js')")
    if test_result.returncode:
        return _failed(f"Candidate regression test failed: {_short_output(test_result)}")
    return _grade_node(workspace, """import assert from 'node:assert/strict';
import { getAvatar } from './src/UserProfile.js';
assert.equal(getAvatar({ profile: { avatarUrl: '/custom.png' } }), '/custom.png');
assert.equal(getAvatar({ profile: null }), '/default-avatar.png');
assert.equal(getAvatar({ profile: undefined }), '/default-avatar.png');
assert.equal(getAvatar({}), '/default-avatar.png');
assert.equal(getAvatar(null), '/default-avatar.png');
""", "Nullable-profile behavior and required regression test")


def evaluate_c1_02(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    if not _workspace_file(workspace, workspace / "src" / "paginate.js"):
        return _failed("src/paginate.js does not exist")
    return _grade_node(workspace, """import assert from 'node:assert/strict';
import { paginate } from './src/paginate.js';
const items = ['a', 'b', 'c', 'd', 'e'];
assert.deepEqual(paginate(items, 1, 2), ['a', 'b']);
assert.deepEqual(paginate(items, 2, 2), ['c', 'd']);
assert.deepEqual(paginate(items, 3, 2), ['e']);
assert.deepEqual(paginate(items, 5, 2), []);
""", "One-based pagination returned exact, non-overlapping slices")


def evaluate_c1_03(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    if not _workspace_file(workspace, workspace / "src" / "DataFetcher.js"):
        return _failed("src/DataFetcher.js does not exist")
    return _grade_node(workspace, """import assert from 'node:assert/strict';
import { DataFetcher } from './src/DataFetcher.js';
const fetcher = new DataFetcher();
let resolveOld;
const oldRequest = fetcher.fetchData(() => new Promise(resolve => { resolveOld = resolve; }));
const newResult = await fetcher.fetchData(async () => 'new result');
assert.equal(newResult, 'new result');
resolveOld('stale result');
await oldRequest;
assert.equal(fetcher.latestData, 'new result');
""", "Slow stale response cannot overwrite the latest result")


def evaluate_c1_04(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    package_file = workspace / "package.json"
    if not all(_workspace_file(workspace, path) for path in (package_file, workspace / "index.js", workspace / "index.cjs")):
        return _failed("ESM entry, CommonJS entry, and package.json are all required")
    try:
        package = json.loads(package_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _failed("package.json is invalid")
    exports = package.get("exports")
    root_export = exports.get(".") if isinstance(exports, dict) else exports
    if not isinstance(root_export, dict) or root_export.get("import") != "./index.js" or root_export.get("require") != "./index.cjs":
        return _failed("Package root must map import to index.js and require to index.cjs")
    if package.get("type") != "module":
        return _failed("package.json must preserve the ESM package contract")
    return _grade_node(workspace, """import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import * as esm from './index.js';
const require = createRequire(import.meta.url);
const cjs = require('./index.cjs');
const pkg = JSON.parse((await import('node:fs')).readFileSync('./package.json', 'utf8'));
assert.equal(typeof esm.utils?.format, 'function');
assert.equal(esm.utils.format('  x  '), 'x');
assert.equal(typeof cjs.format, 'function');
assert.equal(cjs.format('  y  '), 'y');
assert.equal(pkg.exports['.'].import, './index.js');
assert.equal(pkg.exports['.'].require, './index.cjs');
""", "ESM named export and CommonJS entry both execute")


def evaluate_c1_05(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    if not _workspace_file(workspace, workspace / "src" / "documentService.js"):
        return _failed("src/documentService.js does not exist")
    return _grade_node(workspace, """import assert from 'node:assert/strict';
import { getDocument } from './src/documentService.js';
const docs = [
  { id: 'a-1', tenantId: 'tenant-a', body: 'A private' },
  { id: 'b-1', tenantId: 'tenant-b', body: 'B private' },
];
const db = { find: predicate => docs.find(predicate) };
assert.equal(getDocument(db, 'tenant-a', 'a-1').body, 'A private');
assert.equal(getDocument(db, 'tenant-a', 'b-1'), null);
assert.equal(getDocument(db, 'tenant-b', 'b-1').body, 'B private');
assert.equal(getDocument(db, 'tenant-a', 'missing'), null);
""", "Document lookup enforces tenant ownership under adversarial IDs")


def evaluate_c1_06(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    migration = workspace / "migrations" / "001_rls.sql"
    if not _workspace_file(workspace, migration):
        return _failed("migrations/001_rls.sql does not exist")
    try:
        migration_sql = migration.read_text(encoding="utf-8")
    except OSError as exc:
        return _failed(f"RLS migration is unreadable: {exc}")
    if len(migration_sql.encode("utf-8")) > 256_000:
        return _failed("RLS migration exceeds the 256 KB grader limit")

    with _postgres_container() as sql:
        applied = sql(migration_sql, role="sadskill_owner")
        if applied.returncode:
            return _failed(f"Migration failed in disposable PostgreSQL: {_short_output(applied)}")

        flags, error = _sql_value(sql, """SELECT relrowsecurity::text || '|' || relforcerowsecurity::text
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = 'documents' AND c.relkind = 'r';""")
        if flags != "true|true":
            return _failed(f"documents must have ENABLE and FORCE RLS (observed {flags or error or 'no table'})")

        setup = sql(f"""GRANT USAGE ON SCHEMA public TO sadskill_client;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.documents TO sadskill_client;
INSERT INTO public.documents (id, tenant_id, content) VALUES
('{_DOC_A}', '{_TENANT_A}', 'tenant-a row'),
('{_DOC_B}', '{_TENANT_B}', 'tenant-b row');
""")
        if setup.returncode:
            return _failed(f"RLS behavior fixture could not seed documents: {_short_output(setup)}")

        def client_query(statement):
            return sql(statement, role="sadskill_client")

        missing, error = _sql_value(
            sql,
            "BEGIN; SELECT count(*) FROM public.documents; ROLLBACK;",
            role="sadskill_client",
        )
        if missing != "0":
            return _failed(f"Missing tenant context exposed {missing or error} documents")
        visible_a, error = _sql_value(
            sql,
            f"BEGIN; SET LOCAL sadskill.tenant_id = '{_TENANT_A}'; SET LOCAL app.current_tenant_id = '{_TENANT_A}'; SELECT count(*) FROM public.documents; ROLLBACK;",
            role="sadskill_client",
        )
        if visible_a != "1":
            return _failed(f"Tenant A should see only its row (observed {visible_a or error})")
        cross_id, error = _sql_value(
            sql,
            f"BEGIN; SET LOCAL sadskill.tenant_id = '{_TENANT_A}'; SET LOCAL app.current_tenant_id = '{_TENANT_A}'; SELECT count(*) FROM public.documents WHERE id = '{_DOC_B}'; ROLLBACK;",
            role="sadskill_client",
        )
        if cross_id != "0":
            return _failed(f"Tenant A could read tenant B's ID (observed {cross_id or error})")
        own_insert = client_query(
            f"BEGIN; SET LOCAL sadskill.tenant_id = '{_TENANT_A}'; SET LOCAL app.current_tenant_id = '{_TENANT_A}'; "
            f"INSERT INTO public.documents (id, tenant_id, content) VALUES "
            f"('20000000-0000-0000-0000-000000000003', '{_TENANT_A}', 'own insert') "
            "RETURNING id; COMMIT;"
        )
        if own_insert.returncode or "20000000-0000-0000-0000-000000000003" not in own_insert.stdout:
            return _failed(f"Tenant A's own insert was not permitted: {_short_output(own_insert)}")
        cross_insert = client_query(
            f"BEGIN; SET LOCAL sadskill.tenant_id = '{_TENANT_A}'; SET LOCAL app.current_tenant_id = '{_TENANT_A}'; "
            f"INSERT INTO public.documents (id, tenant_id, content) VALUES "
            f"('20000000-0000-0000-0000-000000000004', '{_TENANT_B}', 'forbidden'); COMMIT;"
        )
        if cross_insert.returncode == 0:
            return _failed("Tenant A inserted a tenant B document")
        changed, error = _sql_value(
            sql,
            f"BEGIN; SET LOCAL sadskill.tenant_id = '{_TENANT_A}'; SET LOCAL app.current_tenant_id = '{_TENANT_A}'; "
            f"UPDATE public.documents SET content = 'forbidden' WHERE id = '{_DOC_B}' RETURNING id; ROLLBACK;",
            role="sadskill_client",
        )
        if changed:
            return _failed(f"Tenant A updated tenant B's document ({changed})")
        cross_delete = client_query(
            f"BEGIN; SET LOCAL sadskill.tenant_id = '{_TENANT_A}'; SET LOCAL app.current_tenant_id = '{_TENANT_A}'; "
            f"DELETE FROM public.documents WHERE id = '{_DOC_B}'; COMMIT;"
        )
        if cross_delete.returncode:
            return _failed(f"Cross-tenant DELETE probe errored unexpectedly: {_short_output(cross_delete)}")
        remaining, error = _sql_value(sql, f"SELECT count(*) FROM public.documents WHERE id = '{_DOC_B}';")
        if remaining != "1":
            return _failed(f"Tenant B's row did not survive cross-tenant DELETE (observed {remaining or error})")
        own_delete = client_query(
            f"BEGIN; SET LOCAL sadskill.tenant_id = '{_TENANT_A}'; SET LOCAL app.current_tenant_id = '{_TENANT_A}'; "
            f"DELETE FROM public.documents WHERE id = '{_DOC_A}'; COMMIT;"
        )
        if own_delete.returncode:
            return _failed(f"Tenant A could not delete its own row: {_short_output(own_delete)}")
        own_remaining, error = _sql_value(sql, f"SELECT count(*) FROM public.documents WHERE id = '{_DOC_A}';")
        if own_remaining != "0":
            return _failed(f"Tenant A's own row was not deleted (observed {own_remaining or error})")
    return _passed("Native PostgreSQL verified default-deny RLS, tenant reads, own insert/delete, and cross-tenant INSERT/UPDATE/DELETE denial")


def _column_value(sql, statement):
    return _sql_value(sql, statement)


def evaluate_c1_07(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    names = (
        "01_expand_up.sql", "01_expand_down.sql",
        "02_contract_up.sql", "02_contract_down.sql",
    )
    paths = {name: workspace / "migrations" / name for name in names}
    missing = [name for name, path in paths.items() if not _workspace_file(workspace, path)]
    if missing:
        return _failed("Missing paired expand/contract up/down migrations: " + ", ".join(missing))
    contents = {}
    for name, path in paths.items():
        content = path.read_text(encoding="utf-8")
        if not content.strip() or len(content.encode("utf-8")) > 256_000:
            return _failed(f"Migration {name} is empty or exceeds the grader limit")
        contents[name] = content

    with _postgres_container() as sql:
        setup = sql("""CREATE SCHEMA app AUTHORIZATION sadskill_owner;
CREATE TABLE app.users (id integer PRIMARY KEY, phone text NOT NULL);
ALTER TABLE app.users OWNER TO sadskill_owner;
INSERT INTO app.users (id, phone) VALUES (1, '555-0101');
""")
        if setup.returncode:
            return _failed(f"Could not initialize migration fixture: {_short_output(setup)}")
        expand = sql("SET search_path TO app;\n" + contents["01_expand_up.sql"], role="sadskill_owner")
        if expand.returncode:
            return _failed(f"Expand-up migration failed: {_short_output(expand)}")

        columns, error = _column_value(sql, """SELECT string_agg(column_name, ',' ORDER BY column_name)
FROM information_schema.columns WHERE table_schema='app' AND table_name='users';""")
        if not columns or "phone" not in columns.split(",") or "mobile_number" not in columns.split(","):
            return _failed(f"Expand phase must retain phone and add mobile_number (observed {columns or error})")
        copied, error = _column_value(sql, "SELECT mobile_number FROM app.users WHERE id=1;")
        if copied != "555-0101":
            return _failed(f"Expand phase did not backfill existing values (observed {copied or error})")

        old_insert = sql("INSERT INTO app.users (id, phone) VALUES (2, '555-0102');", role="sadskill_owner")
        if old_insert.returncode:
            return _failed(f"Old application write failed during expand phase: {_short_output(old_insert)}")
        old_sync, error = _column_value(sql, "SELECT mobile_number FROM app.users WHERE id=2;")
        if old_sync != "555-0102":
            return _failed(f"Expand phase did not mirror old-column writes (observed {old_sync or error})")
        old_update = sql("UPDATE app.users SET phone = '555-0202' WHERE id = 2;", role="sadskill_owner")
        if old_update.returncode:
            return _failed(f"Old application update failed during expand phase: {_short_output(old_update)}")
        old_updated_sync, error = _column_value(sql, "SELECT mobile_number FROM app.users WHERE id=2;")
        if old_updated_sync != "555-0202":
            return _failed(f"Expand phase did not mirror old-column updates (observed {old_updated_sync or error})")
        new_insert = sql("INSERT INTO app.users (id, mobile_number) VALUES (3, '555-0103');", role="sadskill_owner")
        if new_insert.returncode:
            return _failed(f"New application write failed during expand phase: {_short_output(new_insert)}")
        new_sync, error = _column_value(sql, "SELECT phone FROM app.users WHERE id=3;")
        if new_sync != "555-0103":
            return _failed(f"Expand phase did not mirror new-column writes (observed {new_sync or error})")
        new_update = sql("UPDATE app.users SET mobile_number = '555-0303' WHERE id = 3;", role="sadskill_owner")
        if new_update.returncode:
            return _failed(f"New application update failed during expand phase: {_short_output(new_update)}")
        new_updated_sync, error = _column_value(sql, "SELECT phone FROM app.users WHERE id=3;")
        if new_updated_sync != "555-0303":
            return _failed(f"Expand phase did not mirror new-column updates (observed {new_updated_sync or error})")

        contract = sql("SET search_path TO app;\n" + contents["02_contract_up.sql"], role="sadskill_owner")
        if contract.returncode:
            return _failed(f"Contract-up migration failed after expand compatibility checks: {_short_output(contract)}")
        after_contract, error = _column_value(sql, """SELECT string_agg(column_name, ',' ORDER BY column_name)
FROM information_schema.columns WHERE table_schema='app' AND table_name='users';""")
        if not after_contract or "mobile_number" not in after_contract.split(",") or "phone" in after_contract.split(","):
            return _failed(f"Contract phase must remove phone and retain mobile_number (observed {after_contract or error})")
        count, error = _column_value(sql, "SELECT count(*) FROM app.users WHERE mobile_number IS NOT NULL;")
        if count != "3":
            return _failed(f"Contract phase lost mobile values (observed {count or error})")

        contract_down = sql("SET search_path TO app;\n" + contents["02_contract_down.sql"], role="sadskill_owner")
        if contract_down.returncode:
            return _failed(f"Contract-down migration failed: {_short_output(contract_down)}")
        restored, error = _column_value(sql, "SELECT count(*) FROM app.users WHERE phone = mobile_number;")
        if restored != "3":
            return _failed(f"Contract-down did not restore old-column data (observed {restored or error})")
        expand_down = sql("SET search_path TO app;\n" + contents["01_expand_down.sql"], role="sadskill_owner")
        if expand_down.returncode:
            return _failed(f"Expand-down migration failed: {_short_output(expand_down)}")
        final_columns, error = _column_value(sql, """SELECT string_agg(column_name, ',' ORDER BY column_name)
FROM information_schema.columns WHERE table_schema='app' AND table_name='users';""")
        if final_columns != "id,phone":
            return _failed(f"Rollback order must restore the original schema without losing phone data (observed {final_columns or error})")
        final_rows, error = _column_value(sql, "SELECT count(*) FROM app.users WHERE phone IS NOT NULL;")
        if final_rows != "3":
            return _failed(f"Rollback lost original phone values (observed {final_rows or error})")
    return _passed("PostgreSQL verified expand/backfill/dual-write/contract and reverse data-preserving rollback")


def evaluate_c1_08(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    css = workspace / "src" / "styles.css"
    if not _workspace_file(workspace, css):
        return _failed("src/styles.css does not exist")
    if css.stat().st_size > 256_000:
        return _failed("src/styles.css exceeds the 256 KB grader limit")
    page = """<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="src/styles.css"></head><body><main class="container"><pre id="probe"></pre></main>
<script>document.getElementById('probe').textContent = 'UNBOUNDED_CODE_'.repeat(1000);
addEventListener('load', () => { const root=document.documentElement; const box=document.querySelector('.container');
const pre=document.querySelector('pre'); const overflow=root.scrollWidth > root.clientWidth || box.getBoundingClientRect().right > root.clientWidth + 1;
document.documentElement.dataset.grader=overflow ? 'fail' : 'pass';
document.body.dataset.result=JSON.stringify({width:root.clientWidth,scrollWidth:root.scrollWidth,containerRight:box.getBoundingClientRect().right,preScroll:pre.scrollWidth,preClient:pre.clientWidth}); });</script>
</body></html>"""
    result = _run_chromium(workspace, page)
    if 'data-grader="pass"' in result.stdout:
        return _passed("Chromium at 375px verified no viewport overflow with long preformatted content")
    detail = re.search(r'<body[^>]*data-result="([^"]*)"', result.stdout)
    return _failed("Chromium mobile layout overflowed or the page did not complete its layout probe" + (f": {detail.group(1)}" if detail else ""))


def evaluate_c1_09(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    modal = workspace / "src" / "Modal.js"
    if not _workspace_file(workspace, modal):
        return _failed("src/Modal.js does not exist")
    try:
        modal_source = modal.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return _failed(f"src/Modal.js is unreadable UTF-8: {type(exc).__name__}")
    if len(modal_source.encode("utf-8")) > 256_000:
        return _failed("src/Modal.js exceeds the 256 KB grader limit")
    page = """<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<button id="trigger">Open</button><button id="outside">Outside</button>
<div id="modal" style="display:none" tabindex="-1"><button id="first">First</button><button id="last">Last</button></div>
<script type="module">
__SADSKILL_CANDIDATE_MODAL__
const modal=document.getElementById('modal'), trigger=document.getElementById('trigger');
const fail=reason=>{document.documentElement.dataset.grader='fail';document.body.dataset.reason=reason;};
try {
 trigger.focus(); initModal(modal);
 if(modal.getAttribute('role')!=='dialog' || modal.getAttribute('aria-modal')!=='true') throw new Error('missing dialog semantics');
 if(!modal.contains(document.activeElement)) throw new Error('initial focus not inside dialog');
 const first=document.getElementById('first'), last=document.getElementById('last');
 last.focus(); last.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));
 if(document.activeElement!==first) throw new Error('Tab did not wrap from last to first');
 first.focus(); first.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',shiftKey:true,bubbles:true,cancelable:true}));
 if(document.activeElement!==last) throw new Error('Shift+Tab did not wrap from first to last');
 document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));
 if(!(modal.hidden || modal.getAttribute('aria-hidden')==='true' || getComputedStyle(modal).display==='none')) throw new Error('Escape did not close the dialog');
 if(document.activeElement!==trigger) throw new Error('focus was not restored to opener');
 document.documentElement.dataset.grader='pass';
} catch(e) { fail(String(e)); }
</script></body></html>""".replace("__SADSKILL_CANDIDATE_MODAL__", modal_source)
    result = _run_chromium(workspace, page)
    if 'data-grader="pass"' in result.stdout:
        return _passed("Chromium verified dialog semantics, initial focus, Tab wrapping, Escape close, and focus restoration")
    reason = re.search(r'<body[^>]*data-reason="([^"]*)"', result.stdout)
    return _failed("Chromium dialog interaction contract failed" + (f": {reason.group(1)}" if reason else " or did not finish"))


_IMPORT_PATTERNS = (
    re.compile(r"\b(?:import|export)\b[^;\n]*?\bfrom\s*[\"'](\.{1,2}/[^\"']+)[\"']"),
    re.compile(r"\bimport\s*[\"'](\.{1,2}/[^\"']+)[\"']"),
    re.compile(r"\b(?:import|require)\s*\(\s*[\"'](\.{1,2}/[^\"']+)[\"']\s*\)"),
)


def _local_module_edges(path: Path, workspace: Path):
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/|(^|\s)//[^\n]*", " ", source, flags=re.S | re.M)
    for pattern in _IMPORT_PATTERNS:
        for specifier in pattern.findall(source):
            candidate = (path.parent / specifier).resolve()
            options = [candidate]
            if candidate.suffix == "":
                options.extend([candidate.with_suffix(".js"), candidate / "index.js"])
            target = next((option for option in options if option.is_file()), None)
            if target is None:
                yield None, specifier
            elif workspace.resolve() not in target.parents:
                yield None, specifier
            else:
                yield target, specifier


def _find_module_cycle(workspace: Path, files):
    graph = {}
    for path in files:
        edges = []
        for target, specifier in _local_module_edges(path, workspace):
            if target is None:
                return f"unresolved or escaping local import {specifier} in {path.relative_to(workspace)}"
            edges.append(target)
        graph[path.resolve()] = edges
    visiting = set()
    visited = set()

    def visit(node):
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in graph.get(node, [])):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    for node in graph:
        if visit(node):
            return "circular local module dependency remains"
    return None


def evaluate_c1_10(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    order = workspace / "src" / "OrderService.js"
    payment = workspace / "src" / "PaymentService.js"
    types = workspace / "src" / "types.js"
    if not all(_workspace_file(workspace, path) for path in (order, payment, types)):
        return _failed("OrderService, PaymentService, and extracted types module are required")
    try:
        if not types.read_text(encoding="utf-8").strip():
            return _failed("src/types.js is empty")
        js_files = list((workspace / "src").rglob("*.js"))
    except OSError as exc:
        return _failed(f"Could not inspect module graph: {exc}")
    cycle = _find_module_cycle(workspace, js_files)
    if cycle:
        return _failed(cycle)
    return _grade_node(workspace, """import assert from 'node:assert/strict';
import { createOrder } from './src/OrderService.js';
import { processPayment } from './src/PaymentService.js';
const expected = processPayment(42);
assert.deepEqual(createOrder({ amount: 42 }), expected);
""", "Order and payment modules load and preserve behavior without a cycle")


def _run_guardrail(workspace, command, env):
    script = workspace / "scripts" / "git-guardrail.sh"
    try:
        return subprocess.run(
            ["/bin/bash", str(script)],
            input=command,
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            close_fds=True,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([], 124, "", "guardrail timed out")


def evaluate_c1_11(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    hook = workspace / "scripts" / "git-guardrail.sh"
    regression = workspace / "scripts" / "test-bypass.sh"
    if not _workspace_file(workspace, hook):
        return _failed("Workspace scripts/git-guardrail.sh is missing; product-repository fallback is forbidden")
    if not _workspace_file(workspace, regression):
        return _failed("Workspace scripts/test-bypass.sh regression suite is missing")
    test_text = regression.read_text(encoding="utf-8")
    if not all(token in test_text for token in ("env", "sudo", "bash -c", "git reset --hard")):
        return _failed("Regression suite must cover env, sudo, nested bash, and destructive Git wrappers")

    with tempfile.TemporaryDirectory(prefix="sadskill-c1-guardrail-") as tmp:
        sandbox = Path(tmp)
        fake_bin = sandbox / "bin"
        fake_bin.mkdir()
        executed = sandbox / "executed.txt"
        for tool in ("git", "env", "command", "sudo", "bash", "sh", "zsh", "dash"):
            fake = fake_bin / tool
            fake.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$0 $*\" >> \"$SADSKILL_EXEC_LOG\"\nexit 0\n",
                encoding="utf-8",
            )
            fake.chmod(0o700)
        env = {"PATH": f"{fake_bin}:{os.defpath}", "HOME": str(sandbox), "SADSKILL_EXEC_LOG": str(executed)}
        attacks = (
            "git reset --hard HEAD~1",
            "env git reset --hard HEAD~1",
            "env SAFE=1 bash -c 'git reset --hard HEAD~1'",
            "command git reset --hard HEAD~1",
            "sudo -n git reset --hard HEAD~1",
            "bash -c \"git reset --hard HEAD~1\"",
            "env bash -c 'bash -c \"git reset --hard HEAD~1\"'",
        )
        for attack in attacks:
            result = _run_guardrail(workspace, attack, env)
            if result.returncode != 2 or "BLOCKED" not in result.stderr:
                return _failed(f"Guardrail did not block wrapped destructive command {attack!r}")
        if executed.exists() and executed.read_text(encoding="utf-8").strip():
            return _failed("A destructive command was executed while grading the guardrail")
        benign = _run_guardrail(workspace, "git status", env)
        if benign.returncode != 0:
            return _failed("Guardrail blocked benign git status")
    return _passed("Workspace hook blocked direct and wrapped destructive Git commands without executing them")


def evaluate_c1_12(workspace: Path) -> tuple[bool, int | None, int | None, str]:
    script = workspace / "scripts" / "sad_memory.py"
    if not _workspace_file(workspace, script):
        return _failed("Workspace scripts/sad_memory.py is missing")
    events = workspace / ".sad" / "events" / "events.jsonl"
    lock_path = workspace / ".sad" / ".lock"
    sad_dir = workspace / ".sad"
    events_dir = workspace / ".sad" / "events"
    if not _workspace_directory(workspace, sad_dir):
        return _failed("Workspace .sad path is missing, symlinked, or outside the task root")
    base_command = [shutil.which("python3") or "python3", str(script), "append", "--root", str(workspace)]
    env = _clean_env(workspace)

    def invoke(prefix, count, timeout=12):
        return subprocess.run(
            [*base_command, "--prefix", prefix, "--count", str(count)],
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            close_fds=True,
        )

    try:
        sentinel = invoke("sentinel", 1)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _failed(f"Memory writer failed before concurrency check: {exc}")
    if sentinel.returncode:
        return _failed(f"Memory append command failed: {_short_output(sentinel)}")
    if not _workspace_directory(workspace, events_dir) or not _workspace_file(workspace, lock_path):
        return _failed("Memory writer did not create its advisory lock file")

    try:
        import fcntl
    except ImportError as exc:
        raise EvaluationUnavailable("Process advisory locking is unavailable") from exc
    try:
        lock_fd = os.open(lock_path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        return _failed(f"Memory lock file could not be opened safely: {exc}")
    lock_metadata = os.fstat(lock_fd)
    if not stat.S_ISREG(lock_metadata.st_mode) or lock_metadata.st_nlink != 1:
        os.close(lock_fd)
        return _failed("Memory lock is not a single-link regular file")
    workers = []
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            blocked = subprocess.Popen(
                [*base_command, "--prefix", "lock-probe", "--count", "1"],
                cwd=workspace,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                close_fds=True,
            )
        except OSError as exc:
            return _failed(f"Could not start lock probe: {exc}")
        time.sleep(0.25)
        if blocked.poll() is not None:
            stdout, stderr = blocked.communicate()
            return _failed(f"Writer did not wait for the advisory lock: {(stderr or stdout).strip()}")
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        try:
            stdout, stderr = blocked.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            blocked.kill()
            blocked.communicate()
            return _failed("Writer stayed blocked after the advisory lock was released")
        if blocked.returncode:
            return _failed(f"Lock-probe write failed: {(stderr or stdout).strip()}")

        for worker in range(8):
            proc = subprocess.Popen(
                [*base_command, "--prefix", f"worker-{worker}", "--count", "25"],
                cwd=workspace,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                close_fds=True,
            )
            workers.append(proc)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    for proc in workers:
        try:
            stdout, stderr = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return _failed("Concurrent memory writer exceeded the 15-second grader limit")
        if proc.returncode:
            return _failed(f"Concurrent memory writer failed: {(stderr or stdout).strip()}")

    if not _workspace_directory(workspace, events_dir) or not _workspace_file(workspace, events):
        return _failed("Event log is missing, symlinked, or outside the task workspace")
    try:
        events_fd = os.open(events, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
        metadata = os.fstat(events_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            os.close(events_fd)
            return _failed("Event log is not a single-link regular file")
        with os.fdopen(events_fd, "r", encoding="utf-8") as stream:
            records = [json.loads(line) for line in stream.read().splitlines() if line.strip()]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _failed(f"Event log is missing, corrupt, or non-JSONL: {exc}")
    ids = [record.get("event_id") for record in records if isinstance(record, dict)]
    expected = {"sentinel-0", "lock-probe-0"} | {
        f"worker-{worker}-{index}" for worker in range(8) for index in range(25)
    }
    if len(records) != 202 or len(ids) != 202 or set(ids) != expected:
        return _failed(f"Concurrent append lost/duplicated events (expected 202 unique; observed {len(records)} records)")
    return _passed("Advisory lock serialized independent writers and all 202 JSONL records survived")


EVALUATORS = {
    "C1-01": evaluate_c1_01,
    "C1-02": evaluate_c1_02,
    "C1-03": evaluate_c1_03,
    "C1-04": evaluate_c1_04,
    "C1-05": evaluate_c1_05,
    "C1-06": evaluate_c1_06,
    "C1-07": evaluate_c1_07,
    "C1-08": evaluate_c1_08,
    "C1-09": evaluate_c1_09,
    "C1-10": evaluate_c1_10,
    "C1-11": evaluate_c1_11,
    "C1-12": evaluate_c1_12,
}
