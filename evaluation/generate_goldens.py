"""
EpiRAG Evaluation — DeepEval

Step 1: Generate candidate gold-standard questions from the corpus PDFs
        using DeepEval's Synthesizer (LLM-generated, exported for manual review).
Step 2: Run the live EpiRAG pipeline against the reviewed goldens.
Step 3: Score with DeepEval metrics — Faithfulness + Contextual Precision/Recall
        as primary; Answer Relevancy + Hallucination as secondary.

Usage:
    python evaluation/generate_goldens.py   # Step 1 — writes goldens_review.json
    # --- manually review/edit goldens_review.json here ---
    python evaluation/evaluate.py           # Steps 2-3 — runs pipeline + scores
"""

import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from deepeval.synthesizer import Synthesizer
from deepeval.synthesizer.config import StylingConfig, ContextConstructionConfig

PAPERS_DIR = Path("data/papers")
GOLDENS_FILE = Path("evaluation/goldens_review.json")
GOLDENS_PER_DOC = 3  # 9 papers -> ~27 candidates to review/trim down to ~15-20

# Use gpt-4o-mini for the synthesizer judge to keep generation cost down,
# consistent with the rest of the project's model choice.
SYNTHESIZER_MODEL = "gpt-4o-mini"


def generate_goldens():
    styling_config = StylingConfig(
        scenario="A junior researcher or non-statistician asking for help "
                 "evaluating the methodology of their own observational study.",
        task="Answer methodological questions grounded strictly in the "
             "retrieved epidemiological literature.",
        input_format="A specific, realistic methodological question — not a "
                      "vague or overly broad one.",
        expected_output_format="A grounded, cited explanation a junior "
                                 "researcher could act on."
    )

    # One context per document, GOLDENS_PER_DOC goldens per context ->
    # roughly GOLDENS_PER_DOC questions per paper.
    context_config = ContextConstructionConfig(
        max_contexts_per_document=1,
    )

    synthesizer = Synthesizer(model=SYNTHESIZER_MODEL, styling_config=styling_config)

    pdf_paths = [str(p) for p in sorted(PAPERS_DIR.glob("*.pdf"))]
    if not pdf_paths:
        print(f"ERROR: no PDFs found in {PAPERS_DIR}")
        sys.exit(1)

    print(f"Generating up to {GOLDENS_PER_DOC} goldens per document "
          f"across {len(pdf_paths)} papers...")

    synthesizer.generate_goldens_from_docs(
        document_paths=pdf_paths,
        max_goldens_per_context=GOLDENS_PER_DOC,
        context_construction_config=context_config,
    )

    goldens = synthesizer.synthetic_goldens
    print(f"Generated {len(goldens)} candidate goldens.")

    GOLDENS_FILE.parent.mkdir(exist_ok=True)
    with open(GOLDENS_FILE, "w") as f:
        json.dump(
            [
                {
                    "input": g.input,
                    "expected_output": g.expected_output,
                    "context": g.context,
                    "source_file": getattr(g, "source_file", None),
                }
                for g in goldens
            ],
            f,
            indent=2,
            default=str,
        )

    print(f"\nWrote {GOLDENS_FILE} — review and trim before running eval.")
    print("Remove any malformed, too-vague, or off-topic questions, "
          "and lightly edit expected_output if it's off.")


if __name__ == "__main__":
    generate_goldens()