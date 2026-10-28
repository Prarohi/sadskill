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
            "package.json": '{"name": "test-pkg", "type": "module", "main": "./index.cjs", "exports": "./index.js"}\n',
            "index.js": """const utils = { format: (s) => s.trim() };
export default utils;
"""
        },
        "expected_files": ["index.js"]
    },
    "C1-05": {
        "id": "C1-05",
        "name": "Cross-tenant authorization",
        "category": "Security & Backend",
        "prompt": "Fix authorization bypass in getDocument endpoint that allows tenant A to retrieve documents belonging to tenant B by document ID alone.",
        "budget": {"max_tokens": 1600, "max_turns": 4, "max_time_seconds": 90},
        "setup_files": {
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
        "prompt": "Harden PostgreSQL organizations table by enabling and forcing Row Level Security with strict tenant isolation policy.",
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
        "prompt": "Refactor immediate destructive column rename into a safe 2-phase expand/contract migration with up and down SQL scripts.",
        "budget": {"max_tokens": 1400, "max_turns": 4, "max_time_seconds": 90},
        "setup_files": {
            "migrations/rename.sql": "ALTER TABLE users RENAME COLUMN phone TO mobile_number;\n"
        },
        "expected_files": ["migrations/01_expand.sql", "migrations/02_contract.sql"]
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
        "prompt": "Implement accessible modal dialog with Escape key dismiss, focus trapping, role='dialog', and aria-modal='true'.",
        "budget": {"max_tokens": 1500, "max_turns": 4, "max_time_seconds": 90},
        "setup_files": {
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
        "prompt": "Verify that command interception guardrail cannot be bypassed using env, sudo, or recursive bash -c wrappers.",
        "budget": {"max_tokens": 1000, "max_turns": 2, "max_time_seconds": 45},
        "setup_files": {
            "scripts/test-bypass.sh": """#!/bin/bash
env bash -c 'git reset --hard'
"""
        },
        "expected_files": ["scripts/test-bypass.sh"]
    },
    "C1-12": {
        "id": "C1-12",
        "name": "Concurrent project memory",
        "category": "Agent Memory",
        "prompt": "Ensure concurrent writes to .sad/ memory utilize advisory locking and append-only event log with zero lost writes.",
        "budget": {"max_tokens": 1200, "max_turns": 3, "max_time_seconds": 60},
        "setup_files": {
            ".sad/README.md": "# Project Memory\n"
        },
        "expected_files": [".sad/events"]
    }
}
