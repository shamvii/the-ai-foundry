# Resume Tailoring Agent

A two-agent CrewAI system that tailors a resume to a job description, with
deterministic guardrails between the agents and an offline eval harness for
tracking quality over time.

## Architecture

```
base resume (JSON) + job description
        |
        v
  Agent 1: Tailor        <- rewrites summary/skills/bullets, never touches
        |                    company/title/dates, never invents experience
        v
  Guardrails (code)      <- hard pass/fail: locked fields, banned phrases,
        |                    page length, fabrication heuristic (warning)
        v (only if passed)
  Agent 2: Evaluator     <- ATS match %, matched/missing keywords, notes
        |
        v
  TailoringReport (JSON)
```

Guardrails run as plain Python, not an LLM call — fast, free, deterministic,
and they don't themselves need evaluating. Agent 2 never sees the base
resume, only the tailored output and the JD, so its score isn't biased by
"knowing" what changed.

## Setup

```bash
python -m venv venv
source venv/bin/activate       # or venv\Scripts\activate on Windows
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
```

CrewAI reads `OPENAI_API_KEY` from the environment automatically via
the `openai/gpt-4o` model string used in `agents.py`.

## Exporting to Word or PDF

This is a separate, manual step — `export_resume.py` never runs
automatically as part of `main.py`. Review the tailoring report first
(check the guardrail results and ATS score), and only export once you're
happy with the content.

```bash
pip install python-docx reportlab   # only needed for export
python export_resume.py --input output/tailoring_report.json --format both
```

- `--input` accepts either the full `tailoring_report.json` (it pulls out
  `tailored_resume` automatically) or a raw resume JSON like
  `sample_data/base_resume.json` — useful if you just want your base
  resume exported without tailoring.
- `--format` is `docx`, `pdf`, or `both`.
- `--out` sets the output path without an extension (default `output/resume`
  → produces `output/resume.docx` and/or `output/resume.pdf`).
- `--template path/to/your_resume.docx` (optional) — matches the fonts and
  sizes from a sample resume you already like, instead of the plain default.
  Example: `python export_resume.py --input output/tailoring_report.json --format both --template sample_data/my_old_resume.docx`

  **What this does and doesn't do:** it lifts font choices and sizes
  (name size, section heading style, body font) via a few heuristics —
  it does NOT clone columns, tables, colors, or graphic templates. Works
  well if your sample is a standard single-column resume; a heavily
  designed template will still need manual touch-ups after export.
  Accepts either `.docx` or `.pdf` as the sample — for PDF, run
  `pip install pdfplumber` first. PDF font extraction only works if the
  PDF has real selectable text (exported from Word/Google Docs/etc.) —
  a scanned image or a photo saved as PDF has no font metadata to read,
  and the tool falls back to the default styling in that case.
  PDF export (the output, not the template) can't use arbitrary fonts
  either way (reportlab only ships a handful of built-in fonts), so
  custom fonts get mapped to the closest equivalent — DOCX export will
  match your sample's actual fonts more precisely than PDF output will.

## Running it

```bash
python main.py --resume sample_data/base_resume.json --jd sample_data/sample_jd.txt
```

This prints the tailoring report to the console and saves the full JSON
(tailored resume + guardrail results + evaluation) to
`output/tailoring_report.json`.

To use your own resume: copy `sample_data/base_resume.json`, fill in your
real experience in the same schema, and point `--resume` at it. Job
descriptions are just plain `.txt` files — paste the JD in as-is.

Optional flags:
- `--max-pages 1.5` — tighten or loosen the page-length guardrail
- `--out path/to/report.json` — change where the report is saved

## Running the eval harness

The eval harness is separate from the live pipeline on purpose — it's for
testing whether a prompt/guardrail change made things better or worse, not
something that runs on every real tailoring request.

1. Create `evals/test_jds/` and drop in a few real job descriptions you've
   actually applied to (as `.txt` files) — 5-10 is a good starting set.
2. Run:
   ```bash
   python evals/eval_harness.py
   ```
3. It reports guardrail pass rate and average/range of ATS match scores
   across all test JDs, and saves full results to
   `evals/last_run_results.json`.

Re-run this any time you tweak a prompt in `agents.py` or a rule in
`guardrails.py` — if the average ATS match drops or the pass rate falls,
you've caught a regression before it hit a real application.

## What's a guardrail vs. an eval, and why it matters

- **Guardrails** (`guardrails.py`) run on every single tailoring request,
  in real time, and can block delivery. They're intentionally simple and
  rule-based — no LLM call, no ambiguity, no cost.
- **Evals** (`evals/eval_harness.py`) run offline, against a fixed test set,
  whenever you change something. They tell you if the *system* improved,
  not whether one specific output was good.

Conflating the two leads to either guardrails that are too slow/expensive
to run live, or evals that only ever tell you about one request instead of
tracking quality over time.

## Known limitations (by design, for now)

- **Fabrication check is heuristic**, not semantic — it flags new content
  words, which can false-positive on legitimate JD terminology reused in
  phrasing. It's a warning, not a hard block, on purpose. Read the flagged
  words yourself before trusting a tailored resume fully.
- **No auth, no multi-user storage** — this is built for personal/small-scale
  use. One base resume, overwritten each run. If you ever need to support
  other people, the data model would need a per-user resume store.
- **No N8N wiring yet** — this is the standalone Python pipeline first. Once
  it's proven out on real JDs, wrap `main.py`'s logic as an N8N node/webhook
  rather than building the orchestration twice.
- **Page-length is estimated, not exact** — it's a words-per-page heuristic
  (`WORDS_PER_PAGE` in `guardrails.py`), not actual PDF rendering. Tune that
  constant against your own resume's real page breaks.

## Next steps (not built yet)

1. Wire this into N8N as the orchestration layer per the original plan.
2. Build the editable UI once the JSON schema and scoring are stable —
   render each section (summary, skills, experience, certs, projects,
   links) as independently editable fields, with the guardrail/eval report
   shown alongside.
3. Consider swapping the fabrication guardrail's heuristic for an LLM-based
   semantic check once you've seen enough false positives/negatives from
   real usage to know it's worth the added cost per run.
