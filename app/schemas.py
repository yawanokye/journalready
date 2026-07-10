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
    max_ideas: int = 10
    resource_result_limit: int = 6
    include_source_search: bool = True
    include_older_foundational: bool = True
    include_research_resource_search: bool = True

    @field_validator("max_ideas")
    @classmethod
    def validate_max_ideas(cls, value: int) -> int:
        return max(3, min(int(value), 20))

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
    target_word_count: int | None = None
    article_structure: str = ""
    long_write_mode: str = "auto"
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

    @field_validator("target_word_count")
    @classmethod
    def validate_target_word_count(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return max(1200, min(int(value), 30000))

    @field_validator("long_write_mode")
    @classmethod
    def validate_long_write_mode(cls, value: str) -> str:
        allowed = {"auto", "single_pass", "batch"}
        return value if value in allowed else "auto"


class ArticleExportRequest(BaseModel):
    article_title: str = "Journal Article Draft"
    article_text: str = Field(..., min_length=10)


class ArticleRevisionRequest(BaseModel):
    article_title: str = Field(..., min_length=3)
    article_text: str = Field(..., min_length=100)
    review_comments: str = ""
    target_journal: str = ""
    journal_scope: str = ""
    author_guidelines: str = ""
    article_type: str = "Empirical research article"
    citation_style: str = "APA 7th"
    word_limit: str = ""
    research_area: str = ""
    context: str = ""
    methodology: str = ""
    data_and_results: str = ""
    contribution_claim: str = ""
    revision_level: str = "Publication-readiness overhaul"
    revision_goals: str = ""
    academic_level: str = "PhD"
    strengthen_conceptualisation: bool = True
    strengthen_contribution: bool = True
    assess_method_fit: bool = True
    assess_analysis: bool = True
    deepen_discussion: bool = True
    strengthen_recommendations: bool = True
    include_reviewer_response_matrix: bool = True
    include_source_search: bool = True
    include_older_foundational: bool = True
    source_search_terms: str = ""
    source_bank: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("source_bank")
    @classmethod
    def validate_revision_source_bank(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in value if isinstance(item, dict)][:120]

    @field_validator("revision_level")
    @classmethod
    def validate_revision_level(cls, value: str) -> str:
        allowed = {
            "Language and clarity polish",
            "Substantive scholarly revision",
            "Publication-readiness overhaul",
        }
        return value if value in allowed else "Publication-readiness overhaul"


class ArticleRevisionExportRequest(BaseModel):
    article_title: str = "Revised Journal Article"
    original_article_text: str = Field(..., min_length=10)
    revised_article_text: str = Field(..., min_length=10)
    revision_report: str = ""
    reviewer_response_matrix: str = ""
    include_revision_report: bool = True
