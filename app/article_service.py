from __future__ import annotations

import hashlib
import io
import json
import os
import random
import re
from datetime import datetime
from typing import Any

try:
    from app.source_finder import search_literature_sources
except Exception:  # pragma: no cover
    search_literature_sources = None

from app.research_resources import discover_research_resources, infer_research_route

# Dynamic source context defaults are controlled through helpers below.  Keep this
# reasonably high because journal articles need deeper citation coverage than a
# thesis chapter subsection.
MAX_SOURCE_CONTEXT = int(os.getenv("ARTICLEREADY_ARTICLE_MAX_SOURCE_CONTEXT", "80"))

_RETRACTION_TERMS = re.compile(
    r"\b(retracted|retraction\s+notice|withdrawn|removed\s+article|expression\s+of\s+concern|erratum\s+to\s+retracted)\b",
    flags=re.IGNORECASE,
)

_ATTENTION_RE = re.compile(
    r"\[(?:insert|verify|confirm|provide|supply|complete|replace|check|add|update|obtain|state|specify|include|revise|review|conduct|perform|run|collect|clarify|report|resolve|address|identify|upload|attach|calculate|test|assess|determine|seek|action|required|author\s+action)\b[^\]]*\]",
    flags=re.IGNORECASE,
)

_ACTION_LABEL_RE = re.compile(
    r"\b(?:action required|author action|required action|remaining action|attention required|user action)\s*:\s*",
    flags=re.IGNORECASE,
)

_ACTION_RED = (192, 0, 0)

_ADAM_2020_REFERENCE = (
    "Adam, A. M. (2020). Sample size determination in survey research. "
    "Journal of Scientific Research and Reports, 26(5), 90-97. "
    "https://journaljsrr.com/index.php/JSRR/article/view/1154"
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


def _select_article_model(level: str, article_type: str = "") -> str:
    """Route journal article drafting by academic depth and publication complexity."""
    level_l = (level or "").strip().lower()
    type_l = (article_type or "").strip().lower()
    is_doctoral = any(token in level_l for token in ["phd", "doctor", "dba", "ded", "professional doctorate"])
    is_research_masters = "research masters" in level_l or "mphil" in level_l
    is_review_article = any(token in type_l for token in ["systematic", "scoping", "meta-analysis", "meta analysis", "review article", "literature review", "conceptual"])
    if is_doctoral:
        return os.getenv("OPENAI_ARTICLE_DOCTORAL_MODEL", os.getenv("OPENAI_DOCTORAL_DRAFT_MODEL", "gpt-5.5")).strip()
    if is_research_masters or is_review_article:
        return os.getenv("OPENAI_ARTICLE_RESEARCH_MODEL", os.getenv("OPENAI_RESEARCH_MASTERS_DRAFT_MODEL", "gpt-5.5")).strip()
    if "non-research" in level_l or "master" in level_l:
        return os.getenv("OPENAI_ARTICLE_MASTERS_MODEL", "gpt-5.4").strip()
    return os.getenv("OPENAI_ARTICLE_BACHELOR_MODEL", os.getenv("OPENAI_BACHELOR_DRAFT_MODEL", "gpt-5.4")).strip()


def _article_kind(article_type: str) -> str:
    t = (article_type or "").lower()
    if any(x in t for x in ["systematic", "meta-analysis", "meta analysis"]):
        return "systematic_review_or_meta_analysis"
    if any(x in t for x in ["review", "literature review", "scoping"]):
        return "review_article_or_literature_review"
    if any(x in t for x in ["short", "brief", "communication"]):
        return "short_communication_or_brief_report"
    if "conference" in t:
        return "conference_paper"
    return "standard_research_article"


def _article_reference_expectations(article_type: str) -> dict[str, Any]:
    """Return article-type citation-depth guidance without encouraging reference padding."""
    kind = _article_kind(article_type)
    matrix: dict[str, dict[str, Any]] = {
        "standard_research_article": {
            "target_range": "40-60 references",
            "default_search_limit": 60,
            "guidance": "Original research should support the background, theory, methods, results interpretation and discussion with substantial but selective coverage.",
        },
        "review_article_or_literature_review": {
            "target_range": "60-150+ references",
            "default_search_limit": 140,
            "guidance": "Review articles require broad coverage of the relevant literature, including competing streams, methodological differences and unresolved debates.",
        },
        "systematic_review_or_meta_analysis": {
            "target_range": "80-300+ references",
            "default_search_limit": 180,
            "guidance": "Systematic reviews and meta-analyses require exhaustive, transparent coverage consistent with the review protocol and eligibility criteria.",
        },
        "short_communication_or_brief_report": {
            "target_range": "10-25 references",
            "default_search_limit": 30,
            "guidance": "Short communications should use a narrow, high-value reference base because of strict word limits.",
        },
        "conference_paper": {
            "target_range": "15-40 references",
            "default_search_limit": 45,
            "guidance": "Conference papers need enough current literature to justify novelty without overcrowding a short manuscript.",
        },
    }
    out = dict(matrix[kind])
    out["article_kind"] = kind
    out["anti_padding_rule"] = (
        "Do not pad the reference list. Cite only sources that directly support a claim, method, theory, measure, comparison or interpretation. "
        "If available verified sources are fewer than the expected range, add an attention placeholder asking for additional verified literature rather than inventing sources."
    )
    return out


def _article_source_limit(payload: dict[str, Any]) -> int:
    env_limit = os.getenv("ARTICLEREADY_ARTICLE_SOURCE_LIMIT", "").strip()
    if env_limit.isdigit():
        return max(1, int(env_limit))
    return int(_article_reference_expectations(str(payload.get("article_type") or "")).get("default_search_limit", 60))


def _looks_retracted(src: dict[str, Any]) -> bool:
    fields = [
        src.get("title"), src.get("type"), src.get("subtype"), src.get("status"), src.get("publication_status"),
        src.get("update_type"), src.get("relation_type"), src.get("abstract"), src.get("note"), src.get("warning"),
    ]
    combined = " ".join(str(x or "") for x in fields)
    if _RETRACTION_TERMS.search(combined):
        return True
    flags = ["is_retracted", "retracted", "has_retraction", "is_withdrawn", "withdrawn", "removed", "expression_of_concern"]
    return any(bool(src.get(flag)) for flag in flags)


def _build_search_profile(payload: dict[str, Any]) -> dict[str, Any]:
    objectives = []
    for raw in str(payload.get("objectives") or "").split("\n"):
        item = raw.strip(" -;,")
        if item:
            objectives.append(item)
    return {
        "title": str(payload.get("article_title") or payload.get("source_thesis_title") or "").strip(),
        "research_area": str(payload.get("research_area") or payload.get("article_title") or payload.get("source_thesis_title") or "").strip(),
        "study_context": str(payload.get("context") or "").strip(),
        "level": str(payload.get("academic_level") or "Research Masters (e.g. MPhil)").strip(),
        "research_approach": str(payload.get("methodology") or "").strip(),
        "data_type": str(payload.get("article_type") or "").strip(),
        "objectives": objectives[:8],
        "notes": " ".join([
            str(payload.get("target_journal") or ""),
            str(payload.get("variables_constructs") or ""),
            str(payload.get("key_findings") or ""),
            str(payload.get("theory_or_framework") or ""),
            str(payload.get("source_thesis_title") or ""),
            str(payload.get("extraction_focus") or ""),
        ]).strip(),
    }


def _source_key(src: dict[str, Any]) -> str:
    doi = str(src.get("doi") or "").strip().lower()
    if doi:
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
        return "doi:" + doi
    title = re.sub(r"[^a-z0-9]+", "", str(src.get("title") or "").lower())[:120]
    return "title:" + title


def _merge_source_banks(*banks: list[dict[str, Any]], limit: int = 120) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for bank in banks:
        for src in bank or []:
            if not isinstance(src, dict):
                continue
            key = _source_key(src)
            if not key or key == "title:" or key in seen:
                continue
            seen.add(key)
            merged.append(dict(src))
            if len(merged) >= limit:
                return merged
    return merged


def _payload_attached_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    direct = payload.get("source_bank") or []
    retrieved = payload.get("retrieved_sources") or {}
    retrieved_items = retrieved.get("sources") or [] if isinstance(retrieved, dict) else []
    attached = _merge_source_banks(direct, retrieved_items, limit=120)
    output: list[dict[str, Any]] = []
    for src in attached:
        record = dict(src)
        record.setdefault("attachment_origin", "attached_before_drafting")
        output.append(record)
    return output


def find_article_sources(payload: dict[str, Any]) -> dict[str, Any]:
    """Search scholarly metadata for the article and return records that can be attached before drafting."""
    if search_literature_sources is None:
        raise RuntimeError("The scholarly source search service is unavailable.")
    profile = _build_search_profile(payload)
    query = str(payload.get("query") or payload.get("source_search_terms") or "").strip()
    result = search_literature_sources(
        profile=profile,
        query=query,
        max_results=int(payload.get("max_results") or 12),
        include_older_foundational=bool(payload.get("include_older_foundational", True)),
    )
    raw_sources = [s for s in (result.get("sources") or []) if isinstance(s, dict)]
    blocked = [s for s in raw_sources if _looks_retracted(s)]
    usable: list[dict[str, Any]] = []
    for src in raw_sources:
        if _looks_retracted(src):
            continue
        record = dict(src)
        record.setdefault("attachment_origin", "manual_source_search")
        usable.append(record)
    return {
        **result,
        "sources": usable,
        "source_bank": usable,
        "source_bank_count": len(usable),
        "excluded_retracted_count": int(result.get("excluded_retracted_count") or 0) + len(blocked),
        "excluded_retracted_titles": list(dict.fromkeys([
            *(result.get("excluded_retracted_titles") or []),
            *(str(src.get("title") or "Untitled") for src in blocked),
        ]))[:20],
        "attachment_note": "These records are attached to the article evidence bank in the browser and will be sent with the drafting request.",
    }


def _search_sources(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    attached_raw = _payload_attached_sources(payload)
    attached_blocked = [src for src in attached_raw if _looks_retracted(src)]
    attached_usable = [src for src in attached_raw if not _looks_retracted(src)]

    search_result: dict[str, Any] = {
        "provider_errors": [],
        "query": str(payload.get("source_search_terms") or ""),
        "sources": [],
        "quality_filters": [],
    }
    searched_usable: list[dict[str, Any]] = []
    searched_blocked: list[dict[str, Any]] = []

    if payload.get("include_source_search", True) and search_literature_sources is not None:
        search_payload = dict(payload)
        search_payload["query"] = str(payload.get("source_search_terms") or "").strip()
        search_payload["max_results"] = _article_source_limit(payload)
        try:
            search_result = find_article_sources(search_payload)
            for src in search_result.get("sources") or []:
                record = dict(src)
                record["attachment_origin"] = "automatic_draft_search"
                searched_usable.append(record)
            searched_blocked = [
                {"title": title, "attachment_origin": "automatic_draft_search"}
                for title in search_result.get("excluded_retracted_titles") or []
            ]
        except Exception as exc:
            search_result = {
                "provider_errors": [{"provider": "source_search", "error": str(exc)[:220]}],
                "query": str(payload.get("source_search_terms") or ""),
                "sources": [],
                "quality_filters": [],
            }

    merged = _merge_source_banks(attached_usable, searched_usable, limit=120)
    blocked = _merge_source_banks(attached_blocked, searched_blocked, limit=40)
    search_result["attached_source_count"] = len(attached_usable)
    search_result["automatic_source_count"] = len(searched_usable)
    search_result["source_bank_count"] = len(merged)
    search_result["sources"] = merged
    search_result["attachment_priority"] = "Sources explicitly attached before drafting are ordered before sources found automatically during drafting."
    return merged, blocked, search_result


def _source_context(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    max_context = max(1, int(os.getenv("ARTICLEREADY_ARTICLE_MAX_SOURCE_CONTEXT", str(MAX_SOURCE_CONTEXT))))
    for idx, src in enumerate(sources[:max_context], start=1):
        authors = src.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]
        records.append({
            "key": f"S{idx}",
            "title": src.get("title", ""),
            "authors": authors,
            "year": src.get("year", ""),
            "source": src.get("source", ""),
            "doi": src.get("doi", ""),
            "url": src.get("url", ""),
            "abstract": str(src.get("abstract") or "")[: int(os.getenv("ARTICLEREADY_ARTICLE_ABSTRACT_CHARS", "700"))],
            "database": src.get("database", ""),
            "relevance_tier": src.get("relevance_tier", ""),
            "citation_count": src.get("citation_count", ""),
            "reference_entry_hint": src.get("apa_hint") or src.get("reference_entry_hint") or "",
            "attachment_origin": src.get("attachment_origin", ""),
        })
    return records


def _extract_text(response: Any) -> str:
    return str(getattr(response, "output_text", "") or "").strip()


def _strip_code_fences(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()


def _is_survey_research(payload: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(payload.get(k) or "")
        for k in ["article_type", "methodology", "context", "data", "data_results", "data_and_results", "variables_constructs", "objectives", "research_area", "thesis_source_material"]
    ).lower()
    return any(token in haystack for token in ["survey", "questionnaire", "likert", "respondent", "pls-sem", "pls sem", "sem", "cross-sectional"])


def _has_sample_size_determination(payload: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(payload.get(k) or "")
        for k in ["methodology", "data", "data_results", "data_and_results", "context", "objectives", "key_findings", "thesis_source_material"]
    ).lower()
    return any(token in haystack for token in ["sample size", "yamane", "krejcie", "morgan", "cochran", "adam (2020)", "power analysis", "g*power", "gpower"])


def _survey_method_requirements(payload: dict[str, Any]) -> dict[str, Any]:
    survey = _is_survey_research(payload)
    if not survey:
        return {"is_survey_research": False, "rules": []}
    rules = [
        "For survey research, include how common method variance/common method bias was addressed in the Methods section, using prose rather than a bare checklist.",
        "Discuss procedural remedies where appropriate: anonymity, voluntary participation, careful item wording, separation of predictor and outcome sections, varied scale anchors where defensible, reduced evaluation apprehension, and clear instructions.",
        "Discuss statistical remedies where appropriate: Harman's single-factor test, marker-variable approach, unmeasured latent method factor, full collinearity VIF, or another method justified by the selected analysis technique.",
        "If PLS-SEM or SEM is used, distinguish measurement-model quality from common-method-bias assessment.",
        "Do not report CMV/CMB statistics unless the user supplied them. Insert [insert CMV/CMB test result] where needed.",
    ]
    if not _has_sample_size_determination(payload):
        rules.append(
            "If the user did not state a sample-size determination method, justify the required sample size using Adam (2020) for survey research and include the Adam (2020) reference. Do not fabricate the final sample size; use [confirm population size and required sample size] where the population size or confidence level is missing."
        )
    return {
        "is_survey_research": True,
        "sample_size_source_if_missing": _ADAM_2020_REFERENCE if not _has_sample_size_determination(payload) else "User supplied another sample-size determination approach.",
        "rules": rules,
    }


def _human_article_style_requirements(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "style_goal": "publishable, strongly human-supervised academic prose",
        "rules": [
            "Write in formal British English with natural academic rhythm, not template-like AI prose.",
            "Use controlled high burstiness and strong lexical variation: combine concise emphasis with developed analytical sentences, without creating fragments or artificial mistakes.",
            "Vary sentence and paragraph length according to argument needs, but keep grammar, citations, headings, tables, equations and references clean.",
            "Build paragraphs around claim, evidence, interpretation, qualification and contribution. Avoid paragraphs that merely list authors.",
            "Vary paragraph openings and transitions so consecutive paragraphs do not begin with the same formula.",
            "Use precise verbs such as indicates, qualifies, complicates, supports, constrains, extends and contradicts.",
            "Avoid filler phrases such as 'in today's world', 'it is important to note', 'delve into', 'plays a crucial role', and repeated 'moreover' or 'furthermore'.",
            "Use cautious scholarly judgement rather than promotional language. Do not overclaim practical or theoretical contributions.",
            "Maintain the author's voice through reasoned transitions, context-specific qualifiers and close links between the study objectives, methods, results and contribution.",
            "Preserve all confirmed facts, statistics, citations, technical terms, placeholders and section logic during stylistic revision.",
            "Do not introduce typos, random grammar errors, lower-case sentence starts, broken citations, invented evidence or artificial mistakes.",
        ],
    }


def _prose_objective_requirements(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "objective_style": "prose-first",
        "rules": [
            "Write the article objective, purpose and contribution in prose. Avoid a bare bullet list of objectives unless the target journal explicitly requires it.",
            "In the Introduction, write objectives as a paragraph such as: 'Accordingly, this article examines..., assesses..., and explains...' rather than listing Objective 1, Objective 2 and Objective 3.",
            "Write all major article sections in prose first. Tables may support the argument, but they must not replace the narrative.",
            "If research questions or hypotheses are needed, introduce them through a short prose bridge before listing or tabulating them.",
        ],
    }


def _equation_and_framework_requirements(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "equation_rules": [
            "When equations or statistical models are required, place each equation in a display equation block using $$ equation $$. Use clean Word-friendly mathematical notation with Unicode Greek letters and subscripts where possible.",
            "Define every symbol directly below the equation in prose. Do not leave equations unexplained.",
            "Use article-appropriate model notation, for example Yᵢ = β₀ + β₁X₁ᵢ + β₂X₂ᵢ + εᵢ, but adapt variable names to the user's actual study.",
            "Do not invent coefficients, p-values or model results. Use [insert model estimates] where results are missing.",
        ],
        "conceptual_framework_rules": [
            "If a conceptual framework is required, structure it as: framework narrative, variable architecture table, hypothesised path table, figure caption, and optional Mermaid or Graphviz code block.",
            "Classify variables as IV, DV, MED, MOD and CV where applicable. Do not force mediation or moderation if not supplied or theoretically justified.",
            "For moderation, show the moderator pointing to the relationship being moderated, not as a vague ordinary predictor of the dependent variable.",
            "Avoid messy ASCII diagrams. Use a concise Mermaid flowchart or Graphviz DOT/Python Graphviz code block where a diagram is useful.",
            "Do not hard-code sample variables. Use only variables, constructs and relationships supplied by the user or clearly inferable from the current article input.",
        ],
        "graphviz_guide": {
            "node_types": ["IV", "DV", "MED", "MOD", "CV"],
            "preferred_orientation": "LR for simple causal frameworks, TB for layered or process frameworks",
            "style_note": "Use publication-style boxes, clear arrows and short labels. If the diagram cannot be rendered in the app, output a Graphviz-compatible code block for the user to render externally.",
        },
    }


def _strong_humanisation_requirements(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "strong_human_supervised",
        "enabled_by_default": True,
        "rules": [
            "Apply controlled high burstiness and high lexical variation while preserving clarity, evidence and disciplinary precision.",
            "Allow sentence length to vary naturally. Split overloaded sentences at defensible clause boundaries, but do not create fragments.",
            "Vary paragraph shape and openings according to the argument rather than through random transition words.",
            "Retain the user's confirmed facts, citations, statistics, quotations, placeholders, equations, tables and reference details exactly unless a substantive revision is justified by supplied evidence.",
            "Remove generic filler and repetitive academic templates. Replace them with context-specific reasoning and precise verbs.",
            "Do not randomise paragraph order, inject unrelated tangents, fabricate citations, or add deliberate grammatical errors.",
            "Do not mention humanisation, AI detection or detector scores in the manuscript.",
        ],
    }


def _article_prompt_quality_pack(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "human_article_style_requirements": _human_article_style_requirements(payload),
        "strong_humanisation_requirements": _strong_humanisation_requirements(payload),
        "prose_objective_requirements": _prose_objective_requirements(payload),
        "survey_method_requirements": _survey_method_requirements(payload),
        "equation_and_framework_requirements": _equation_and_framework_requirements(payload),
        "reference_depth_requirements": _article_reference_expectations(str(payload.get("article_type") or "")),
    }


def _light_human_article_polish(text: str) -> str:
    """Safe text polish adapted from ai_service.py, without artificial errors."""
    if not text:
        return text
    replacements = {
        r"\bin today's world\b": "in the present context",
        r"\bit is important to note that\b": "",
        r"\bdelve into\b": "examine",
        r"\bplays a crucial role\b": "is important",
        r"\bvarious factors\b": "specific factors",
        r"\bsignificant impact\b": "meaningful effect",
        r"\bthis highlights the importance of\b": "this indicates why",
        r"\bmoreover,\s+moreover\b": "moreover",
        r"\bfurthermore,\s+furthermore\b": "furthermore",
    }
    out = text
    for pattern, repl in replacements.items():
        def case_replacement(match: re.Match[str], replacement: str = repl) -> str:
            if not replacement:
                return replacement
            return replacement[:1].upper() + replacement[1:] if match.group(0)[:1].isupper() else replacement
        out = re.sub(pattern, case_replacement, out, flags=re.IGNORECASE)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


_HUMANISATION_OFF_VALUES = {"0", "false", "no", "off"}
_SENTENCE_ABBREVIATIONS = (
    "e.g.", "i.e.", "et al.", "Dr.", "Prof.", "Mr.", "Mrs.", "Ms.",
    "Fig.", "Eq.", "No.", "Vol.", "pp.", "p.", "vs.", "etc.",
)


def _strong_humanisation_enabled() -> bool:
    return os.getenv("ARTICLEREADY_STRONG_HUMANISATION", "1").strip().lower() not in _HUMANISATION_OFF_VALUES


def _humanisation_strength() -> str:
    value = os.getenv("ARTICLEREADY_HUMANISATION_STRENGTH", "strong").strip().lower()
    return value if value in {"light", "standard", "strong"} else "strong"


def _humanisation_rng(text: str, seed_text: str = "") -> random.Random:
    salt = os.getenv("ARTICLEREADY_HUMANISATION_SEED_SALT", "articleready-v1")
    digest = hashlib.sha256(f"{salt}|{seed_text}|{text[:4000]}".encode("utf-8", errors="ignore")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _split_sentences_safe(text: str) -> list[str]:
    if not text.strip():
        return []
    protected = text
    token = "<AR_DOT>"
    for abbr in _SENTENCE_ABBREVIATIONS:
        protected = re.sub(
            re.escape(abbr),
            lambda match: match.group(0).replace(".", token),
            protected,
            flags=re.IGNORECASE,
        )
    protected = re.sub(r"(?<=\d)\.(?=\d)", token, protected)
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9\[\(“"])', protected)
    return [part.replace(token, ".").strip() for part in parts if part.strip()]


def _sentence_word_count(sentence: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", sentence))


def _capitalise_sentence_start(text: str) -> str:
    match = re.search(r"[A-Za-z]", text)
    if not match:
        return text
    idx = match.start()
    return text[:idx] + text[idx].upper() + text[idx + 1:]


def _best_sentence_split(sentence: str) -> tuple[str, str] | None:
    if _sentence_word_count(sentence) < 26:
        return None
    candidates: list[tuple[int, int]] = []
    for match in re.finditer(r";\s+|:\s+|,\s+(?=(?:but|yet|however)\b)", sentence, flags=re.IGNORECASE):
        left = sentence[:match.start()].strip()
        right = sentence[match.end():].strip()
        if _sentence_word_count(left) >= 9 and _sentence_word_count(right) >= 8:
            candidates.append((match.start(), match.end()))
    if not candidates:
        return None
    midpoint = len(sentence) / 2
    start, end = min(candidates, key=lambda pair: abs(pair[0] - midpoint))
    left = sentence[:start].rstrip(" ,;:") + "."
    right = sentence[end:].strip()
    separator = sentence[start:end].strip().lower()
    if right.lower().startswith("but "):
        right = "Even so, " + right[4:]
    elif right.lower().startswith("yet "):
        right = "Even so, " + right[4:]
    elif separator.startswith(","):
        conjunction = re.sub(r"^[,;:]\s*", "", separator).strip()
        if conjunction and not right.lower().startswith(conjunction + " "):
            right = conjunction.capitalize() + " " + right
    right = _capitalise_sentence_start(right)
    return left, right


def _increase_natural_variation(text: str, rng: random.Random | None = None) -> str:
    """Improve rhythm and remove repetitive stock phrases without adding new claims."""
    if not text:
        return text
    rng = rng or _humanisation_rng(text)
    replacements = {
        r"\bin order to\b": "to",
        r"\bdue to the fact that\b": "because",
        r"\bthe fact that\b": "that",
        r"\bas a result of\b": "because of",
        r"\bit is important to note that\b": "",
        r"\bit should be noted that\b": "",
        r"\bthe present study seeks to\b": "this article",
    }
    out = text
    for pattern, replacement in replacements.items():
        def case_replacement(match: re.Match[str], value: str = replacement) -> str:
            if not value:
                return value
            return value[:1].upper() + value[1:] if match.group(0)[:1].isupper() else value
        out = re.sub(pattern, case_replacement, out, flags=re.IGNORECASE)
    sentences = _split_sentences_safe(out)
    if len(sentences) >= 2:
        lengths = [_sentence_word_count(sentence) for sentence in sentences]
        for index in sorted(range(len(sentences)), key=lambda i: lengths[i], reverse=True):
            if lengths[index] < 34:
                break
            split = _best_sentence_split(sentences[index])
            if split:
                sentences[index:index + 1] = list(split)
                break
        repeated_openers = {
            "this study": ["The present article", "The analysis", "This investigation"],
            "the findings": ["These results", "The evidence", "The reported findings"],
            "the results": ["These results", "The evidence", "The estimates"],
        }
        previous = ""
        counts: dict[str, int] = {}
        for index, sentence in enumerate(sentences):
            match = re.match(r"([A-Za-z]+(?:\s+[A-Za-z]+)?)", sentence)
            opener = match.group(1).lower() if match else ""
            if opener == previous and opener in repeated_openers:
                count = counts.get(opener, 0)
                replacement = repeated_openers[opener][count % len(repeated_openers[opener])]
                counts[opener] = count + 1
                sentences[index] = re.sub(rf"^{re.escape(match.group(1))}", replacement, sentence, count=1, flags=re.IGNORECASE)
                opener = replacement.lower()
            previous = opener
        out = " ".join(sentences)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def _enforce_burstiness(
    text: str,
    target_std_dev: float = 10.0,
    max_uniform: int = 3,
    rng: random.Random | None = None,
) -> str:
    """Increase sentence-length variation by splitting overloaded sentences at safe boundaries."""
    if not text or len(text) < 180:
        return text
    rng = rng or _humanisation_rng(text)
    sentences = _split_sentences_safe(text)
    if len(sentences) < 2:
        return text

    def spread(items: list[str]) -> float:
        lengths = [_sentence_word_count(item) for item in items]
        mean = sum(lengths) / max(1, len(lengths))
        return (sum((value - mean) ** 2 for value in lengths) / max(1, len(lengths))) ** 0.5

    attempts = 0
    while spread(sentences) < target_std_dev and attempts < 3:
        attempts += 1
        lengths = [_sentence_word_count(sentence) for sentence in sentences]
        candidates = [i for i, length in enumerate(lengths) if length >= 28]
        if not candidates:
            break
        index = max(candidates, key=lambda i: lengths[i])
        split = _best_sentence_split(sentences[index])
        if not split:
            break
        sentences[index:index + 1] = list(split)

    # Break long runs of similarly sized sentences only when a safe split is available.
    run = 1
    lengths = [_sentence_word_count(sentence) for sentence in sentences]
    for index in range(1, len(sentences)):
        if abs(lengths[index] - lengths[index - 1]) <= 3:
            run += 1
        else:
            run = 1
        if run > max_uniform and lengths[index] >= 28:
            split = _best_sentence_split(sentences[index])
            if split:
                sentences[index:index + 1] = list(split)
                break
    return " ".join(sentences).strip()


def _add_drafting_artefacts(
    text: str,
    probability_per_500_words: float = 0.35,
    rng: random.Random | None = None,
) -> str:
    """Add restrained scholarly texture by removing formulaic transitions, without adding errors or claims."""
    if not text or len(text.split()) < 120:
        return text
    rng = rng or _humanisation_rng(text)
    if rng.random() > probability_per_500_words:
        return text
    substitutions = [
        (r"^Furthermore,\s+", ""),
        (r"^Moreover,\s+", ""),
        (r"^It is also important to note that\s+", ""),
        (r"^In addition,\s+", "More specifically, "),
    ]
    out = text
    for pattern, replacement in substitutions:
        if re.search(pattern, out, flags=re.IGNORECASE):
            out = re.sub(pattern, replacement, out, count=1, flags=re.IGNORECASE)
            return _capitalise_sentence_start(out)
    return out


def _boost_lexical_richness(
    text: str,
    replacement_probability: float = 0.35,
    rng: random.Random | None = None,
) -> str:
    """Reduce repetitive academic phrasing using meaning-preserving substitutions."""
    if not text or len(text.split()) < 40:
        return text
    rng = rng or _humanisation_rng(text)
    replacements = [
        (r"\bshows that\b", "indicates that"),
        (r"\bsuggests that\b", "points to"),
        (r"\bdemonstrates that\b", "provides evidence that"),
        (r"\bimportant role\b", "substantive role"),
        (r"\bmany studies\b", "a substantial body of research"),
        (r"\bfor example\b", "for instance"),
        (r"\bin contrast\b", "by contrast"),
        (r"\bhas been shown to\b", "has been found to"),
    ]
    out = text
    applied = False
    def replace_once(source: str, pattern: str, replacement: str) -> str:
        def case_replacement(match: re.Match[str]) -> str:
            return replacement[:1].upper() + replacement[1:] if match.group(0)[:1].isupper() else replacement
        return re.sub(pattern, case_replacement, source, count=1, flags=re.IGNORECASE)

    for pattern, replacement in replacements:
        if rng.random() <= replacement_probability and re.search(pattern, out, flags=re.IGNORECASE):
            out = replace_once(out, pattern, replacement)
            applied = True
    if not applied and replacement_probability >= 0.30:
        for pattern, replacement in replacements:
            if re.search(pattern, out, flags=re.IGNORECASE):
                out = replace_once(out, pattern, replacement)
                break
    return out


def _cluster_citations(text: str) -> str:
    """Compatibility hook: citations are preserved and never fabricated or moved mechanically."""
    return text or ""


def _vary_paragraph_openings(text: str) -> str:
    """Reduce repeated paragraph openings with conservative, article-appropriate alternatives."""
    paragraphs = re.split(r"(\n\s*\n)", text or "")
    previous_opener = ""
    alternatives = {
        "this study": ["The present article", "The analysis", "This investigation"],
        "the findings": ["These results", "The evidence", "The reported findings"],
        "the results": ["These results", "The evidence", "The estimates"],
    }
    counters: dict[str, int] = {}
    for index in range(0, len(paragraphs), 2):
        paragraph = paragraphs[index]
        stripped = paragraph.lstrip()
        if not stripped or stripped.startswith(("#", "|", "- ", "* ")):
            continue
        match = re.match(r"([A-Za-z]+(?:\s+[A-Za-z]+)?)", stripped)
        opener = match.group(1).lower() if match else ""
        if opener == previous_opener and opener in alternatives:
            count = counters.get(opener, 0)
            replacement = alternatives[opener][count % len(alternatives[opener])]
            counters[opener] = count + 1
            leading = paragraph[: len(paragraph) - len(stripped)]
            stripped = re.sub(rf"^{re.escape(match.group(1))}", replacement, stripped, count=1, flags=re.IGNORECASE)
            paragraphs[index] = leading + stripped
            opener = replacement.lower()
        previous_opener = opener
    return "".join(paragraphs)


def _force_short_sentences(text: str, target_every_n_words: int = 220) -> str:
    """Create occasional concise sentences by safely splitting existing long sentences."""
    words = re.findall(r"\b[\w’'-]+\b", text or "")
    if len(words) < target_every_n_words:
        return text
    sentences = _split_sentences_safe(text)
    if any(_sentence_word_count(sentence) <= 9 for sentence in sentences):
        return text
    candidates = sorted(
        ((index, _sentence_word_count(sentence)) for index, sentence in enumerate(sentences)),
        key=lambda item: item[1],
        reverse=True,
    )
    for index, length in candidates:
        if length < 30:
            break
        split = _best_sentence_split(sentences[index])
        if split:
            sentences[index:index + 1] = list(split)
            return " ".join(sentences)
    return text


def _add_human_noise(text: str, error_probability: float = 0.0) -> str:
    """Compatibility hook. ArticleReady never introduces deliberate mistakes or citation damage."""
    return text or ""


def _protect_humanisation_regions(text: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        key = f"<AR_PROTECTED_{len(protected)}>"
        protected[key] = match.group(0)
        return key

    out = re.sub(r"```.*?```", replace, text, flags=re.DOTALL)
    out = re.sub(r"(?ms)^\$\$\s*$.*?^\$\$\s*$", replace, out)
    return out, protected


def _restore_humanisation_regions(text: str, protected: dict[str, str]) -> str:
    out = text
    for key, value in protected.items():
        out = out.replace(key, value)
    return out


def _is_humanisable_block(block: str) -> bool:
    stripped = block.strip()
    if not stripped or stripped.startswith("<AR_PROTECTED_"):
        return False
    if stripped.startswith(("#", "|", "- ", "* ")):
        return False
    if re.match(r"^\d+[.)]\s+", stripped):
        return False
    if any(line.lstrip().startswith("|") for line in stripped.splitlines()):
        return False
    if re.match(r"^(Funding|Conflict of interest|Ethics approval|Data availability):", stripped, flags=re.IGNORECASE):
        return False
    return len(re.findall(r"\b[\w’'-]+\b", stripped)) >= 18


def _apply_strong_article_humanisation(
    text: str,
    *,
    seed_text: str = "",
    preserve_reference_section: bool = True,
) -> str:
    """Apply the strong, evidence-safe humanisation layer adapted from ai_service.py.

    The pass is deterministic for the same text and seed. It changes prose rhythm and
    repetitive wording, but protects headings, tables, code blocks, equations, citations,
    placeholders, references and article structure.
    """
    if not text or not _strong_humanisation_enabled():
        return text
    strength = _humanisation_strength()
    if strength == "light":
        target_std, lexical_probability, texture_probability = 7.0, 0.18, 0.15
    elif strength == "standard":
        target_std, lexical_probability, texture_probability = 8.5, 0.25, 0.25
    else:
        target_std, lexical_probability, texture_probability = 10.0, 0.35, 0.35

    reference_tail = ""
    body = text
    if preserve_reference_section:
        match = re.search(r"(?im)^#{1,4}\s+(references|source use audit)\s*$", text)
        if match:
            body = text[:match.start()].rstrip()
            reference_tail = "\n\n" + text[match.start():].lstrip()

    protected_body, protected = _protect_humanisation_regions(body)
    blocks = re.split(r"(\n\s*\n)", protected_body)
    rng = _humanisation_rng(text, seed_text)
    for index in range(0, len(blocks), 2):
        block = blocks[index]
        if not _is_humanisable_block(block):
            continue
        polished = _light_human_article_polish(block)
        polished = _increase_natural_variation(polished, rng)
        polished = _enforce_burstiness(polished, target_std_dev=target_std, rng=rng)
        polished = _add_drafting_artefacts(polished, probability_per_500_words=texture_probability, rng=rng)
        polished = _boost_lexical_richness(polished, replacement_probability=lexical_probability, rng=rng)
        polished = _cluster_citations(polished)
        polished = _force_short_sentences(polished, target_every_n_words=220)
        polished = _add_human_noise(polished)
        blocks[index] = polished

    output = "".join(blocks)
    output = _vary_paragraph_openings(output)
    output = _restore_humanisation_regions(output, protected)
    output = re.sub(r"[ \t]{2,}", " ", output)
    output = re.sub(r"\n{3,}", "\n\n", output).strip()
    return output + reference_tail


def _is_independent_article(payload: dict[str, Any]) -> bool:
    return "new independent article" in str(payload.get("source_mode") or "").strip().lower()


def _prepare_workflow_payload(payload: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(payload)
    independent = _is_independent_article(prepared)
    stage = str(prepared.get("draft_stage") or "full_article").strip()
    if stage not in {"full_article", "initial_to_methods", "continuation_after_results"}:
        stage = "full_article"
    if independent and stage == "full_article":
        stage = "initial_to_methods"
    prepared["draft_stage"] = stage
    if independent:
        # Independent articles should not depend on thesis/dissertation/project material.
        prepared["source_thesis_title"] = ""
        prepared["thesis_source_material"] = ""
        current_level = str(prepared.get("academic_level") or "").strip()
        if not current_level or current_level == "Research Masters (e.g. MPhil)":
            prepared["academic_level"] = "PhD"
    return prepared


def _resource_markdown(resources: dict[str, Any]) -> str:
    if not resources:
        return ""
    lines = ["## Research Resource Guidance", "", resources.get("search_note") or "Verify every proposed research resource before use."]
    data_sources = resources.get("data_sources") or []
    instruments = resources.get("instrument_sources") or []
    if data_sources:
        lines.extend(["", "### Possible Secondary Data Sources", ""])
        for item in data_sources[:8]:
            line = f"- **{item.get('name', 'Unnamed source')}**, {item.get('provider', '')}. {item.get('coverage', '')} {item.get('suitability', '')}"
            if item.get("url"):
                line += f" Access: {item['url']}"
            if item.get("access_note"):
                line += f" Check: {item['access_note']}"
            lines.append(line.strip())
    if instruments:
        lines.extend(["", "### Possible Questionnaire or Instrument Sources", ""])
        for item in instruments[:8]:
            line = f"- **{item.get('name', 'Unnamed instrument source')}**, {item.get('provider', '')}. {item.get('purpose', '')} {item.get('suitability', '')}"
            if item.get("url"):
                line += f" Access: {item['url']}"
            if item.get("permission_note"):
                line += f" Use condition: {item['permission_note']}"
            lines.append(line.strip())
    return "\n".join(lines).strip()


def _fallback_instrument(payload: dict[str, Any], resources: dict[str, Any]) -> str:
    if not payload.get("include_instrument_draft"):
        return ""
    route = infer_research_route(payload)
    requirements = str(payload.get("instrument_requirements") or "").strip()
    if route == "qualitative_instrument":
        return f"""# Provisional Interview Guide

## Use and Adaptation Note

This guide is provisional and must be aligned with the article objective, ethics approval and study context. {requirements or '[specify the participant group, interview setting and expected duration]'}

## Opening Script

[insert consent, confidentiality, voluntary participation and recording statement]

## Section A: Participant Context

1. Please describe your role or experience in relation to the study topic.
2. What aspects of the context are most important for understanding this issue?

## Section B: Core Article Constructs or Themes

1. How do you understand or experience [insert focal construct or phenomenon]?
2. What factors shape this experience or outcome?
3. Can you describe a specific example?
4. Under what conditions does the pattern become stronger, weaker or different?

## Section C: Implications

1. What changes would improve the situation?
2. What constraints could prevent those changes?

## Probes

Use neutral probes such as “Could you explain further?”, “What happened next?”, “Why was that important?” and “Were there exceptions?”

## Validation Actions

[conduct expert review, cognitive testing or pilot interviews, revise ambiguous questions, and document the final guide]
""".strip()
    return f"""# Provisional Questionnaire and Measurement Plan

## Use and Adaptation Note

This is an original provisional instrument framework, not a reproduction of a proprietary scale. Confirm whether a validated instrument listed in the research-resource guidance is suitable before creating new items. {requirements or '[specify the target population, constructs and preferred response scale]'}

## Section A: Screening and Consent

1. [insert eligibility question]
2. [insert informed-consent statement]

## Section B: Respondent Profile

Include only demographic or organisational variables needed for the analysis and justified by the article.

## Section C: Focal Construct Measures

For each construct, create a clearly labelled item block with a consistent response scale. Draft at least three content-valid items per reflective construct unless the original validated scale specifies otherwise.

| Construct | Proposed item focus | Response format | Original or adapted source | Action required |
|---|---|---|---|---|
| [Construct 1] | [define the content domain] | [e.g. 1 strongly disagree to 5 strongly agree] | [insert verified source] | [expert review and pilot test] |
| [Construct 2] | [define the content domain] | [insert scale] | [insert verified source] | [translation/adaptation check] |
| [Outcome] | [define the outcome domain] | [insert scale] | [insert verified source] | [validity and reliability assessment] |

## Section D: Open Comment

Please provide any additional information that would help explain your responses.

## Instrument Development and Validation Plan

1. Map every item to an article objective, hypothesis or construct.
2. Verify permission and licensing for adopted scales.
3. Use expert review for content validity and cognitive interviewing for comprehension.
4. Pilot the instrument with respondents similar to the target population.
5. Assess reliability and the measurement model using methods appropriate to the study design.
6. Document all adaptations, translations, removed items and scoring changes.
""".strip()


def _fallback_article(payload: dict[str, Any], sources: list[dict[str, Any]], resources: dict[str, Any] | None = None) -> str:
    title = str(payload.get("article_title") or "Article Draft").strip()
    article_type = str(payload.get("article_type") or "Empirical research article").strip()
    citation_style = str(payload.get("citation_style") or "APA 7th").strip()
    stage = str(payload.get("draft_stage") or "full_article")
    ref_expectation = _article_reference_expectations(article_type)
    survey_rules = _survey_method_requirements(payload)
    source_note = ""
    source_audit = ""
    if sources:
        source_note = "\n\nAn attached evidence bank is available for this article, including: " + "; ".join(
            f"S{i+1}: {s.get('title', 'Untitled')} ({s.get('year', 'n.d.')})" for i, s in enumerate(sources[:8])
        ) + ". Each record must pass a relevance check before citation."
        source_audit = "\n\n## Source Use Audit\n\n" + "\n".join(
            f"- S{i+1}: {s.get('title', 'Untitled')} ({s.get('year', 'n.d.')}), attached but not yet integrated because the fallback draft contains placeholders. Verify relevance and cite it only where it directly supports a claim."
            for i, s in enumerate(sources[:12])
        )
    survey_note = ""
    if survey_rules.get("is_survey_research"):
        survey_note = (
            "\n\nFor survey research, this Methods section should explain sample-size determination, questionnaire development, "
            "validity, reliability and common method variance/common method bias remedies. If no sample-size method has been supplied, use Adam (2020) as the sample-size determination source and verify the final population size and required sample size."
        )
    resource_text = _resource_markdown(resources or {})

    if stage == "initial_to_methods":
        return f"""# {title}

## Protocol Status

This is a PhD-depth independent article development draft. The manuscript body intentionally stops at the Methods section. Results, Discussion and Conclusion must be completed only after the analysis is uploaded.

## Abstract

[insert a protocol-style abstract covering the problem, objective, proposed method and intended contribution. Do not report results that do not yet exist]

## Keywords

[insert 4-6 keywords]

## 1. Introduction

This section should establish the focused research problem, article-level gap, context and intended contribution. Write the objective in prose. {source_note}

## 2. Literature Review and Theoretical Positioning

[insert a critical synthesis using verified current and foundational literature]

## 3. Conceptual or Analytical Framework

[insert framework narrative, variable architecture, hypotheses or propositions, and a clean framework figure where appropriate]

## 4. Methods

[insert the proposed design, setting, population or units of analysis, data source or instrument, sample strategy, measures, analysis plan, validity or trustworthiness procedures, ethics, data management and reproducibility steps]{survey_note}

## Methods Readiness Checklist

- [confirm data access or participant access]
- [confirm variable availability or instrument permission]
- [confirm sampling frame and sample-size approach]
- [confirm analysis software and model specification]
- [confirm ethics approval or exemption before data collection]

{resource_text}

## Next Stage

When analysis is ready, select **Stage 2: Complete article after results**, upload this draft together with the results or analysis output, and generate the Results, Discussion, Conclusion, updated Abstract, Declarations and final References.

## References

[insert {citation_style} references cited in Sections 1-4 only]{source_audit}
""".strip()

    if stage == "continuation_after_results":
        return f"""# {title}

## Continuation Draft Status

The supplied previous sections and analysis should be integrated into one coherent article. Preserve accurate material from the earlier draft and revise it only where the new results require alignment.

## Abstract

[update the abstract with the confirmed sample, method, key results and contribution]

## 1. Introduction to Methods

[insert or preserve the supplied earlier article sections]

## 5. Results

[write the results from the uploaded analysis only. Insert tables and figures where supported. Do not invent statistics or themes]

## 6. Discussion

[interpret each confirmed finding against theory, prior studies and the study context]

## 7. Conclusion

[write the conclusion, contribution, implications, limitations and future research]

## Declarations

Funding: [confirm funding statement]

Conflict of interest: [confirm conflict-of-interest statement]

Ethics approval: [confirm ethics approval or exemption]

Data availability: [confirm data availability statement]

## References

[merge and verify all {citation_style} references cited in the completed article]{source_audit}
""".strip()

    return f"""# {title}

## Article Type and Target

This manuscript is being prepared as a {article_type}. The target journal is {payload.get('target_journal') or '[insert target journal]'}. The expected reference depth for this article type is {ref_expectation['target_range']}, but the final reference list must include only sources cited in the manuscript.

## Abstract

[insert 180-250 word structured or unstructured abstract after confirming the final results, sample, method and contribution]

## Keywords

[insert 4-6 keywords]

## 1. Introduction

This section should establish the research problem, the current scholarly conversation, the study context and the article's contribution. The article objective should be written in prose rather than as a bare list. {source_note}

## 2. Literature Review and Theoretical Positioning

[insert focused literature synthesis using verified current sources and foundational theory where appropriate]

## 3. Conceptual or Analytical Framework

[insert framework narrative, variable architecture table, hypothesised path table, and Mermaid or Graphviz code block where applicable]

## 4. Methods

[insert article-ready methods section, including design, setting, population/sample, data source, measures, analysis technique, validity/reliability or trustworthiness, and ethics]{survey_note}

## 5. Results

[insert analysed results, tables and figures. Do not invent statistics, coefficients, themes or p-values]

## 6. Discussion

[insert interpretation of findings against theory, prior studies and the study context]

## 7. Conclusion

[insert concise conclusion, contribution, limitations and future research]

## Declarations

Funding: [confirm funding statement]

Conflict of interest: [confirm conflict-of-interest statement]

Ethics approval: [confirm ethics approval or exemption]

Data availability: [confirm data availability statement]

## References

[insert {citation_style} references for sources cited in the article only]{source_audit}
""".strip()

def _finalise_article_text(text: str) -> str:
    text = _strip_code_fences(text or "")
    text = re.sub(r"<span\s+[^>]*>(.*?)</span>", r"\1", text, flags=re.I | re.S)
    text = text.replace("—", ", ").replace(" – ", ", ").replace("–", "-").replace("‑", "-")
    text = _light_human_article_polish(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _split_draft_package(text: str) -> tuple[str, str]:
    raw = str(text or "").strip()
    article_marker = "===ARTICLE_DRAFT==="
    instrument_marker = "===INSTRUMENT_DRAFT==="
    if article_marker in raw:
        raw = raw.split(article_marker, 1)[1]
    if instrument_marker in raw:
        article, instrument = raw.split(instrument_marker, 1)
        return article.strip(), instrument.strip()
    return raw, ""


def _enforce_initial_scope(text: str) -> str:
    # Stop an accidental continuation if the model writes later empirical sections.
    pattern = re.compile(r"(?im)^#{1,3}\s*(?:\d+\.?\s*)?(results|findings|discussion|conclusion|implications)\b")
    match = pattern.search(text or "")
    if not match:
        return text
    kept = (text or "")[:match.start()].rstrip()
    return kept + "\n\n## Next Stage\n\nResults, Discussion and Conclusion were intentionally withheld. Upload the completed analysis with the previous sections and use Stage 2 to finish the article."


def draft_journal_article(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _prepare_workflow_payload(dict(payload))
    payload["thesis_source_material"] = str(payload.get("thesis_source_material") or "")[:50000]
    payload["previous_sections"] = str(payload.get("previous_sections") or "")[:70000]
    payload["continuation_material"] = str(payload.get("continuation_material") or "")[:70000]
    payload["author_guidelines"] = str(payload.get("author_guidelines") or "")[:18000]
    payload["data_and_results"] = str(payload.get("data_and_results") or "")[:50000]
    if not str(payload.get("article_title") or "").strip():
        raise ValueError("Article title or working topic is required.")
    if payload["draft_stage"] == "continuation_after_results" and not (
        str(payload.get("previous_sections") or "").strip() or str(payload.get("continuation_material") or "").strip() or str(payload.get("data_and_results") or "").strip()
    ):
        raise ValueError("Upload or paste the previous article sections and the completed results or analysis before using Stage 2.")

    sources, blocked, search_result = _search_sources(payload)
    source_records = _source_context(sources)
    resources = payload.get("research_resources") or {}
    if payload.get("include_research_resource_search", True) and not (resources.get("data_sources") or resources.get("instrument_sources")):
        resources = discover_research_resources(
            payload,
            extra_text=" ".join([str(payload.get("research_problem") or ""), str(payload.get("objectives") or "")]),
            max_results=8,
            include_live_search=bool(payload.get("include_source_search", True)),
        )
    payload["research_route"] = infer_research_route(payload)
    model = _select_article_model(str(payload.get("academic_level") or ""), str(payload.get("article_type") or ""))
    client = _safe_get_openai_client()
    provider_errors = list(search_result.get("provider_errors") or []) if isinstance(search_result, dict) else []
    provider_errors.extend(resources.get("provider_errors") or [])
    instrument_text = ""

    if not client or os.getenv("ARTICLEREADY_ARTICLE_USE_AI", "1").strip().lower() in {"0", "false", "no"}:
        article_text = _fallback_article(payload, sources, resources)
        instrument_text = _fallback_instrument(payload, resources)
        mode = "metadata_fallback"
    else:
        current_year = datetime.now().year
        quality_pack = _article_prompt_quality_pack(payload)
        article_inputs = {key: value for key, value in payload.items() if key not in {"source_bank", "retrieved_sources", "research_resources"}}
        article_inputs["attached_source_count"] = int(search_result.get("attached_source_count") or 0)
        article_inputs["automatic_source_count"] = int(search_result.get("automatic_source_count") or 0)
        stage = payload["draft_stage"]
        stage_rules = {
            "initial_to_methods": [
                "This is Stage 1 for a new independent article. Draft the manuscript body only from the Title through the Methods section.",
                "Use PhD-level depth by default. Develop a strong article-level gap, theory or framework, questions or hypotheses, and a defensible proposed method.",
                "Do not write Results, Findings, Discussion, Conclusion, completed declarations or result-based claims.",
                "The abstract must be protocol-style and must not imply that data have been analysed.",
                "After Methods, add a Methods Readiness Checklist and a short Next Stage note. References and Source Use Audit may follow.",
            ],
            "continuation_after_results": [
                "This is Stage 2. Use previous_sections as the earlier manuscript and continuation_material/data_and_results as the completed analysis evidence.",
                "Integrate the earlier sections and new results into one coherent full article. Preserve accurate prior prose but revise objectives, methods and framing when the analysis requires alignment.",
                "Write Results, Discussion, Conclusion, updated Abstract, implications, limitations, declarations and the final References from supplied evidence only.",
                "Do not invent missing coefficients, p-values, sample details, themes, quotations, tables or figures.",
            ],
            "full_article": [
                "Draft the full article because the user supplied a completed thesis, project, dataset analysis or study evidence.",
            ],
        }[stage]
        prompt = {
            "task": "Draft the requested stage of a publishable journal article and, where requested, a separate provisional instrument package.",
            "draft_stage": stage,
            "article_inputs": article_inputs,
            "current_year": current_year,
            "source_records": source_records,
            "research_resource_guidance": resources,
            "quality_pack": quality_pack,
            "stage_rules": stage_rules,
            "strict_rules": [
                "Use supplied target-journal guidance as structural rules. If absent, use an article structure appropriate to the article type and current stage.",
                "Treat an independent article as a new study, not as a disguised thesis extraction. Thesis, dissertation and project fields are intentionally blank in independent mode.",
                "Do not guarantee publication and do not fabricate evidence, results, citations, permissions, ethics approvals, data access or declarations.",
                "Use bracketed attention placeholders for missing details.",
                "Apply a relevance gate to all attached scholarly sources and research resources.",
                "Candidate data sources and instruments are possibilities only. Explain variable coverage, population fit, period, access, ethics, licensing and validation checks before recommending adoption.",
                "Do not reproduce proprietary questionnaire items. When a scale may be copyrighted, identify the source and state that permission or licensing must be checked.",
                "If include_instrument_draft is true, draft a separate original provisional questionnaire, interview guide or measurement plan aligned with the objectives. Do not present it as validated until it has been tested.",
                "Write in polished formal British English, minimise long dashes, use prose-led objectives and maintain a focused article contribution.",
                "Apply the strong_humanisation_requirements in the quality pack: use controlled high burstiness, varied paragraph shape, precise lexical variation and natural transitions while preserving all evidence, citations, tables, equations and placeholders.",
                "Do not randomise paragraph order, inject tangents, introduce deliberate mistakes, or mention AI detection or humanisation in the article.",
                "Use only confirmed results in Stage 2 or full-article mode. Metadata abstracts do not justify detailed claims about a paper's findings.",
                "References must contain only cited and verified sources. Include a Source Use Audit when source records are supplied.",
            ],
            "output_format": [
                "Return plain Markdown separated by exact markers.",
                "Start with ===ARTICLE_DRAFT=== and then the article draft.",
                "If include_instrument_draft is true, add ===INSTRUMENT_DRAFT=== followed by the separate instrument package. Otherwise omit the instrument marker.",
                "Do not wrap the response in code fences.",
            ],
        }
        try:
            response = client.responses.create(
                model=model,
                instructions=(
                    "You are ArticleReady AI's staged journal article development assistant. Respect the selected stage. "
                    "Apply the supplied strong human-supervised academic writing layer: use natural sentence-length variation, varied paragraph openings, "
                    "precise disciplinary language and evidence-led reasoning while preserving citations, technical terms, tables, equations and placeholders. "
                    "Do not add deliberate errors, unrelated tangents, or commentary about AI detection or humanisation. "
                    "For a new independent study, stop the article body at Methods and provide data-source or instrument guidance without inventing access or validated items. "
                    "For Stage 2, use the uploaded previous sections and results to complete the manuscript."
                ),
                input=json.dumps(prompt, ensure_ascii=False, indent=2),
            )
            raw_text = _extract_text(response)
            article_text, instrument_text = _split_draft_package(raw_text)
            if not article_text:
                article_text = _fallback_article(payload, sources, resources)
            if payload.get("include_instrument_draft") and not instrument_text:
                instrument_text = _fallback_instrument(payload, resources)
            mode = "ai_draft"
        except Exception as exc:
            provider_errors.append(f"OpenAI article drafting failed: {str(exc)[:180]}")
            article_text = _fallback_article(payload, sources, resources)
            instrument_text = _fallback_instrument(payload, resources)
            mode = "metadata_fallback_after_ai_error"

    article_text = _finalise_article_text(article_text)
    instrument_text = _finalise_article_text(instrument_text) if instrument_text else ""
    if payload["draft_stage"] == "initial_to_methods":
        article_text = _enforce_initial_scope(article_text)
    if mode == "ai_draft":
        article_text = _apply_strong_article_humanisation(
            article_text,
            seed_text="|".join([
                str(payload.get("article_title") or ""),
                str(payload.get("article_type") or ""),
                str(payload.get("draft_stage") or ""),
            ]),
        )
        article_text = _finalise_article_text(article_text)

    return {
        "article_text": article_text,
        "instrument_text": instrument_text,
        "draft_stage": payload["draft_stage"],
        "academic_level_used": payload.get("academic_level") or "PhD",
        "research_route": payload.get("research_route") or "undetermined",
        "research_resources": resources,
        "model_used": model if client else "none",
        "mode": mode,
        "source_records_used": source_records,
        "attached_source_count": int(search_result.get("attached_source_count") or 0),
        "automatic_source_count": int(search_result.get("automatic_source_count") or 0),
        "source_bank_count": len(source_records),
        "source_search_terms": str(search_result.get("query") or payload.get("source_search_terms") or ""),
        "excluded_retracted_count": len(blocked),
        "excluded_retracted_titles": [str(s.get("title") or "Untitled") for s in blocked[:10]],
        "provider_errors": provider_errors,
        "reference_depth_guidance": _article_reference_expectations(str(payload.get("article_type") or "")),
        "strong_humanisation_applied": mode == "ai_draft" and _strong_humanisation_enabled(),
        "humanisation_strength": _humanisation_strength(),
        "quality_filters": [
            "The strong human-supervised writing layer varies sentence rhythm, paragraph shape and wording without changing confirmed evidence or article structure.",
            "Independent-article mode disables thesis, dissertation and project source fields.",
            "Stage 1 stops the article body at Methods. Stage 2 requires previous sections and completed results or analysis.",
            "Candidate secondary datasets and instruments must be checked for fit, access, permission and validity.",
            "Retracted, withdrawn, removed and expression-of-concern records are excluded where detectable.",
            "Attached scholarly records are filtered through a relevance gate and cannot replace the user's study evidence.",
            "Missing article details are rendered as bracketed attention placeholders.",
        ],
    }

def _normalise_inline_markdown(text: str) -> str:
    """Normalise common Markdown emphasis typos before DOCX rendering."""
    value = str(text or "")
    # Common model-output typo: one extra closing marker, for example **text***.
    value = re.sub(r"(?<!\*)\*\*(?!\*)([^*\n]+)\*{3}(?=$|[\s.,;:!?])", r"**\1**", value)
    value = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+)\*{2}(?=$|[\s.,;:!?])", r"*\1*", value)
    value = re.sub(r"(?<!_)__(?!_)([^_\n]+)_{3}(?=$|[\s.,;:!?])", r"__\1__", value)
    value = re.sub(r"(?<!_)_(?!_)([^_\n]+)_{2}(?=$|[\s.,;:!?])", r"_\1_", value)
    return value


def _strip_stray_inline_markers(text: str) -> str:
    """Remove unmatched emphasis markers at word boundaries without touching multiplication signs."""
    value = str(text or "")
    value = re.sub(r"(?<!\w)\*{1,3}(?=\w)", "", value)
    value = re.sub(r"(?<=\w)\*{1,3}(?=$|[\s.,;:!?])", "", value)
    value = re.sub(r"(?<!\w)_{1,3}(?=\w)", "", value)
    value = re.sub(r"(?<=\w)_{1,3}(?=$|[\s.,;:!?])", "", value)
    return value


def _split_action_segments(text: str, bold: bool = False, italic: bool = False) -> list[tuple[str, bool, bool, bool]]:
    """Split visible text into normal and author-action segments."""
    value = str(text or "")
    if not value:
        return []
    segments: list[tuple[str, bool, bool, bool]] = []
    position = 0
    bracket_re = re.compile(r"\[[^\]\n]+\]")
    for match in bracket_re.finditer(value):
        if match.start() > position:
            prefix = value[position:match.start()]
            label = _ACTION_LABEL_RE.search(prefix)
            if label:
                if label.start() > 0:
                    segments.append((prefix[:label.start()], bold, italic, False))
                segments.append((prefix[label.start():], bold, italic, True))
            else:
                segments.append((prefix, bold, italic, False))
        token = match.group(0)
        segments.append((token, bold, italic, bool(_ATTENTION_RE.fullmatch(token))))
        position = match.end()
    if position < len(value):
        tail = value[position:]
        label = _ACTION_LABEL_RE.search(tail)
        if label:
            if label.start() > 0:
                segments.append((tail[:label.start()], bold, italic, False))
            segments.append((tail[label.start():], bold, italic, True))
        else:
            segments.append((tail, bold, italic, False))
    if not segments:
        label = _ACTION_LABEL_RE.search(value)
        if label:
            if label.start() > 0:
                segments.append((value[:label.start()], bold, italic, False))
            segments.append((value[label.start():], bold, italic, True))
        else:
            segments.append((value, bold, italic, False))
    return [(part, b, i, action) for part, b, i, action in segments if part]


def _parse_inline_segments(text: str) -> list[tuple[str, bool, bool, bool]]:
    """Parse Markdown emphasis and action placeholders into DOCX-ready segments.

    The returned tuples are: visible text, bold, italic and action-required.
    """
    value = _normalise_inline_markdown(text)
    style_re = re.compile(
        r"(?P<bolditalic>\*\*\*(?P<bolditalic_text>.+?)\*\*\*)"
        r"|(?P<bold>\*\*(?P<bold_text>.+?)\*\*)"
        r"|(?P<italic>(?<!\*)\*(?!\*)(?P<italic_text>.+?)(?<!\*)\*(?!\*))"
        r"|(?P<bolditalic_u>___(?P<bolditalic_u_text>.+?)___)"
        r"|(?P<bold_u>__(?P<bold_u_text>.+?)__)"
        r"|(?P<italic_u>(?<!\w)_(?!_)(?P<italic_u_text>.+?)(?<!_)_(?!\w))",
        flags=re.DOTALL,
    )
    segments: list[tuple[str, bool, bool, bool]] = []
    position = 0
    for match in style_re.finditer(value):
        if match.start() > position:
            plain = _strip_stray_inline_markers(value[position:match.start()])
            segments.extend(_split_action_segments(plain))
        if match.group("bolditalic") is not None:
            inner, bold, italic = match.group("bolditalic_text"), True, True
        elif match.group("bold") is not None:
            inner, bold, italic = match.group("bold_text"), True, False
        elif match.group("italic") is not None:
            inner, bold, italic = match.group("italic_text"), False, True
        elif match.group("bolditalic_u") is not None:
            inner, bold, italic = match.group("bolditalic_u_text"), True, True
        elif match.group("bold_u") is not None:
            inner, bold, italic = match.group("bold_u_text"), True, False
        else:
            inner, bold, italic = match.group("italic_u_text"), False, True
        segments.extend(_split_action_segments(inner or "", bold=bold, italic=italic))
        position = match.end()
    if position < len(value):
        segments.extend(_split_action_segments(_strip_stray_inline_markers(value[position:])))
    if not segments and value:
        segments.extend(_split_action_segments(_strip_stray_inline_markers(value)))
    return segments


def _plain_inline_text(text: str) -> str:
    return "".join(segment[0] for segment in _parse_inline_segments(text))


def _add_inline_runs(paragraph, text: str, force_bold: bool = False) -> None:
    """Render Markdown emphasis and colour author-action text red."""
    from docx.shared import RGBColor

    for visible, bold, italic, action_required in _parse_inline_segments(text):
        run = paragraph.add_run(visible)
        run.bold = bool(bold or force_bold)
        run.italic = bool(italic)
        if action_required:
            run.font.color.rgb = RGBColor(*_ACTION_RED)

def _add_markdown_table(doc, lines: list[str]) -> None:
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and not all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cells):
            rows.append(cells)
    if not rows:
        return
    width = max(len(r) for r in rows)
    table = doc.add_table(rows=0, cols=width)
    table.style = "Table Grid"
    for row_idx, cells in enumerate(rows):
        row = table.add_row().cells
        for i in range(width):
            value = cells[i] if i < len(cells) else ""
            paragraph = row[i].paragraphs[0]
            paragraph.clear()
            _add_inline_runs(paragraph, value, force_bold=row_idx == 0)

def _add_equation_paragraph(doc, equation: str) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(equation.strip())
    run.font.name = "Cambria Math"
    run.font.size = Pt(12)


def _add_code_block(doc, code_lines: list[str]) -> None:
    from docx.shared import Pt
    for line in code_lines:
        p = doc.add_paragraph()
        run = p.add_run(line.rstrip())
        run.font.name = "Consolas"
        run.font.size = Pt(9)


def export_article_docx(article_text: str, title: str = "Journal Article Draft") -> tuple[io.BytesIO, str]:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt

    safe_title = re.sub(r"[^A-Za-z0-9_-]+", "_", (title or "journal_article")[:80]).strip("_") or "journal_article"
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)
    style.paragraph_format.line_spacing = 1.5

    table_buffer: list[str] = []
    code_buffer: list[str] = []
    in_code = False
    equation_buffer: list[str] = []
    in_equation = False

    for raw_line in _finalise_article_text(article_text).splitlines():
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            if in_code:
                _add_code_block(doc, code_buffer)
                code_buffer = []
                in_code = False
            else:
                if table_buffer:
                    _add_markdown_table(doc, table_buffer)
                    table_buffer = []
                in_code = True
            continue
        if in_code:
            code_buffer.append(line)
            continue

        stripped = line.strip()
        if stripped == "$$":
            if in_equation:
                _add_equation_paragraph(doc, " ".join(equation_buffer))
                equation_buffer = []
                in_equation = False
            else:
                if table_buffer:
                    _add_markdown_table(doc, table_buffer)
                    table_buffer = []
                in_equation = True
            continue
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
            if table_buffer:
                _add_markdown_table(doc, table_buffer)
                table_buffer = []
            _add_equation_paragraph(doc, stripped.strip("$").strip())
            continue
        if in_equation:
            equation_buffer.append(stripped)
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            table_buffer.append(line)
            continue
        if table_buffer:
            _add_markdown_table(doc, table_buffer)
            table_buffer = []
        if not stripped:
            continue
        if line.startswith("# "):
            p = doc.add_heading("", level=0)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_inline_runs(p, line[2:].strip())
        elif line.startswith("## "):
            p = doc.add_heading("", level=1)
            _add_inline_runs(p, line[3:].strip())
        elif line.startswith("### "):
            p = doc.add_heading("", level=2)
            _add_inline_runs(p, line[4:].strip())
        elif re.match(r"^[-*•]\s+", line):
            p = doc.add_paragraph(style="List Bullet")
            _add_inline_runs(p, re.sub(r"^[-*•]\s+", "", line).strip())
        elif re.match(r"^\d+[.)]\s+", line):
            p = doc.add_paragraph(style="List Number")
            _add_inline_runs(p, re.sub(r"^\d+[.)]\s+", "", line).strip())
        else:
            p = doc.add_paragraph()
            _add_inline_runs(p, line)
    if table_buffer:
        _add_markdown_table(doc, table_buffer)
    if code_buffer:
        _add_code_block(doc, code_buffer)
    if equation_buffer:
        _add_equation_paragraph(doc, " ".join(equation_buffer))

    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream, f"{safe_title}_journal_article_draft.docx"
