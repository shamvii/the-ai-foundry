"""
The two-agent CrewAI system:

  Agent 1 (Tailor)    — rewrites resume content to match a job description.
  Agent 2 (Evaluator) — scores the tailored output (ATS match, gaps).

They run as separate crews/tasks, not one combined crew, on purpose:
Agent 1 never sees its own output being graded, and Agent 2 never sees the
base resume — it only judges what's in front of it against the JD. This
keeps the evaluation honest instead of self-reinforcing.
"""

import json
from crewai import Agent, Task, Crew, Process
from crewai.llm import LLM

from models import Resume, EvalResult
from guardrails import WORDS_PER_PAGE

# Swap model here if you want a cheaper/faster judge for Agent 2, e.g. "openai/gpt-4o-mini"
OPENAI_MODEL = "openai/gpt-4o"

llm = LLM(model=OPENAI_MODEL, temperature=0.3)


# ---------------------------------------------------------------------------
# Agent 1 — Tailor
# ---------------------------------------------------------------------------

tailor_agent = Agent(
    role="Resume Tailoring Specialist",
    goal=(
        "Rewrite resume summary, skills ordering, and experience/project bullets "
        "to align with a specific job description — without inventing experience, "
        "tools, metrics, or achievements that aren't already present in the base resume."
    ),
    backstory=(
        "You are a meticulous resume writer who has read thousands of job descriptions. "
        "You know how to mirror a JD's language and priorities honestly: reordering and "
        "rephrasing real experience to highlight what's relevant. "
        "\n\nABSOLUTE RULE — NO FABRICATION: every skill, tool, metric, and achievement "
        "in your output must already exist somewhere in the base resume. You may rephrase "
        "and reorder, but you may NEVER add a skill, technology, number, or outcome that "
        "isn't already present in the source. If the JD wants something the candidate's "
        "base resume doesn't show, do not invent it — simply don't claim it. When in doubt, "
        "leave it out rather than stretch the truth. This rule matters more than sounding "
        "like a perfect match. "
        "\n\nYou NEVER change company names, job titles, dates, or the education section — "
        "those are locked fields. Skills are organized into named categories (e.g. "
        "'AI & Automation', 'Leadership & Research'); you may reorder categories and "
        "reorder/trim skills within a category to prioritize relevance, but never invent "
        "a skill that isn't already listed somewhere. Certifications may be reordered by "
        "relevance but their name/issuer/date must never change. You avoid generic "
        "corporate filler phrases (e.g. 'synergy', 'spearheaded', 'results-driven') in "
        "favor of specific, concrete language."
        "\n\nYou are also disciplined about length: when a page budget is given, you WILL "
        "trim the number of bullets under older or less relevant roles (down to 1-2 sharp "
        "bullets each if needed) to make room for the most relevant, JD-aligned bullets "
        "under recent roles. You never remove an entire role, but you do cut freely within "
        "a role's bullet list to hit the target length. Prioritize bullets with concrete, "
        "quantified outcomes over general responsibility statements when deciding what to keep."
    ),
    llm=llm,
    verbose=True,
)


def build_tailor_task(base_resume: Resume, job_description: str, max_pages: float = 1.0) -> Task:
    target_words = int(max_pages * WORDS_PER_PAGE)
    return Task(
        description=(
            "Here is a candidate's base resume as JSON:\n\n"
            f"{base_resume.model_dump_json(indent=2)}\n\n"
            "Here is the job description to tailor the resume for:\n\n"
            f"{job_description}\n\n"
            "Rewrite the `summary` (write a strong 2-3 sentence one if the base resume's is "
            "empty), reorder skill categories and the skills within them to prioritize what's "
            "relevant to this JD, and rewrite `experience[].bullets` to emphasize relevant, "
            "real achievements in language that mirrors the JD.\n\n"
            f"LENGTH BUDGET: the final resume must fit on {max_pages} page(s), which is "
            f"roughly {target_words} words total across summary, skills, and all bullets "
            "combined. To hit this, cut the number of bullets under older/less-relevant roles "
            "down to whatever's necessary (as few as 1-2 sharp, quantified bullets for roles "
            "far from this JD's focus), while keeping the most JD-relevant recent role(s) "
            "detailed enough to make the case. Never remove an entire role, company, or the "
            "education/certifications sections — only trim within a role's bullet list.\n\n"
            "Do NOT change company, title, start_date, end_date, or add/remove experience "
            "entries. Do NOT change `education` at all. Do NOT change the name/issuer/date of "
            "any certification (reordering by relevance is fine). Do NOT invent skills, tools, "
            "metrics, or responsibilities not present in the base resume — every claim in your "
            "output must be traceable to something already in the base resume. Return the full "
            "resume in the same JSON shape, fully populated (carry over any fields you don't "
            "change, like certifications, education, and links, unmodified)."
        ),
        expected_output=(
            f"A complete tailored Resume object in the exact same schema as the input, "
            f"totaling roughly {target_words} words to fit {max_pages} page(s)."
        ),
        agent=tailor_agent,
        output_pydantic=Resume,
    )


def run_tailor(base_resume: Resume, job_description: str, max_pages: float = 1.0) -> Resume:
    task = build_tailor_task(base_resume, job_description, max_pages=max_pages)
    crew = Crew(agents=[tailor_agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    return result.pydantic  # the Resume object, per output_pydantic


# ---------------------------------------------------------------------------
# Agent 2 — Evaluator
# ---------------------------------------------------------------------------

evaluator_agent = Agent(
    role="ATS & Fit Evaluator",
    goal=(
        "Given a tailored resume and the job description it was tailored for, score how "
        "well it matches — keyword coverage, relevant emphasis, and any obvious gaps a "
        "recruiter or ATS system would flag. Be specific and honest, not encouraging."
    ),
    backstory=(
        "You are a former technical recruiter who has screened thousands of resumes "
        "against job descriptions. You know which keywords ATS systems weight heavily "
        "(skills, tools, certifications, years of experience) versus soft-skill fluff "
        "that barely matters. You call out real gaps instead of softening feedback."
    ),
    llm=llm,
    verbose=True,
)


def build_eval_task(tailored_resume: Resume, job_description: str) -> Task:
    return Task(
        description=(
            "Here is a tailored resume as JSON:\n\n"
            f"{tailored_resume.model_dump_json(indent=2)}\n\n"
            "Here is the job description it was tailored for:\n\n"
            f"{job_description}\n\n"
            "Score this resume against the job description. Identify which important "
            "keywords/skills from the JD are present (matched_keywords) and which important "
            "ones are missing entirely from the resume (missing_keywords). Compute an "
            "ats_match_pct (0-100) reflecting overall keyword/requirement coverage. Write "
            "section_notes on anything worth flagging (e.g. 'skills section buries the most "
            "relevant tool at the bottom of the list') and an overall_recommendation in 1-2 "
            "sentences."
        ),
        expected_output="An EvalResult object with ats_match_pct, matched/missing keywords, notes.",
        agent=evaluator_agent,
        output_pydantic=EvalResult,
    )


def run_evaluation(tailored_resume: Resume, job_description: str) -> EvalResult:
    task = build_eval_task(tailored_resume, job_description)
    crew = Crew(agents=[evaluator_agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    return result.pydantic
