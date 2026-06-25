from __future__ import annotations

from typing import Any

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
    research_route: str = "Auto"
    data_available: str = ""
    variables_or_themes: str = ""
    preferred_contribution: str = ""
    keywords: str = ""
    max_ideas: int = 6
    resource_result_limit: int = 6
    include_source_search: bool = True
    include_older_foundational: bool = True
    include_research_resource_search: bool = True

    @field_validator("max_ideas")
    @classmethod
    def validate_max_ideas(cls, value: int) -> int:
        return max(3, min(int(value), 10))

    @field_validator("resource_result_limit")
    @classmethod
    def validate_resource_limit(cls, value: int) -> int:
        return max(3, min(int(value), 12))


class ResearchResourceRequest(BaseModel):
    article_title: str = ""
    title: str = ""
    research_area: str = ""
    source_mode: str = "Develop as a new independent article"
    article_type: str = "Empirical research article"
    research_route: str = "Auto"
    context: str = ""
    objective: str = ""
    objectives: str = ""
    variables_constructs: str = ""
    variables_or_themes: str = ""
    methodology: str = ""
    data_available: str = ""
    extraction_focus: str = ""
    instrument_requirements: str = ""
    max_results: int = 6
    include_live_search: bool = True

    @field_validator("max_results")
    @classmethod
    def validate_max_results(cls, value: int) -> int:
        return max(3, min(int(value), 12))


class ArticleSourceSearchRequest(BaseModel):
    query: str = ""
    article_title: str = ""
    research_area: str = ""
    source_thesis_title: str = ""
    extraction_focus: str = ""
    context: str = ""
    objectives: str = ""
    theory_or_framework: str = ""
    variables_constructs: str = ""
    key_findings: str = ""
    methodology: str = ""
    article_type: str = "Empirical research article"
    academic_level: str = "Research Masters (e.g. MPhil)"
    max_results: int = 12
    include_older_foundational: bool = True

    @field_validator("max_results")
    @classmethod
    def validate_max_results(cls, value: int) -> int:
        return max(3, min(int(value), 30))


class JournalArticleRequest(BaseModel):
    article_title: str = Field(..., min_length=3)
    research_area: str = ""
    source_mode: str = "Extract from a completed thesis or dissertation"
    draft_stage: str = "full_article"
    source_thesis_title: str = ""
    thesis_source_material: str = ""
    previous_sections: str = ""
    continuation_material: str = ""
    extraction_focus: str = ""
    target_journal: str = ""
    author_guidelines: str = ""
    article_type: str = "Empirical research article"
    academic_level: str = "Research Masters (e.g. MPhil)"
    research_route: str = "Auto"
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
    instrument_requirements: str = ""
    include_instrument_draft: bool = False
    word_limit: str = "6000-8000"
    citation_style: str = "APA 7th"
    include_source_search: bool = True
    include_older_foundational: bool = True
    include_research_resource_search: bool = True
    source_search_terms: str = ""
    source_bank: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_sources: dict[str, Any] = Field(default_factory=dict)
    research_resources: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_bank")
    @classmethod
    def validate_source_bank(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in value if isinstance(item, dict)][:120]

    @field_validator("draft_stage")
    @classmethod
    def validate_stage(cls, value: str) -> str:
        allowed = {"full_article", "initial_to_methods", "continuation_after_results"}
        return value if value in allowed else "full_article"


class ArticleExportRequest(BaseModel):
    article_title: str = "Journal Article Draft"
    article_text: str = Field(..., min_length=10)
