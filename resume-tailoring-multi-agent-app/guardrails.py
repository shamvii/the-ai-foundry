"""
Guardrails: deterministic, code-based checks that run on every tailoring
result, no exceptions. These are pass/fail, not scored — a failure here
should block delivery, not just lower a number.

Deliberately kept rule-based (not LLM calls) so they're fast, free, and
don't themselves need evaluating.
"""

import re
from typing import List, Tuple
from models import Resume, GuardrailResult

# Words per page is a rough estimate for a standard single-column resume
# in 10-11pt font. Tune this against your own resume once you have real data.
WORDS_PER_PAGE = 550

BANNED_PHRASES = [
    "synergy", "synergies", "leveraged synergies", "spearheaded",
    "thought leader", "go-getter", "results-driven", "team player",
    "detail-oriented", "hardworking", "self-starter", "circle back",
    "move the needle", "low-hanging fruit", "think outside the box",
]

# Fields that must never change between base and tailored resume.
# Bullets are the only thing Agent 1 should be rewriting.
LOCKED_EXPERIENCE_FIELDS = ["company", "title", "start_date", "end_date"]


def _word_count(resume: Resume) -> int:
    parts = [resume.summary]
    for cat in resume.skills:
        parts.append(cat.category)
        parts.extend(cat.skills)
    for cert in resume.certifications:
        parts.append(cert.name)
        if cert.issuer:
            parts.append(cert.issuer)
    for edu in resume.education:
        parts.append(edu.institution)
        parts.append(edu.degree)
    for exp in resume.experience:
        parts.append(exp.company)
        parts.append(exp.title)
        parts.extend(exp.bullets)
    for proj in resume.projects:
        parts.append(proj.name)
        if proj.description:
            parts.append(proj.description)
        parts.extend(proj.bullets)
    return len(" ".join(parts).split())


def _extract_content_tokens(resume: Resume) -> set:
    """Lowercased, punctuation-stripped words from every part of the resume
    that could contain a CLAIM (skills, bullets, project descriptions).

    `summary` is deliberately EXCLUDED from this check: Agent 1 is explicitly
    instructed to write a fresh summary when the base resume's is empty (a
    common case), which means every word in a freshly-written summary would
    otherwise look "new" and trigger false fabrication flags on totally
    generic phrasing ("experienced", "proven", "background"). A summary is
    supposed to be a synthesis in new words, not a verbatim echo — checking
    it the same way as bullets/skills produces near-constant false positives.

    Education and certifications are also excluded — they're locked/reorder-
    only fields, not places Agent 1 should be adding claims."""
    text_parts = []
    for cat in resume.skills:
        text_parts.extend(cat.skills)
    for exp in resume.experience:
        text_parts.extend(exp.bullets)
    for proj in resume.projects:
        if proj.description:
            text_parts.append(proj.description)
        text_parts.extend(proj.bullets)
    text = " ".join(text_parts).lower()
    tokens = re.findall(r"[a-z0-9\+\#\.]+", text)
    return set(tokens)


def check_locked_fields(base: Resume, tailored: Resume) -> List[str]:
    """Company names, titles, dates, and education must never be altered
    by the tailor agent."""
    failures = []

    if len(base.experience) != len(tailored.experience):
        failures.append(
            f"Experience entry count changed ({len(base.experience)} -> {len(tailored.experience)}); "
            "tailoring should never add or remove roles."
        )
    else:
        for i, (b, t) in enumerate(zip(base.experience, tailored.experience)):
            for field in LOCKED_EXPERIENCE_FIELDS:
                if getattr(b, field) != getattr(t, field):
                    failures.append(
                        f"Experience[{i}].{field} changed: '{getattr(b, field)}' -> '{getattr(t, field)}' "
                        "(this field should never be edited by the tailor agent)"
                    )

    # Education should never be touched at all — compare as full lists
    base_edu = [(e.institution, e.degree, e.start_date, e.end_date) for e in base.education]
    tailored_edu = [(e.institution, e.degree, e.start_date, e.end_date) for e in tailored.education]
    if base_edu != tailored_edu:
        failures.append("Education section was modified — this should never change during tailoring.")

    return failures


def check_certifications_unaltered(base: Resume, tailored: Resume) -> List[str]:
    """Certifications can be REORDERED by relevance, but their content must
    not change — compare as sets, not ordered lists."""
    base_set = {(c.name, c.issuer, c.date) for c in base.certifications}
    tailored_set = {(c.name, c.issuer, c.date) for c in tailored.certifications}
    if base_set != tailored_set:
        added = tailored_set - base_set
        removed = base_set - tailored_set
        msg = "Certifications changed content (reordering is fine, but content must match)."
        if added:
            msg += f" Added: {added}."
        if removed:
            msg += f" Removed: {removed}."
        return [msg]
    return []


def check_no_fabrication(base: Resume, tailored: Resume, allowance: int = 3, hard_fail_at: int = 12) -> Tuple[List[str], List[str]]:
    """
    Lightweight heuristic: flag content words that appear in the tailored resume
    but nowhere in the base resume. Not perfect — it will miss paraphrased
    fabrications and can false-positive on synonyms — but it catches the most
    dangerous failure mode (a tool/skill/metric invented wholesale).

    Returns (failures, warnings):
      - A small number of new words (up to `allowance`) is normal JD-language
        bleed-through and isn't flagged at all.
      - Above `allowance` but below `hard_fail_at`: a warning — read it, but it
        won't block delivery on its own (could be legitimate paraphrasing).
      - At or above `hard_fail_at`: treated as a hard failure — that many new
        content words is a strong signal of wholesale fabrication, not rephrasing.

    This is still a heuristic, not a guarantee — it catches volume, not every
    single fabricated phrase. Always read the tailored resume yourself before
    sending it anywhere; no automated check replaces that.
    """
    base_tokens = _extract_content_tokens(base)
    tailored_tokens = _extract_content_tokens(tailored)

    stopwords = {
        "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with",
        "at", "by", "from", "as", "is", "was", "are", "were", "this", "that",
        "using", "used", "via", "into", "across", "including", "based",
    }
    new_tokens = (tailored_tokens - base_tokens) - stopwords
    suspicious = sorted(t for t in new_tokens if len(t) > 3 and not t.isdigit())

    if len(suspicious) == 0 or len(suspicious) <= allowance:
        return [], []

    preview = f"{', '.join(suspicious[:15])}{'...' if len(suspicious) > 15 else ''}"
    message = (
        f"{len(suspicious)} new content words appeared in the tailored resume that don't "
        f"appear in the base resume (allowance is {allowance}). Review for fabrication: {preview}"
    )

    if len(suspicious) >= hard_fail_at:
        return [f"LIKELY FABRICATION — {message}"], []
    return [], [message]


def check_banned_phrases(tailored: Resume) -> List[str]:
    failures = []
    all_text = " ".join(
        [tailored.summary]
        + [b for exp in tailored.experience for b in exp.bullets]
        + [b for proj in tailored.projects for b in proj.bullets]
    ).lower()
    for phrase in BANNED_PHRASES:
        if phrase in all_text:
            failures.append(f"Banned filler phrase found: '{phrase}'")
    return failures


def check_page_length(tailored: Resume, max_pages: float = 2.0) -> Tuple[List[str], int, float]:
    word_count = _word_count(tailored)
    estimated_pages = round(word_count / WORDS_PER_PAGE, 2)
    failures = []
    if estimated_pages > max_pages:
        failures.append(
            f"Estimated {estimated_pages} pages, exceeds the {max_pages}-page limit "
            f"({word_count} words at ~{WORDS_PER_PAGE} words/page). Trim bullets before delivering."
        )
    return failures, word_count, estimated_pages


def run_guardrails(base: Resume, tailored: Resume, max_pages: float = 2.0) -> GuardrailResult:
    failures: List[str] = []
    warnings: List[str] = []

    failures.extend(check_locked_fields(base, tailored))
    failures.extend(check_certifications_unaltered(base, tailored))
    failures.extend(check_banned_phrases(tailored))

    fabrication_failures, fabrication_warnings = check_no_fabrication(base, tailored)
    failures.extend(fabrication_failures)
    warnings.extend(fabrication_warnings)

    page_failures, word_count, page_count = check_page_length(tailored, max_pages)
    failures.extend(page_failures)

    return GuardrailResult(
        passed=len(failures) == 0,
        failures=failures,
        warnings=warnings,
        estimated_word_count=word_count,
        estimated_page_count=page_count,
    )
