from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

from app.source_finder import search_literature_sources
from app.research_resources import discover_research_resources, infer_research_route, resources_for_idea

_RETRACTION_TERMS = re.compile(
    r"\b(retracted|retraction\s+notice|withdrawn|removed\s+article|expression\s+of\s+concern)\b",
    flags=re.IGNORECASE,
)


def _safe_get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=api_key)
    except Exception:
        return None


def _select_model(article_type: str) -> str:
    article_type_l = (article_type or "").lower()
    advanced = any(
        token in article_type_l
        for token in ["systematic", "scoping", "conceptual", "methodological", "meta-analysis", "meta analysis"]
    )
    if advanced:
        return os.getenv("OPENAI_ARTICLE_IDEA_ADVANCED_MODEL", "gpt-5.5").strip()
    return os.getenv("OPENAI_ARTICLE_IDEA_MODEL", "gpt-5.4").strip()


def _looks_retracted(source: dict[str, Any]) -> bool:
    combined = " ".join(
        str(source.get(key) or "")
        for key in ["title", "type", "status", "publication_status", "retraction_status", "abstract"]
    )
    return bool(_RETRACTION_TERMS.search(combined)) or bool(source.get("is_retracted"))


def _clean_list(value: Any, limit: int = 12) -> list[str]:
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"\n|;|,", str(value or ""))
    cleaned: list[str] = []
    for item in items:
        text = re.sub(r"\s+", " ", str(item or "")).strip(" -.;")
        if text and text.lower() not in {x.lower() for x in cleaned}:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _build_search_profile(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("thesis_title") or payload.get("research_area") or "").strip()
    return {
        "title": title,
        "research_area": str(payload.get("research_area") or "").strip(),
        "study_context": str(payload.get("context") or "").strip(),
        "objectives": _clean_list(payload.get("variables_or_themes"), 5),
        "level": "Journal article",
        "research_approach": str(payload.get("methodology") or "").strip(),
        "data_type": str(payload.get("article_type") or "").strip(),
        "notes": " ".join(
            filter(
                None,
                [
                    str(payload.get("target_journal") or "").strip(),
                    str(payload.get("journal_scope") or "").strip(),
                    str(payload.get("preferred_contribution") or "").strip(),
                ],
            )
        ),
    }


def _search_sources(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not payload.get("include_source_search", True):
        return [], {"provider_errors": [], "excluded_retracted_count": 0, "quality_filters": []}
    max_results = int(os.getenv("JOURNALREADY_IDEA_SOURCE_LIMIT", "16"))
    query = " ".join(
        filter(
            None,
            [
                str(payload.get("research_area") or "").strip(),
                str(payload.get("variables_or_themes") or "").strip(),
                str(payload.get("context") or "").strip(),
                str(payload.get("keywords") or "").strip(),
            ],
        )
    )[:220]
    try:
        result = search_literature_sources(
            _build_search_profile(payload),
            query=query,
            max_results=max_results,
            include_older_foundational=bool(payload.get("include_older_foundational", True)),
        )
    except Exception as exc:
        return [], {
            "provider_errors": [f"Source search failed: {str(exc)[:180]}"],
            "excluded_retracted_count": 0,
            "quality_filters": [],
        }
    sources = [src for src in (result.get("sources") or []) if not _looks_retracted(src)]
    return sources, result


def _source_context(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, src in enumerate(sources[:18], start=1):
        output.append(
            {
                "key": f"S{index}",
                "title": src.get("title", ""),
                "authors": src.get("authors", []),
                "year": src.get("year", ""),
                "source": src.get("source", ""),
                "doi": src.get("doi", ""),
                "url": src.get("url", ""),
                "abstract": str(src.get("abstract") or "")[:700],
                "database": src.get("database", ""),
            }
        )
    return output


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.M)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def _response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return str(text)
    output = getattr(response, "output", None) or []
    chunks: list[str] = []
    for item in output:
        content = getattr(item, "content", None) or []
        for part in content:
            value = getattr(part, "text", None)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks)


def _article_objective(title: str, focal: str, outcome: str, context: str) -> str:
    context_text = f" in {context}" if context else ""
    if focal and outcome:
        return f"To examine how {focal} relates to {outcome}{context_text}."
    return f"To investigate the central argument represented by '{title}'{context_text}."


def _suggested_sections(article_type: str) -> list[str]:
    value = (article_type or "").lower()
    if "systematic" in value or "scoping" in value:
        return ["Introduction", "Review methods", "Results", "Synthesis", "Discussion", "Conclusion"]
    if "conceptual" in value:
        return ["Introduction", "Conceptual background", "Proposed framework", "Discussion", "Implications", "Conclusion"]
    if "methodological" in value:
        return ["Introduction", "Methodological problem", "Proposed approach", "Validation", "Discussion", "Conclusion"]
    if "case study" in value:
        return ["Introduction", "Case context", "Methods", "Findings", "Discussion", "Conclusion"]
    if "policy" in value or "practice" in value:
        return ["Introduction", "Problem context", "Evidence", "Policy or practice implications", "Conclusion"]
    if "short communication" in value:
        return ["Introduction", "Methods", "Results", "Discussion", "Conclusion"]
    return ["Introduction", "Focused literature/theory", "Methods", "Results/Findings", "Discussion", "Conclusion"]


def _fallback_ideas(payload: dict[str, Any]) -> list[dict[str, Any]]:
    area = str(payload.get("research_area") or "the selected research area").strip()
    thesis_title = str(payload.get("thesis_title") or "").strip()
    context = str(payload.get("context") or "").strip()
    article_type = str(payload.get("article_type") or "Empirical research article").strip()
    target_journal = str(payload.get("target_journal") or "").strip()
    contribution = str(payload.get("preferred_contribution") or "context-specific empirical evidence").strip()
    variables = _clean_list(payload.get("variables_or_themes"), 8)
    focal = variables[0] if variables else area
    outcome = variables[1] if len(variables) > 1 else "the principal outcome"
    mechanism = variables[2] if len(variables) > 2 else "the underlying mechanism"
    boundary = variables[3] if len(variables) > 3 else "the relevant contextual condition"
    source_stem = thesis_title or area

    templates = [
        {
            "title": f"{focal.title()} and {outcome.title()}: Evidence from {context or 'the Study Context'}",
            "angle": "A focused direct-relationship article built around one central empirical claim from the larger study.",
            "gap": f"The thesis may treat {area} broadly, while this article isolates the relationship between {focal} and {outcome} and positions it against recent evidence.",
            "objective": _article_objective(source_stem, focal, outcome, context),
            "questions_or_hypotheses": [
                f"How is {focal} associated with {outcome}{' in ' + context if context else ''}?",
                f"H1: {focal} is significantly associated with {outcome}.",
            ],
            "contribution": contribution,
            "method_and_data_route": str(payload.get("methodology") or payload.get("data_available") or "Use the strongest relevant analysis already supported by the thesis dataset."),
        },
        {
            "title": f"Explaining {outcome.title()}: The Role of {mechanism.title()} in {context or area}",
            "angle": "A mechanism-centred paper that moves beyond a broad effect to explain how or why the effect occurs.",
            "gap": f"Existing work may document associations without adequately explaining the role of {mechanism}.",
            "objective": f"To assess whether and how {mechanism} explains variation in {outcome}{' in ' + context if context else ''}.",
            "questions_or_hypotheses": [
                f"What role does {mechanism} play in explaining {outcome}?",
                f"H1: {mechanism} transmits or explains the effect of {focal} on {outcome}.",
            ],
            "contribution": f"Clarifies the mechanism through which {focal} may influence {outcome}.",
            "method_and_data_route": "Use mediation, process analysis, qualitative mechanism tracing, or another design justified by the available data. Do not claim mediation unless the design supports it.",
        },
        {
            "title": f"When Does {focal.title()} Matter for {outcome.title()}? The Conditioning Role of {boundary.title()}",
            "angle": "A boundary-condition article focused on heterogeneity, moderation or contextual differences.",
            "gap": f"Prior findings may appear inconsistent because the conditioning role of {boundary} has received limited attention.",
            "objective": f"To determine whether the relationship between {focal} and {outcome} varies across levels or categories of {boundary}.",
            "questions_or_hypotheses": [
                f"Does {boundary} alter the relationship between {focal} and {outcome}?",
                f"H1: The effect of {focal} on {outcome} differs according to {boundary}.",
            ],
            "contribution": "Identifies a theoretically or practically meaningful boundary condition.",
            "method_and_data_route": "Use interaction analysis, subgroup comparison, multigroup analysis, comparative cases, or another defensible heterogeneity test.",
        },
        {
            "title": f"Rethinking {area.title()}: A Contextual Analysis of {context or 'an Understudied Setting'}",
            "angle": "A context-contribution paper that uses the study setting to qualify or extend established knowledge.",
            "gap": f"Evidence on {area} may be concentrated in settings that differ institutionally, economically or culturally from {context or 'the study setting'}.",
            "objective": f"To explain how the characteristics of {context or 'the study setting'} shape established expectations about {area}.",
            "questions_or_hypotheses": [
                f"Which contextual features shape {area} in the study setting?",
                "How do the findings confirm, qualify or challenge dominant explanations in the literature?",
            ],
            "contribution": "Adds contextual precision rather than presenting location alone as novelty.",
            "method_and_data_route": str(payload.get("methodology") or "Use the existing empirical or qualitative evidence, with explicit comparison to prior settings."),
        },
        {
            "title": f"From Evidence to Action: Practical Implications of {source_stem.title()}",
            "angle": "A policy or practice paper focused on an actionable problem and a clearly defined user of the findings.",
            "gap": "The original thesis may contain useful recommendations, but an article needs a tighter evidence-to-action argument and a named policy or managerial audience.",
            "objective": f"To translate the study evidence on {area} into a focused set of policy or practice implications.",
            "questions_or_hypotheses": [
                "Which findings have the strongest practical significance?",
                "What implementable actions follow from the evidence, and under what constraints?",
            ],
            "contribution": "Connects empirical findings to a specific decision problem without overstating causality.",
            "method_and_data_route": "Use the completed study results, stakeholder evidence, implementation constraints and relevant policy documents.",
        },
        {
            "title": f"A Focused Review of {area.title()}: Gaps, Tensions and a Future Research Agenda",
            "angle": "A review or conceptual article only where the user has enough literature coverage and a defensible review method.",
            "gap": f"The literature on {area} may be fragmented across constructs, contexts or methods.",
            "objective": f"To synthesise and critically organise evidence on {area}, identify unresolved tensions and propose a focused research agenda.",
            "questions_or_hypotheses": [
                f"How has {area} been conceptualised and studied?",
                "Which findings are consistent, contested or method-dependent?",
            ],
            "contribution": "Offers synthesis, conceptual clarification and a research agenda rather than a descriptive summary.",
            "method_and_data_route": "Use a transparent systematic, scoping, integrative or structured review protocol appropriate to the article type.",
        },
        {
            "title": f"Measuring {area.title()}: Evidence on the Quality and Structure of Key Constructs",
            "angle": "A measurement or methodological paper centred on scale quality, construct structure, model specification, or analytical improvement.",
            "gap": f"Studies of {area} may rely on measures or model choices whose validity, reliability, comparability or contextual suitability remains uncertain.",
            "objective": f"To evaluate the measurement or analytical approach used to study {area} and determine its suitability for the study context.",
            "questions_or_hypotheses": [
                "How well do the selected measures represent the intended constructs?",
                "Which model specifications or validation checks materially affect the conclusions?",
            ],
            "contribution": "Provides methodological evidence that improves how the phenomenon is measured or analysed.",
            "method_and_data_route": "Use measurement validation, robustness analysis, model comparison, scale adaptation evidence, or simulation only where the existing data support it.",
        },
        {
            "title": f"Who Benefits and Who Does Not? Heterogeneous Patterns in {area.title()}",
            "angle": "A distributional or subgroup article examining whether the main pattern differs across meaningful populations, institutions, sectors, or cases.",
            "gap": "Average effects can conceal important differences across groups or settings that matter for theory and practice.",
            "objective": f"To examine heterogeneity in the principal findings on {area} across theoretically or practically relevant groups.",
            "questions_or_hypotheses": [
                "Which groups or settings display materially different patterns?",
                "What factors plausibly explain the observed differences?",
            ],
            "contribution": "Shows where the central finding holds, weakens, strengthens, or reverses.",
            "method_and_data_route": "Use subgroup, quantile, multigroup, interaction, comparative case, or stratified analysis already supported by the sample and design.",
        },
        {
            "title": f"Change over Time in {area.title()}: Patterns, Turning Points and Implications",
            "angle": "A temporal paper focused on dynamics, shocks, phases, policy changes, or evolving relationships rather than a static average.",
            "gap": f"The literature may treat {area} as stable even though the relationship or process can change over time.",
            "objective": f"To analyse how the pattern or relationship underlying {area} changes across time, periods, or relevant events.",
            "questions_or_hypotheses": [
                "How does the central pattern evolve over the observed period?",
                "Are there identifiable turning points, structural changes, or phase-specific effects?",
            ],
            "contribution": "Adds temporal precision and identifies when conclusions differ from the full-period average.",
            "method_and_data_route": "Use time-varying, longitudinal, event, trend, change-point, panel, or period-comparison methods only if the data have a defensible time dimension.",
        },
        {
            "title": f"When Expected Effects Do Not Appear: Reassessing {focal.title()} and {outcome.title()}",
            "angle": "A theory-refining paper built around null, weak, mixed, or unexpected findings that can be explained rigorously.",
            "gap": "Publication narratives often understate null or contradictory findings, even when they reveal boundary conditions, measurement limits, or contextual differences.",
            "objective": f"To explain why the expected relationship between {focal} and {outcome} is weak, absent, mixed, or contrary to prior expectations.",
            "questions_or_hypotheses": [
                "Which theoretical, contextual, measurement, or design factors may explain the unexpected result?",
                "What does the finding imply for the scope of the original theory or proposition?",
            ],
            "contribution": "Refines theory or practice by treating an unexpected result as evidence to be explained, not concealed.",
            "method_and_data_route": "Use robustness checks, alternative specifications, qualitative explanation, sensitivity analysis, or triangulation. Do not overinterpret statistical non-significance.",
        },
    ]

    max_ideas = max(3, min(int(payload.get("max_ideas") or 6), 10))
    output: list[dict[str, Any]] = []
    for index, item in enumerate(templates[:max_ideas], start=1):
        item.update(
            {
                "idea_number": index,
                "article_type": article_type,
                "journal_fit": f"Assess against {target_journal or 'the selected journal'} aims, scope, recent publications and word limit.",
                "suggested_sections": _suggested_sections(article_type),
                "keywords": _clean_list([focal, outcome, mechanism, context, area], 6),
                "evidence_needed": [
                    "A clearly bounded result or argument from the thesis",
                    "Recent verified literature that establishes the article-level gap",
                    "Complete method and results details needed to support the central claim",
                    "A journal-specific fit check before submission",
                ],
                "scope_warning": "Do not compress the entire thesis into one article. Build the paper around one central contribution and only the evidence needed to support it.",
                "readiness_score": max(58, 88 - (index - 1) * 4),
                "research_route": infer_research_route(payload, str(item.get("method_and_data_route") or "")),
            }
        )
        output.append(item)
    return output


def _normalise_ideas(parsed: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_ideas = parsed.get("ideas") if isinstance(parsed, dict) else None
    if not isinstance(raw_ideas, list):
        return []
    max_ideas = max(3, min(int(payload.get("max_ideas") or 6), 10))
    ideas: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_ideas[:max_ideas], start=1):
        if not isinstance(raw, dict):
            continue
        title = re.sub(r"\s+", " ", str(raw.get("title") or "")).strip()
        if not title:
            continue
        ideas.append(
            {
                "idea_number": index,
                "title": title,
                "article_type": str(raw.get("article_type") or payload.get("article_type") or "Empirical research article"),
                "angle": str(raw.get("angle") or "").strip(),
                "gap": str(raw.get("gap") or "").strip(),
                "objective": str(raw.get("objective") or "").strip(),
                "questions_or_hypotheses": _clean_list(raw.get("questions_or_hypotheses"), 5),
                "contribution": str(raw.get("contribution") or "").strip(),
                "method_and_data_route": str(raw.get("method_and_data_route") or "").strip(),
                "journal_fit": str(raw.get("journal_fit") or "").strip(),
                "suggested_sections": _clean_list(raw.get("suggested_sections"), 10),
                "keywords": _clean_list(raw.get("keywords"), 8),
                "evidence_needed": _clean_list(raw.get("evidence_needed"), 8),
                "scope_warning": str(raw.get("scope_warning") or "Build the article around one central contribution.").strip(),
                "readiness_score": max(0, min(int(raw.get("readiness_score") or 70), 100)),
                "research_route": str(raw.get("research_route") or infer_research_route(payload, str(raw.get("method_and_data_route") or ""))),
            }
        )
    return ideas


def generate_article_ideas(payload: dict[str, Any]) -> dict[str, Any]:
    if not str(payload.get("research_area") or "").strip():
        raise ValueError("Research area is required.")

    sources, source_result = _search_sources(payload)
    source_records = _source_context(sources)
    model = _select_model(str(payload.get("article_type") or ""))
    client = _safe_get_openai_client()
    provider_errors: list[Any] = list(source_result.get("provider_errors") or [])
    ideas: list[dict[str, Any]] = []
    mode = "structured_fallback"

    if client and os.getenv("JOURNALREADY_IDEA_USE_AI", "1").strip().lower() not in {"0", "false", "no"}:
        current_year = datetime.now().year
        prompt = {
            "task": "Generate journal-article topic ideas, especially publishable papers that can be extracted from a thesis or dissertation.",
            "current_year": current_year,
            "inputs": payload,
            "source_records": source_records,
            "article_design_rules": [
                "Treat a journal article as a focused paper, not a shortened thesis.",
                "Each idea must make one central claim or contribution and use only the thesis evidence needed for that claim.",
                "Narrow broad thesis titles by selecting one relationship, mechanism, boundary condition, methodological contribution, contextual qualification, policy problem or review question.",
                "Use one clear overall article objective. Add no more than three tightly aligned questions or hypotheses unless the article type requires otherwise.",
                "Do not create novelty merely by adding a country name. Explain the theoretical, empirical, methodological, policy or contextual contribution.",
                "Match each idea to the data and analysis that the user actually has. Flag ideas requiring unavailable data.",
                "For review articles, require a transparent and defensible review method. Do not relabel a thesis literature review as a systematic review without a protocol.",
                "Do not fabricate findings, citations, journal requirements, sample details or statistical results.",
                "Use only non-retracted source metadata supplied in source_records when discussing current literature signals.",
                "Titles should be concise, searchable and article-like. Avoid thesis wording such as 'an assessment of' unless genuinely suitable.",
                "Include a readiness score based on fit with the supplied thesis material, data, contribution and target journal.",
                "Identify whether each idea is most suited to secondary data, a survey or scale, qualitative instruments, mixed methods, experimental instruments, or review/conceptual work.",
                "For secondary-data ideas, the app will attach candidate official data sources. For primary or qualitative ideas, it will attach candidate questionnaire, scale, interview-guide or instrument sources that must be verified before adoption or adaptation.",
            ],
            "required_json_shape": {
                "ideas": [
                    {
                        "title": "string",
                        "article_type": "string",
                        "angle": "string",
                        "gap": "string",
                        "objective": "single prose objective",
                        "questions_or_hypotheses": ["maximum three items"],
                        "contribution": "string",
                        "method_and_data_route": "string",
                        "journal_fit": "string",
                        "suggested_sections": ["section names"],
                        "keywords": ["4-7 keywords"],
                        "evidence_needed": ["specific evidence or results needed"],
                        "scope_warning": "string",
                        "readiness_score": 0,
                        "research_route": "secondary_data | survey_or_scale | qualitative_instrument | mixed_methods | experimental_instrument | review_or_conceptual | undetermined",
                    }
                ],
                "portfolio_note": "Briefly explain which ideas can coexist as separate articles without salami slicing or duplication.",
            },
            "output_rule": "Return valid JSON only, with no markdown fences.",
        }
        try:
            response = client.responses.create(
                model=model,
                instructions=(
                    "You are JournalReady AI's article development editor. Convert broad studies and theses into ethical, focused, publication-oriented article ideas. "
                    "Protect against salami slicing, duplicated claims, invented novelty and unsupported methods. Return valid JSON only."
                ),
                input=json.dumps(prompt, ensure_ascii=False, indent=2),
            )
            parsed = _extract_json(_response_text(response))
            ideas = _normalise_ideas(parsed or {}, payload)
            if ideas:
                mode = "ai_generated"
                portfolio_note = str((parsed or {}).get("portfolio_note") or "").strip()
            else:
                portfolio_note = ""
        except Exception as exc:
            provider_errors.append(f"OpenAI article idea generation failed: {str(exc)[:180]}")
            portfolio_note = ""
    else:
        portfolio_note = ""

    if not ideas:
        ideas = _fallback_ideas(payload)
        portfolio_note = (
            "Use the ideas as a publication portfolio only when each paper has a distinct question, analysis and contribution. "
            "Avoid splitting one result into several minimally different papers, and disclose overlap with the thesis where required."
        )

    resource_result: dict[str, Any] = {
        "research_route": "undetermined",
        "research_route_label": "Research route not yet determined",
        "data_sources": [],
        "instrument_sources": [],
        "provider_errors": [],
        "search_note": "Research-resource search was not requested.",
    }
    if payload.get("include_research_resource_search", True):
        ideas_text = " ".join(
            f"{idea.get('title', '')} {idea.get('objective', '')} {idea.get('method_and_data_route', '')}"
            for idea in ideas
        )
        resource_result = discover_research_resources(
            payload,
            extra_text=ideas_text,
            max_results=int(payload.get("resource_result_limit") or 6),
            include_live_search=bool(payload.get("include_source_search", True)),
        )
        provider_errors.extend(resource_result.get("provider_errors") or [])

    for idea in ideas:
        idea["resource_guidance"] = resources_for_idea(idea, resource_result, limit=5)

    return {
        "ideas": ideas,
        "portfolio_note": portfolio_note,
        "model_used": model if client else "none",
        "mode": mode,
        "source_records_used": source_records,
        "research_resources": resource_result,
        "provider_errors": provider_errors,
        "excluded_retracted_count": int(source_result.get("excluded_retracted_count") or 0),
        "quality_filters": source_result.get("quality_filters") or [
            "Retracted and withdrawn records excluded where detectable.",
            "Ideas narrowed to one central article contribution.",
            "Methods and evidence requirements stated explicitly.",
        ],
    }
