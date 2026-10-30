#!/usr/bin/env python3
"""sadskill C1 Benchmark Visualizer & Metrics Synthesizer.
Processes benchmark JSONL execution records and generates comparative Markdown
tables, statistical summaries, and Mermaid charts.
"""

import argparse
import json
import math
from pathlib import Path
import re
import sys


_REAL_PROVIDERS = {"codex", "claude", "gemini"}
_CONDITIONS = ("plain", "sadskill", "competitor")


def synthesize_metrics(records: list) -> dict:
    # Keep only schema-valid runner records. These checks do not authenticate
    # the JSONL source; reports must still be backed by trusted runner output.
    records = [
        r for r in records
        if isinstance(r, dict)
        and r.get("provider") in _REAL_PROVIDERS
        and r.get("synthetic") is False
        and r.get("status") == "COMPLETED_REAL"
        and r.get("condition") in _CONDITIONS
        and isinstance(r.get("task_id"), str)
        and re.fullmatch(r"C1-\d{2}", r["task_id"])
        and isinstance(r.get("model"), str)
        and bool(r["model"].strip())
        and isinstance(r.get("experiment_id"), str)
        and re.fullmatch(r"[0-9a-f]{32}", r["experiment_id"])
        and isinstance(r.get("repetition"), int)
        and not isinstance(r.get("repetition"), bool)
        and r["repetition"] > 0
        and isinstance(r.get("prompt_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", r["prompt_sha256"])
        and isinstance(r.get("input_tokens"), int)
        and not isinstance(r.get("input_tokens"), bool)
        and r.get("input_tokens") >= 0
        and isinstance(r.get("output_tokens"), int)
        and not isinstance(r.get("output_tokens"), bool)
        and r.get("output_tokens") >= 0
        and isinstance(r.get("success"), bool)
        and isinstance(r.get("wall_clock_seconds"), (int, float))
        and not isinstance(r.get("wall_clock_seconds"), bool)
        and math.isfinite(r["wall_clock_seconds"])
        and r["wall_clock_seconds"] >= 0
    ]
    trials_by_condition = {condition: [] for condition in _CONDITIONS}
    for record in records:
        trials_by_condition[record["condition"]].append((
            record["experiment_id"], record["provider"], record["model"],
            record["task_id"], record["repetition"],
        ))
    paired_tokens = all(trials_by_condition[condition] for condition in _CONDITIONS)
    if paired_tokens:
        key_sets = [set(trials_by_condition[condition]) for condition in _CONDITIONS]
        paired_tokens = (
            all(len(keys) == len(trials_by_condition[condition])
                for keys, condition in zip(key_sets, _CONDITIONS))
            and key_sets[0] == key_sets[1] == key_sets[2]
        )
    conditions = {}
    for r in records:
        cond = r.get("condition", "unknown")
        if cond not in conditions:
            conditions[cond] = {
                "total": 0,
                "passed": 0,
                "regressions": 0,
                "regression_measurements": 0,
                "safety_violations": 0,
                "safety_measurements": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "wall_clock": 0.0,
                "evidence_count": 0,
            }
        c = conditions[cond]
        c["total"] += 1
        if r.get("success"):
            c["passed"] += 1
        if isinstance(r.get("regressions"), int) and not isinstance(r.get("regressions"), bool) and r["regressions"] >= 0:
            c["regressions"] += r["regressions"]
            c["regression_measurements"] += 1
        if isinstance(r.get("safety_violations"), int) and not isinstance(r.get("safety_violations"), bool) and r["safety_violations"] >= 0:
            c["safety_violations"] += r["safety_violations"]
            c["safety_measurements"] += 1
        c["input_tokens"] += r.get("input_tokens", 0)
        c["output_tokens"] += r.get("output_tokens", 0)
        c["wall_clock"] += r.get("wall_clock_seconds", 0.0)
        if r.get("evidence_produced") is True:
            c["evidence_count"] += 1

    summary = {}
    for cond, data in conditions.items():
        tot = data["total"] or 1
        summary[cond] = {
            "total_runs": data["total"],
            "success_rate": round((data["passed"] / tot) * 100, 1),
            "regressions": data["regressions"] if data["regression_measurements"] == data["total"] else None,
            "safety_violations": data["safety_violations"] if data["safety_measurements"] == data["total"] else None,
            "avg_input_tokens": round(data["input_tokens"] / tot),
            "avg_output_tokens": round(data["output_tokens"] / tot),
            "avg_total_tokens": round((data["input_tokens"] + data["output_tokens"]) / tot),
            "avg_latency_s": round(data["wall_clock"] / tot, 2),
            "evidence_rate": round((data["evidence_count"] / tot) * 100, 1),
        }
    if summary:
        summary["_paired_token_comparison"] = paired_tokens
    return summary


def generate_markdown_report(summary: dict) -> str:
    if not summary:
        return (
            "# C1 Comparative Benchmark Results\n\n"
            "**NOT_EXECUTED: No measured live-agent trials are available.**\n\n"
            "Mock runs are synthetic fixture demonstrations, not empirical model results. "
            "They cannot establish success rates, token savings, competitor performance, "
            "latency, or authenticated verification evidence.\n"
        )
    md = [
        "# C1 Comparative Benchmark Results\n",
        "Schema-valid live-agent records; JSONL claims are not cryptographically authenticated. Use trusted runner output and compare only matched trials.\n",
        "| Condition | Success Rate | Regressions | Safety Violations | Avg Tokens | Avg Latency | Evidence Rate |",
        "|---|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for cond in ("plain", "sadskill", "competitor"):
        if cond in summary:
            s = summary[cond]
            regression_count = s["regressions"] if s["regressions"] is not None else "NOT_MEASURED"
            safety_count = s["safety_violations"] if s["safety_violations"] is not None else "NOT_MEASURED"
            md.append(
                f"| **`{cond}`** | **{s['success_rate']}%** | {regression_count} | {safety_count} | {s['avg_total_tokens']} | {s['avg_latency_s']}s | {s['evidence_rate']}% |"
            )

    md.append("\n## Token & Efficiency Comparison\n")
    if summary.get("_paired_token_comparison"):
        sad_tokens = summary["sadskill"]["avg_total_tokens"]
        comp_tokens = summary["competitor"]["avg_total_tokens"]
        if comp_tokens > sad_tokens:
            savings = round(((comp_tokens - sad_tokens) / comp_tokens) * 100, 1)
            md.append(f"> **Observed token difference**: {savings}% across matched task/model/repetition records in one experiment. This is descriptive, not proof of causal improvement.\n")
    else:
        md.append("> **Token comparison omitted**: no complete matched trial set exists across plain, sadskill, and competitor conditions.\n")

    md.append("\n```mermaid\nxychart-beta\n  title \"Task Success Rate vs Token Consumption\"\n  x-axis [\"plain\", \"sadskill\", \"competitor\"]\n  y-axis \"Success Rate (%)\" 0 --> 100\n  bar ["
              + f"{summary.get('plain', {}).get('success_rate', 0)}, "
              + f"{summary.get('sadskill', {}).get('success_rate', 0)}, "
              + f"{summary.get('competitor', {}).get('success_rate', 0)}"
              + "]\n```\n")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="sadskill Benchmark Visualizer")
    parser.add_argument("--inputs", nargs="+", required=True, help="Path(s) to JSONL benchmark result files")
    parser.add_argument("--output-markdown", default=None, help="Path to write Markdown summary report")

    args = parser.parse_args()

    all_records = []
    for pattern in args.inputs:
        path = Path(pattern)
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        all_records.append(json.loads(line))
                    except Exception:
                        pass

    if not all_records:
        sys.exit("No valid JSONL records found in specified input files.")

    summary = synthesize_metrics(all_records)
    report = generate_markdown_report(summary)

    if args.output_markdown:
        out_p = Path(args.output_markdown)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(report, encoding="utf-8")
        print(f"Report written to: {out_p}")
    else:
        print(report)


if __name__ == "__main__":
    main()
