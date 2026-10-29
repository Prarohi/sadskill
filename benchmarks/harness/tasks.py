"""Definitions for the 12 C1 Comparative Agent Benchmark Tasks.
Covers real-world defects across Bugfix, Backend, Security, UI, and Architecture.
"""

C1_TASKS = {
    "C1-01": {
        "id": "C1-01",
        "name": "Nullable-profile bug",
        "category": "Bugfix",
        "prompt": "Fix TypeError: Cannot read properties of undefined (reading 'avatarUrl') in UserProfile component when user.profile is null or undefined, and add regression test.",
        "budget": {"max_tokens": 1200, "max_turns": 4, "max_time_seconds": 60},
        "setup_files": {
            "package.json": '{"private":true,"type":"module"}\n',
            "src/UserProfile.js": """export function getAvatar(user) {
  // Bug: Throws if user.profile is undefined
  return user.profile.avatarUrl || '/default-avatar.png';
}
""",
            "test/UserProfile.test.js": """import { getAvatar } from '../src/UserProfile.js';
import assert from 'node:assert';

// Existing baseline test
assert.strictEqual(getAvatar({ profile: { avatarUrl: '/custom.png' } }), '/custom.png');
console.log('Existing tests pass');
"""
        },
        "expected_files": ["src/UserProfile.js", "test/UserProfile.test.js"]
    },
    "C1-02": {
        "id": "C1-02",
        "name": "Pagination off-by-one",
        "category": "Bugfix",
        "prompt": "Fix off-by-one pagination helper where page 1 and page 2 overlap the last item at boundary, and ensure 1-based index returns accurate non-overlapping slices.",
        "budget": {"max_tokens": 1200, "max_turns": 4, "max_time_seconds": 60},
        "setup_files": {
            "package.json": '{"private":true,"type":"module"}\n',
            "src/paginate.js": """export function paginate(items, page, pageSize) {
  // Bug: inclusive slice boundary overlaps one item
  const start = (page - 1) * pageSize;
  const end = start + pageSize + 1;
  return items.slice(start, end);
}
"""
        },
        "expected_files": ["src/paginate.js"]
    },
    "C1-03": {
        "id": "C1-03",
        "name": "Async stale-result race",
        "category": "Async & Concurrency",
        "prompt": "Fix async stale-result race condition in DataFetcher where a slow prior request overwrites results from a newer request.",
        "budget": {"max_tokens": 1500, "max_turns": 4, "max_time_seconds": 60},
        "setup_files": {
            "package.json": '{"private":true,"type":"module"}\n',
            "src/DataFetcher.js": """export class DataFetcher {
  constructor() {
    this.latestData = null;
  }
  async fetchData(queryFn) {
    const data = await queryFn();
    this.latestData = data;
    return this.latestData;
  }
}
"""
        },
        "expected_files": ["src/DataFetcher.js"]
    },
    "C1-04": {
        "id": "C1-04",
        "name": "Node ESM export mismatch",
        "category": "Modules & Packaging",
        "prompt": "Fix Node.js ESM named export error 'The requested module does not provide an export named utils' while preserving CommonJS backward compatibility.",
        "budget": {"max_tokens": 1200, "max_turns": 4, "max_time_seconds": 60},
        "setup_files": {
            "package.json": '{"name": "test-pkg", "private": true, "type": "module", "main": "./index.cjs", "exports": "./index.js"}\n',
            "index.js": """const utils = { format: (s) => s.trim() };
export default utils;
""",
            "index.cjs": """const utils = { format: (s) => s.trim() };
module.exports = utils;
"""
        },
        "expected_files": ["index.js", "index.cjs", "package.json"]
    },
    "C1-05": {
        "id": "C1-05",
        "name": "Cross-tenant authorization",
        "category": "Security & Backend",
        "prompt": "Fix authorization bypass in getDocument endpoint that allows tenant A to retrieve documents belonging to tenant B by document ID alone.",
        "budget": {"max_tokens": 1600, "max_turns": 4, "max_time_seconds": 90},
        "setup_files": {
            "package.json": '{"private":true,"type":"module"}\n',
            "src/documentService.js": """export function getDocument(db, tenantId, docId) {
  // Bug: Query ignores tenantId scope
  const doc = db.find(d => d.id === docId);
  return doc || null;
}
"""
        },
        "expected_files": ["src/documentService.js"]
    },
    "C1-06": {
        "id": "C1-06",
        "name": "PostgreSQL RLS hole",
        "category": "Database Security",
        "prompt": "Harden the supplied PostgreSQL documents table with ENABLE and FORCE ROW LEVEL SECURITY. Add a restrictive policy that uses the transaction-local sadskill.tenant_id setting to enforce tenant_id on reads and writes; missing tenant context must reveal no rows and cross-tenant writes must be rejected.",
        "budget": {"max_tokens": 1500, "max_turns": 4, "max_time_seconds": 90},
        "setup_files": {
            "migrations/001_rls.sql": """-- Table without forced RLS
CREATE TABLE documents (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  content TEXT
);
"""
        },
        "expected_files": ["migrations/001_rls.sql"]
    },
    "C1-07": {
        "id": "C1-07",
        "name": "Safe expand/contract migration",
        "category": "Database Reliability",
        "prompt": "Replace the destructive phone-to-mobile_number rename with four PostgreSQL migrations: 01_expand_up.sql, 01_expand_down.sql, 02_contract_up.sql, and 02_contract_down.sql. Expand must retain phone, add and backfill mobile_number, and keep either old-column or new-column application writes synchronized during rollout. Contract may remove phone only after expansion. Down migrations run in reverse order and must preserve all stored values.",
        "budget": {"max_tokens": 1400, "max_turns": 4, "max_time_seconds": 90},
        "setup_files": {
            "migrations/rename.sql": "ALTER TABLE users RENAME COLUMN phone TO mobile_number;\n"
        },
        "expected_files": ["migrations/01_expand_up.sql", "migrations/01_expand_down.sql", "migrations/02_contract_up.sql", "migrations/02_contract_down.sql"]
    },
    "C1-08": {
        "id": "C1-08",
        "name": "Mobile CSS overflow",
        "category": "Frontend Craft",
        "prompt": "Eliminate horizontal viewport scrolling on mobile screens (<= 375px) caused by fixed container widths and unbounded pre tags.",
        "budget": {"max_tokens": 1200, "max_turns": 4, "max_time_seconds": 60},
        "setup_files": {
            "src/styles.css": """.container {
  width: 600px;
}
pre {
  white-space: pre;
}
"""
        },
        "expected_files": ["src/styles.css"]
    },
    "C1-09": {
        "id": "C1-09",
        "name": "Accessible dialog behavior",
        "category": "Accessibility & UI",
        "prompt": "Implement initModal(el) as an accessible modal dialog: set role='dialog' and aria-modal='true', open and focus the dialog, wrap Tab and Shift+Tab among its buttons, close on Escape, and restore focus to the element active before opening. Keep the function interface unchanged.",
        "budget": {"max_tokens": 1500, "max_turns": 4, "max_time_seconds": 90},
        "setup_files": {
            "package.json": '{"private":true,"type":"module"}\n',
            "src/Modal.js": """export function initModal(el) {
  // Basic display without a11y focus or key handlers
  el.style.display = 'block';
}
"""
        },
        "expected_files": ["src/Modal.js"]
    },
    "C1-10": {
        "id": "C1-10",
        "name": "Circular dependency removal",
        "category": "Architecture",
        "prompt": "Decouple circular dependency between OrderService and PaymentService by extracting shared types/interfaces to an independent module.",
        "budget": {"max_tokens": 1600, "max_turns": 4, "max_time_seconds": 90},
        "setup_files": {
            "package.json": '{"private":true,"type":"module"}\n',
            "src/OrderService.js": """import { processPayment } from './PaymentService.js';
export function createOrder(data) {
  return processPayment(data.amount);
}
export function getOrder(id) { return { id }; }
""",
            "src/PaymentService.js": """import { getOrder } from './OrderService.js';
export function processPayment(amount) {
  return { success: true, amount };
}
"""
        },
        "expected_files": ["src/OrderService.js", "src/PaymentService.js", "src/types.js"]
    },
    "C1-11": {
        "id": "C1-11",
        "name": "Guardrail wrapper bypass",
        "category": "Safety Enforcement",
        "prompt": "Harden scripts/git-guardrail.sh, which receives one proposed shell command from stdin, so destructive git reset --hard commands remain blocked through env assignments, sudo, command, and recursive bash -c wrappers. Benign git status must remain allowed. In scripts/test-bypass.sh, preserve exactly the supplied seven-case array, top-level loop, fail-on-allow hook invocation, and benign git status check; do not add other executable lines or change the structure. Comments and blank lines are allowed. The evaluator checks this exact reference structure statically and never executes the candidate test script. The test suite must never execute the destructive command.",
        "budget": {"max_tokens": 1000, "max_turns": 2, "max_time_seconds": 45},
        "setup_files": {
            "scripts/git-guardrail.sh": """#!/bin/bash
set -euo pipefail
command_text="$(cat)"
case "$command_text" in
  "git reset --hard"*) echo "BLOCKED: destructive command" >&2; exit 2 ;;
esac
exit 0
""",
            "scripts/test-bypass.sh": """#!/bin/bash
set -e
hook="$(dirname "$0")/git-guardrail.sh"
cases=(
  'git reset --hard HEAD~1'
  'env git reset --hard HEAD~1'
  'env SAFE=1 bash -c git reset --hard HEAD~1'
  'command git reset --hard HEAD~1'
  'sudo -n git reset --hard HEAD~1'
  'bash -c git reset --hard HEAD~1'
  'env bash -c bash -c git reset --hard HEAD~1'
)
for command in "${cases[@]}"; do
  printf '%s\\n' "$command" | bash "$hook" && exit 1
done
printf '%s\\n' 'git status' | bash "$hook"
"""
        },
        "expected_files": ["scripts/git-guardrail.sh", "scripts/test-bypass.sh"]
    },
    "C1-12": {
        "id": "C1-12",
        "name": "Concurrent project memory",
        "category": "Agent Memory",
        "prompt": "Implement scripts/sad_memory.py append --root <project> --prefix <writer> --count <n>. Serialize writes with an advisory process lock at .sad/.lock and write JSONL events to .sad/events/events.jsonl. Concurrent writers must preserve all prior events and every unique new record.",
        "budget": {"max_tokens": 1200, "max_turns": 3, "max_time_seconds": 60},
        "setup_files": {
            ".sad/README.md": "# Project Memory\n",
            "scripts/sad_memory.py": """#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path

def append(root, prefix, count):
    events = root / '.sad' / 'events' / 'events.jsonl'
    events.parent.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        old = events.read_text(encoding='utf-8') if events.exists() else ''
        time.sleep(0.002)
        record = {'event_id': f'{prefix}-{index}', 'type': 'custom'}
        events.write_text(old + json.dumps(record) + '\\n', encoding='utf-8')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    write = sub.add_parser('append')
    write.add_argument('--root', required=True, type=Path)
    write.add_argument('--prefix', required=True)
    write.add_argument('--count', required=True, type=int)
    args = parser.parse_args()
    append(args.root, args.prefix, args.count)
"""
        },
        "expected_files": ["scripts/sad_memory.py", ".sad/.lock", ".sad/events/events.jsonl"]
    }
}
