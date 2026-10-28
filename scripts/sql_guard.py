#!/usr/bin/env python3
"""sadskill Deep SQL Semantic Tokenizer & Guardrail.
Inspects SQL queries for destructive mutating statements across comments,
CTEs, multi-statement payloads, and unbounded DELETE queries.
"""

import argparse
import re
import sys


def strip_sql_comments(sql: str) -> str:
    """Removes single-line (--) and multi-line (/* */) comments while preserving strings."""
    tokens = []
    i = 0
    n = len(sql)
    in_single_quote = False
    in_double_quote = False

    while i < n:
        c = sql[i]
        next_c = sql[i + 1] if i + 1 < n else ""

        # Handle string quoting
        if c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            tokens.append(c)
            i += 1
            continue
        if c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            tokens.append(c)
            i += 1
            continue

        if not in_single_quote and not in_double_quote:
            # Single-line comment: -- ...
            if c == "-" and next_c == "-":
                i += 2
                while i < n and sql[i] not in ("\n", "\r"):
                    i += 1
                continue
            # Multi-line comment: /* ... */
            if c == "/" and next_c == "*":
                i += 2
                while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                    i += 1
                i += 2  # skip closing */
                tokens.append(" ")
                continue

        tokens.append(c)
        i += 1

    return "".join(tokens)


def inspect_sql(sql_query: str) -> tuple[bool, str]:
    """Evaluates whether SQL query contains destructive operations.
    Returns (is_destructive, reason).
    """
    clean_sql = strip_sql_comments(sql_query).strip()
    if not clean_sql:
        return False, ""

    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", clean_sql)

    # 1. DROP operations
    drop_match = re.search(
        r"\bDROP\s+(?:DATABASE|SCHEMA|TABLE|VIEW|MATERIALIZED\s+VIEW|INDEX|COLUMN)\b",
        normalized,
        re.IGNORECASE,
    )
    if drop_match:
        return True, f"Destructive SQL DROP operation detected: {drop_match.group(0)}"

    # 2. ALTER TABLE ... DROP COLUMN
    if re.search(r"\bALTER\s+TABLE\s+[^\s;]+\s+DROP\s+COLUMN\b", normalized, re.IGNORECASE):
        return True, "Destructive ALTER TABLE DROP COLUMN detected"

    # 3. TRUNCATE operations
    truncate_match = re.search(r"\bTRUNCATE\s+(?:TABLE\s+)?([a-zA-Z0-9_.\"']+)\b", normalized, re.IGNORECASE)
    if truncate_match:
        return True, f"Destructive SQL TRUNCATE operation detected on {truncate_match.group(1)}"

    # 4. Unbounded DELETE FROM without WHERE clause
    # Checks for standalone DELETE FROM <table>; or end of string without WHERE
    unbounded_delete = re.search(
        r"\bDELETE\s+FROM\s+[a-zA-Z0-9_.\"']+\s*(?:;|$)(?!\s*WHERE\b)",
        normalized,
        re.IGNORECASE,
    )
    if unbounded_delete:
        return True, "Unbounded DELETE FROM query detected without WHERE clause"

    return False, ""


def main():
    parser = argparse.ArgumentParser(description="sadskill SQL Safety Guard")
    parser.add_argument("query", help="SQL statement string to inspect")
    args = parser.parse_args()

    destructive, reason = inspect_sql(args.query)
    if destructive:
        print(f"BLOCKED: {reason}", file=sys.stderr)
        sys.exit(2)
    print("ALLOWED: SQL query is non-destructive")
    sys.exit(0)


if __name__ == "__main__":
    main()
