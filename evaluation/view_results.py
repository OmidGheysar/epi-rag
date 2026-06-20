"""
EpiRAG Evaluation — Results Viewer

Converts evaluation/results.json into:
  1. evaluation/results_summary.csv  — one row per question, one column per
     metric score. Open in Excel, sort/filter by any metric.
  2. evaluation/results_lowlights.md — for each metric, the 3 lowest-scoring
     cases with the full question and the judge LLM's reasoning, so you can
     spot-check without hunting through raw JSON.

Usage:
    python evaluation/view_results.py
"""

import json
import csv
from pathlib import Path

RESULTS_FILE = Path("evaluation/results.json")
CSV_FILE = Path("evaluation/results_summary.csv")
LOWLIGHTS_FILE = Path("evaluation/results_lowlights.md")

NUM_LOWLIGHTS = 3


def load_results():
    if not RESULTS_FILE.exists():
        print(f"ERROR: {RESULTS_FILE} not found — run evaluate.py first.")
        exit(1)
    with open(RESULTS_FILE) as f:
        return json.load(f)


def write_csv(data):
    records = data["results"]
    metric_names = [m["name"] for m in records[0]["metrics"]]

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "overall_success"] + metric_names)
        for r in records:
            scores_by_name = {m["name"]: m["score"] for m in r["metrics"]}
            writer.writerow(
                [r["input"], r["success"]]
                + [scores_by_name.get(name, "") for name in metric_names]
            )

    print(f"Wrote {CSV_FILE} — open in Excel, sort/filter by any metric column.")


def write_lowlights(data):
    records = data["results"]
    metric_names = [m["name"] for m in records[0]["metrics"]]

    lines = [f"# EpiRAG Eval — Lowlights (run: {data['run_at']})\n"]
    lines.append(f"Model: {data['model']} | Test cases: {data['num_test_cases']}\n")

    for metric_name in metric_names:
        # Hallucination is inverted — lower is worse-looking but actually better.
        # For lowlights we want the cases that look WORST for each metric's
        # intended direction, so sort ascending for normal metrics, descending
        # for Hallucination (where high score = bad).
        reverse = metric_name == "Hallucination"

        scored = []
        for r in records:
            for m in r["metrics"]:
                if m["name"] == metric_name:
                    scored.append((
                        m["score"], r["input"], m["reason"], m["success"],
                        r.get("actual_output", ""), r.get("expected_output", "")
                    ))

        scored.sort(key=lambda x: x[0], reverse=reverse)
        worst = scored[:NUM_LOWLIGHTS]

        lines.append(f"\n## {metric_name}\n")
        if metric_name == "Hallucination":
            lines.append("*(Lower is better for this metric — showing HIGHEST/worst scores)*\n")
        else:
            lines.append("*(Showing LOWEST scores)*\n")

        for score, question, reason, success, actual_output, expected_output in worst:
            lines.append(f"\n---\n**Score: {score:.3f}** (success: {success})")
            lines.append(f"\n**Q:** {question}")
            lines.append(f"\n**Reason:** {reason}")
            lines.append(f"\n**Actual Output (EpiRAG's answer):**\n{actual_output}")
            lines.append(f"\n**Expected Output (synthetic gold answer):**\n{expected_output}\n")

    with open(LOWLIGHTS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {LOWLIGHTS_FILE} — readable breakdown of the worst case per metric.")


if __name__ == "__main__":
    data = load_results()
    write_csv(data)
    write_lowlights(data)