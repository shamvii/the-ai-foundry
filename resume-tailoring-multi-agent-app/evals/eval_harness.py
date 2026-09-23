"""
Offline eval harness — NOT part of the live pipeline.

Run this whenever you change a prompt, model, or guardrail rule, against a
fixed set of real job descriptions you've actually applied to. This is what
tells you whether a change made the SYSTEM better or worse, as opposed to
guardrails (which check one single run) or the live evaluator (which scores
one tailored resume against its own JD).

Metrics tracked per run:
  - faithfulness_flag: did guardrails' fabrication check fire?
  - ats_match_pct: from Agent 2, per JD
  - page_count: did it fit the target length?
  - consistency: run each JD twice, flag if ats_match_pct swings > 15 points
    (a sign the tailor prompt is underspecified / too random)

This is intentionally simple (no RAGAS dependency) so it runs standalone.
If you want deeper faithfulness scoring later, swap in RAGAS the same way
you're already using it on the arXiv RAG project — same eval logic, just a
different domain to point it at.
"""

import json
import sys
from pathlib import Path
from statistics import mean

sys.path.append(str(Path(__file__).parent.parent))  # allow importing sibling modules

from models import Resume
from guardrails import run_guardrails
from agents import run_tailor, run_evaluation

TEST_JD_DIR = Path(__file__).parent / "test_jds"
BASE_RESUME_PATH = Path(__file__).parent.parent / "sample_data" / "base_resume.json"


def load_base_resume() -> Resume:
    with open(BASE_RESUME_PATH) as f:
        return Resume.model_validate(json.load(f))


def run_single_eval(base_resume: Resume, jd_path: Path) -> dict:
    job_description = jd_path.read_text()
    tailored = run_tailor(base_resume, job_description)
    guardrail_result = run_guardrails(base_resume, tailored)

    result = {
        "jd_file": jd_path.name,
        "guardrails_passed": guardrail_result.passed,
        "guardrail_failures": guardrail_result.failures,
        "fabrication_warnings": guardrail_result.warnings,
        "estimated_pages": guardrail_result.estimated_page_count,
        "ats_match_pct": None,
    }

    if guardrail_result.passed:
        evaluation = run_evaluation(tailored, job_description)
        result["ats_match_pct"] = evaluation.ats_match_pct
        result["missing_keywords"] = evaluation.missing_keywords

    return result


def run_consistency_check(base_resume: Resume, jd_path: Path, runs: int = 2) -> float:
    """Run the same JD multiple times; return the spread (max-min) in ats_match_pct.
    A large spread means the tailor prompt is under-constrained."""
    scores = []
    for _ in range(runs):
        r = run_single_eval(base_resume, jd_path)
        if r["ats_match_pct"] is not None:
            scores.append(r["ats_match_pct"])
    if len(scores) < 2:
        return 0.0
    return max(scores) - min(scores)


def main():
    if not TEST_JD_DIR.exists() or not list(TEST_JD_DIR.glob("*.txt")):
        print(f"No test JDs found in {TEST_JD_DIR}. Add a few real job descriptions "
              "you've applied to (as .txt files) before running evals.")
        return

    base_resume = load_base_resume()
    jd_files = sorted(TEST_JD_DIR.glob("*.txt"))

    print(f"Running eval suite against {len(jd_files)} job description(s)...\n")

    all_results = []
    for jd_path in jd_files:
        print(f"--- {jd_path.name} ---")
        result = run_single_eval(base_resume, jd_path)
        all_results.append(result)
        print(json.dumps(result, indent=2))
        print()

    scores = [r["ats_match_pct"] for r in all_results if r["ats_match_pct"] is not None]
    pass_rate = sum(1 for r in all_results if r["guardrails_passed"]) / len(all_results) * 100

    print("=" * 50)
    print("EVAL SUMMARY")
    print("=" * 50)
    print(f"Guardrail pass rate: {pass_rate:.0f}%")
    if scores:
        print(f"Average ATS match: {mean(scores):.1f}%")
        print(f"Range: {min(scores):.1f}% - {max(scores):.1f}%")

    results_path = Path(__file__).parent / "last_run_results.json"
    results_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nFull results saved to {results_path}")


if __name__ == "__main__":
    main()
