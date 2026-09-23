"""
Data models for the resume tailoring agent.

Schema updated to match Shamvi's real resume structure:
  - Skills are grouped into categories (e.g. "Core Competencies", "AI & Automation"),
    not a flat list — this is how the actual resume is organized and how a
    recruiter/ATS scans it.
  - Certifications carry an issuer and date.
  - Education is now a first-class section (was missing before).
  - Projects stays as a simple optional section — the real resume mostly just
    links out to a portfolio/GitHub rather than listing individual projects
    with bullets, so this can be empty without breaking anything.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class ExperienceEntry(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str  # "Present" is fine
    location: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    name: str
    description: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)


class SkillCategory(BaseModel):
    category: str          # e.g. "AI & Automation"
    skills: List[str] = Field(default_factory=list)


class Certification(BaseModel):
    name: str
    issuer: Optional[str] = None
    date: Optional[str] = None


class EducationEntry(BaseModel):
    institution: str
    degree: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Links(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: List[str] = Field(default_factory=list)


class Resume(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    links: Links = Field(default_factory=Links)
    summary: str = ""  # ok to be empty in the base resume — Agent 1 can craft one when tailoring
    skills: List[SkillCategory] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    education: List[EducationEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)


class GuardrailResult(BaseModel):
    passed: bool
    failures: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    estimated_word_count: int = 0
    estimated_page_count: float = 0.0


class EvalResult(BaseModel):
    """Output of the Evaluator agent — softer, LLM-judged quality signals.
    Guardrails (above) are the hard pass/fail gate; this is the score layer."""
    ats_match_pct: float = Field(ge=0, le=100)
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    section_notes: str = ""
    overall_recommendation: str = ""


class TailoringReport(BaseModel):
    """The full result returned to the user for one tailoring run."""
    tailored_resume: Resume
    guardrails: GuardrailResult
    evaluation: Optional[EvalResult] = None  # None if guardrails failed and we stopped early
