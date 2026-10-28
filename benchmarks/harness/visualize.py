#!/usr/bin/env python3
"""sadskill C1 Benchmark Visualizer & Metrics Synthesizer.
Processes benchmark JSONL execution records and generates comparative Markdown
tables, statistical summaries, and Mermaid charts.
"""

import argparse
import json
from pathlib import Path
import sys


def synthesize_metrics(records: list) -> dict:
    conditions = {}
    for r in records:
        cond = r.get("condition", "unknown")
        if cond not in conditions:
            conditions[cond] = {
                "total": 0,
                "passed": 0,
                "regressions": 0,
                "safety_violations": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "wall_clock": 0.0,
                "evidence_count": 0,
            }
        c = conditions[cond]
        c["total"] += 1
        if r.get("success"):
            c["passed"] += 1
        c["regressions"] += r.get("regressions", 0)
        c["safety_violations"] += r.get("safety_violations", 0)
        c["input_tokens"] += r.get("input_tokens", 0)
        c["output_tokens"] += r.get("output_tokens", 0)
        c["wall_clock"] += r.get("wall_clock_seconds", 0.0)
        if r.get("evidence_produced"):
            c["evidence_count"] += 1

    summary = {}
    for cond, data in conditions.items():
        tot = data["total"] or 1
        summary[cond] = {
            "total_runs": data["total"],
            "success_rate": round((data["passed"] / tot) * 100, 1),
            "regressions": data["regressions"],
            "safety_violations": data["safety_violations"],
            "avg_input_tokens": round(data["input_tokens"] / tot),
            "avg_output_tokens": round(data["output_tokens"] / tot),
            "avg_total_tokens": round((data["input_tokens"] + data["output_tokens"]) / tot),
            "avg_latency_s": round(data["wall_clock"] / tot, 2),
            "evidence_rate": round((data["evidence_count"] / tot) * 100, 1),
        }
    return summary


def generate_markdown_report(summary: dict) -> str:
    md = [
        "# C1 Comparative Benchmark Results\n",
        "Empirical performance evaluation across the 12 C1 benchmark tasks.\n",
        "| Condition | Success Rate | Regressions | Safety Violations | Avg Tokens | Avg Latency | Evidence Rate |",
        "|---|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for cond in ("plain", "sadskill", "competitor"):
        if cond in summary:
            s = summary[cond]
            md.append(
                f"| **`{cond}`** | **{s['success_rate']}%** | {s['regressions']} | {s['safety_violations']} | {s['avg_total_tokens']} | {s['avg_latency_s']}s | {s['evidence_rate']}% |"
            )

    md.append("\n## Token & Efficiency Comparison\n")
    sad_tokens = summary.get("sadskill", {}).get("avg_total_tokens", 1)
    comp_tokens = summary.get("competitor", {}).get("avg_total_tokens", 1)
    if comp_tokens > sad_tokens:
        savings = round(((comp_tokens - sad_tokens) / comp_tokens) * 100, 1)
        md.append(f"> **Token Efficiency**: `sadskill` achieves **{savings}% token reduction** compared to competitor workflows through contract-first planning and surgical file diffs.\n")

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
