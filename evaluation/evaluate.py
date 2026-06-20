"""
EpiRAG Evaluation — Step 2-3: run pipeline + score.

Usage:
    python evaluation/evaluate.py
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    FaithfulnessMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    AnswerRelevancyMetric,
    HallucinationMetric,
)
from deepeval import evaluate

from app.pipeline import run_pipeline

GOLDENS_FILE = Path("evaluation/goldens_review.json")
RESULTS_FILE = Path("evaluation/results.json")
EVAL_MODEL = "gpt-4o-mini"  # judge model for metrics, cost control

# Primary metrics — these are the ones that actually matter for a
# methodology-advice tool: is it making things up, is retrieval pulling
# the right paper.
PRIMARY_THRESHOLD = 0.7
# Secondary — useful signal, lower priority for a first pass.
SECONDARY_THRESHOLD = 0.5


def load_goldens():
    if not GOLDENS_FILE.exists():
        print(f"ERROR: {GOLDENS_FILE} not found — run generate_goldens.py first, "
              f"then review/trim it.")
        sys.exit(1)
    with open(GOLDENS_FILE) as f:
        return json.load(f)


def build_test_cases(goldens):
    test_cases = []
    for g in goldens:
        result = run_pipeline(g["input"])

        # pipeline.py returns retrieved_chunks as a list of dicts with the
        # actual chunk text under "text" — extract that for DeepEval.
        retrieved_chunks = result.get("retrieved_chunks", [])
        retrieval_context = [c["text"] for c in retrieved_chunks if c.get("text")]
        if not retrieval_context:
            print(f"WARNING: no chunks retrieved for question "
                  f"'{g['input'][:60]}...' — contextual/faithfulness metrics "
                  f"will fail or be meaningless for this case.")

        # HallucinationMetric needs a separate "context" field — the
        # ground-truth source context the golden was generated from
        # (saved by generate_goldens.py), not the live retrieval result.
        context = g.get("context")
        if not context:
            print(f"WARNING: no source context saved for question "
                  f"'{g['input'][:60]}...' — Hallucination metric will fail "
                  f"for this case.")

        test_cases.append(
            LLMTestCase(
                input=g["input"],
                actual_output=result["answer"],
                expected_output=g.get("expected_output"),
                retrieval_context=retrieval_context,
                context=context,
            )
        )
    return test_cases


def get_metrics():
    return [
        FaithfulnessMetric(threshold=PRIMARY_THRESHOLD, model=EVAL_MODEL),
        ContextualPrecisionMetric(threshold=PRIMARY_THRESHOLD, model=EVAL_MODEL),
        ContextualRecallMetric(threshold=PRIMARY_THRESHOLD, model=EVAL_MODEL),
        AnswerRelevancyMetric(threshold=SECONDARY_THRESHOLD, model=EVAL_MODEL),
        HallucinationMetric(threshold=SECONDARY_THRESHOLD, model=EVAL_MODEL),
    ]


def save_results(eval_result):
    records = []
    for test_result in eval_result.test_results:
        record = {
            "input": test_result.input,
            "actual_output": test_result.actual_output,
            "expected_output": test_result.expected_output,
            "success": test_result.success,
            "metrics": [],
        }
        for m in test_result.metrics_data:
            record["metrics"].append({
                "name": m.name,
                "score": m.score,
                "threshold": m.threshold,
                "success": m.success,
                "reason": m.reason,
            })
        records.append(record)

    output = {
        "run_at": datetime.now().isoformat(),
        "model": EVAL_MODEL,
        "num_test_cases": len(records),
        "results": records,
    }

    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResults saved to {RESULTS_FILE}")

    # Quick summary per metric
    summary = {}
    for record in records:
        for m in record["metrics"]:
            summary.setdefault(m["name"], []).append(m["score"])

    print("\n--- Summary (mean score per metric) ---")
    for name, scores in summary.items():
        avg = sum(scores) / len(scores)
        print(f"  {name}: {avg:.3f} (n={len(scores)})")


if __name__ == "__main__":
    goldens = load_goldens()
    print(f"Loaded {len(goldens)} reviewed goldens.")

    print("Running EpiRAG pipeline on each question...")
    test_cases = build_test_cases(goldens)

    print("Scoring with DeepEval metrics...")
    metrics = get_metrics()
    eval_result = evaluate(test_cases, metrics)

    save_results(eval_result)