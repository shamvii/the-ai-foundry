"""
Orchestrator for the resume tailoring pipeline.

Flow:
    base resume + job description
        -> Agent 1 (Tailor)
        -> Guardrails (deterministic pass/fail)
        -> if passed: Agent 2 (Evaluator) for ATS scoring
        -> TailoringReport

Guardrails sit as a hard gate BETWEEN the two agents on purpose: there's no
point scoring output that already violates a hard rule (fabricated content,
changed dates, blown page limit). Fix that first.

This is a local CLI for now — N8N orchestration is the next layer once this
core pipeline is proven out.
"""

import argparse
import json
import sys
from pathlib import Path

from models import Resume, TailoringReport
from guardrails import run_guardrails
from agents import run_tailor, run_evaluation


def load_resume(path: str) -> Resume:
    with open(path, "r") as f:
        data = json.load(f)
    return Resume.model_validate(data)


def load_job_description(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def tailor_and_evaluate(base_resume: Resume, job_description: str, max_pages: float = 1.0) -> TailoringReport:
    print("\n=== Step 1: Tailoring resume (Agent 1) ===\n")
    tailored = run_tailor(base_resume, job_description, max_pages=max_pages)

    print("\n=== Step 2: Running guardrails ===\n")
    guardrail_result = run_guardrails(base_resume, tailored, max_pages=max_pages)

    if not guardrail_result.passed:
        print("\n⚠️  GUARDRAILS FAILED — stopping before evaluation.\n")
        for f in guardrail_result.failures:
            print(f"  ✗ {f}")
        for w in guardrail_result.warnings:
            print(f"  ⚠ {w}")
        return TailoringReport(tailored_resume=tailored, guardrails=guardrail_result, evaluation=None)

    print("✓ Guardrails passed" + (f" (with {len(guardrail_result.warnings)} warning(s))" if guardrail_result.warnings else ""))
    for w in guardrail_result.warnings:
        print(f"  ⚠ {w}")

    print("\n=== Step 3: Evaluating fit (Agent 2) ===\n")
    evaluation = run_evaluation(tailored, job_description)

    return TailoringReport(tailored_resume=tailored, guardrails=guardrail_result, evaluation=evaluation)


def print_report(report: TailoringReport):
    print("\n" + "=" * 60)
    print("TAILORING REPORT")
    print("=" * 60)

    g = report.guardrails
    print(f"\nGuardrails: {'PASSED' if g.passed else 'FAILED'}")
    print(f"Estimated length: {g.estimated_word_count} words (~{g.estimated_page_count} pages)")

    if report.evaluation:
        e = report.evaluation
        print(f"\nATS Match: {e.ats_match_pct}%")
        print(f"Matched keywords: {', '.join(e.matched_keywords) if e.matched_keywords else '(none listed)'}")
        print(f"Missing keywords: {', '.join(e.missing_keywords) if e.missing_keywords else '(none)'}")
        print(f"\nNotes: {e.section_notes}")
        print(f"Recommendation: {e.overall_recommendation}")
    else:
        print("\n(No evaluation — guardrails blocked delivery. Fix the failures above and re-run.)")

    print("\n" + "=" * 60)


def save_report(report: TailoringReport, out_path: str):
    Path(out_path).write_text(report.model_dump_json(indent=2))
    print(f"\nFull report saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tailor a resume to a job description.")
    parser.add_argument("--resume", required=True, help="Path to base resume JSON")
    parser.add_argument("--jd", required=True, help="Path to job description text file")
    parser.add_argument("--max-pages", type=float, default=1.0, help="Page length guardrail limit")
    parser.add_argument("--out", default="output/tailoring_report.json", help="Where to save the full report JSON")
    args = parser.parse_args()

    if not Path(args.resume).exists():
        sys.exit(f"Resume file not found: {args.resume}")
    if not Path(args.jd).exists():
        sys.exit(f"Job description file not found: {args.jd}")

    base_resume = load_resume(args.resume)
    job_description = load_job_description(args.jd)

    report = tailor_and_evaluate(base_resume, job_description, max_pages=args.max_pages)
    print_report(report)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    save_report(report, args.out)
