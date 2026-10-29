#!/usr/bin/env python3
"""Conservative lexical SQL mutation guard; not a SQL parser or permission boundary."""

import argparse
import re
import sys

_DOLLAR_QUOTE = re.compile(r"\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$")


def _scan_sql(sql: str, *, mask_literals: bool) -> str:
    """Remove comments and optionally literal contents without merging tokens."""
    out = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":
            i += 2
            while i < n and sql[i] not in "\r\n":
                i += 1
            out.append(" ")
            continue
        if ch == "/" and nxt == "*":
            i += 2
            depth = 1
            while i < n and depth:
                if sql.startswith("/*", i):
                    depth += 1
                    i += 2
                elif sql.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth:
                raise ValueError("unterminated SQL block comment")
            out.append(" ")
            continue
        if ch in ("'", '"'):
            start, quote = i, ch
            i += 1
            while i < n:
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                if sql[i] == "\\" and i + 1 < n:
                    i += 2
                else:
                    i += 1
            else:
                raise ValueError("unterminated SQL quote")
            out.append((" ident " if quote == '"' else " ") if mask_literals else sql[start:i])
            continue
        if ch == "$":
            match = _DOLLAR_QUOTE.match(sql, i)
            if match:
                tag = match.group(0)
                end = sql.find(tag, match.end())
                if end < 0:
                    raise ValueError("unterminated SQL dollar quote")
                out.append(" " if mask_literals else sql[i:end + len(tag)])
                i = end + len(tag)
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def strip_sql_comments(sql: str) -> str:
    """Remove comments without altering string contents."""
    return _scan_sql(sql, mask_literals=False)


def _has_unconditional_where(condition: str) -> bool:
    """Recognize a small set of obvious true predicates; this is not SQL parsing."""
    condition = re.sub(r"\b(?:RETURNING|ORDER\s+BY|LIMIT)\b.*$", "", condition, flags=re.I).strip()
    truth = r"\(*\s*(?:TRUE|1\s*=\s*1|NOT\s+FALSE)\s*\)*"
    return bool(
        re.fullmatch(truth, condition, re.I)
        or re.match(rf"^\s*{truth}\s+OR\b", condition, re.I)
        or re.search(rf"\bOR\s+{truth}\s*(?:\bOR\b|$)", condition, re.I)
    )


def inspect_sql(sql_query: str) -> tuple[bool, str]:
    """Return (blocked, reason); only a defense-in-depth heuristic."""
    try:
        clean = _scan_sql(sql_query, mask_literals=True)
    except ValueError as exc:
        return True, f"Cannot safely inspect malformed SQL: {exc}"

    for statement in clean.split(";"):
        normalized = re.sub(r"\s+", " ", statement).strip()
        if not normalized:
            continue
        if re.search(
            r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA|VIEW|MATERIALIZED\s+VIEW|INDEX|"
            r"COLUMN|OWNED|ROLE|USER|FUNCTION|TRIGGER|POLICY|EXTENSION)\b",
            normalized, re.I,
        ):
            return True, "Destructive SQL DROP operation detected"
        if re.search(r"\bALTER\s+TABLE\b.*\bDROP\s+(?:COLUMN|CONSTRAINT)\b", normalized, re.I):
            return True, "Destructive ALTER TABLE DROP operation detected"
        if re.search(r"\bTRUNCATE\b", normalized, re.I):
            return True, "Destructive SQL TRUNCATE operation detected"
        for match in re.finditer(r"\bDELETE\s+FROM\b", normalized, re.I):
            remainder = normalized[match.end():]
            where = re.search(r"\bWHERE\b", remainder, re.I)
            if where is None:
                return True, "Unbounded DELETE FROM query detected without WHERE clause"
            condition = remainder[where.end():].strip()
            if not condition:
                return True, "Unbounded DELETE FROM query detected with an empty WHERE clause"
            if _has_unconditional_where(condition):
                return True, "Unbounded DELETE FROM query detected with unconditional WHERE"
    return False, ""


def main():
    parser = argparse.ArgumentParser(
        description="Conservative SQL guard; not an SQL parser or sandbox"
    )
    parser.add_argument("query", help="SQL query text to inspect")
    args = parser.parse_args()
    blocked, reason = inspect_sql(args.query)
    if blocked:
        print(f"BLOCKED: {reason}", file=sys.stderr)
        sys.exit(2)
    print("ALLOWED BY HEURISTIC: no known destructive SQL pattern detected")
    sys.exit(0)


if __name__ == "__main__":
    main()
