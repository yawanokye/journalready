from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


ARTICLE_TYPES = (
    "Empirical research article",
    "Systematic review",
    "Scoping review",
    "Conceptual article",
    "Methodological article",
    "Case study article",
    "Policy or practice article",
    "Short communication",
)


class ArticleIdeaRequest(BaseModel):
    research_area: str = Field(..., min_length=3)
    source_mode: str = "Extract from a completed thesis or dissertation"
    thesis_title: str = ""
    thesis_material: str = ""
    discipline: str = ""
    context: str = ""
    target_journal: str = ""
    journal_scope: str = ""
    article_type: str = "Empirical research article"
    methodology: str = ""
    data_available: str = ""
    variables_or_themes: str = ""
    preferred_contribution: str = ""
    keywords: str = ""
    max_ideas: int = 6
    include_source_search: bool = True
    include_older_foundational: bool = True

    @field_validator("max_ideas")
    @classmethod
    def validate_max_ideas(cls, value: int) -> int:
        return max(3, min(int(value), 10))


class JournalArticleRequest(BaseModel):
    article_title: str = Field(..., min_length=3)
    research_area: str = ""
    source_mode: str = "Extract from a completed thesis or dissertation"
    source_thesis_title: str = ""
    thesis_source_material: str = ""
    extraction_focus: str = ""
    target_journal: str = ""
    author_guidelines: str = ""
    article_type: str = "Empirical research article"
    academic_level: str = "Research Masters (e.g. MPhil)"
    methodology: str = ""
    context: str = ""
    research_problem: str = ""
    objectives: str = ""
    theory_or_framework: str = ""
    variables_constructs: str = ""
    data_and_results: str = ""
    key_findings: str = ""
    contribution: str = ""
    references_notes: str = ""
    word_limit: str = "6000-8000"
    citation_style: str = "APA 7th"
    include_source_search: bool = True
    include_older_foundational: bool = True


class ArticleExportRequest(BaseModel):
    article_title: str = "Journal Article Draft"
    article_text: str = Field(..., min_length=10)
