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


_TOPIC_STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or",
    "the", "to", "with", "study", "research", "article", "effect", "effects", "impact",
    "relationship", "analysis", "evidence", "case", "context",
}

# These synonym groups are used only as conservative relevance gates. They help
# retain genuine conceptual matches while rejecting records that merely share a
# country name or one common word.
_TOPIC_SYNONYM_GROUPS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("term structure",), ("term structure", "yield curve", "yield curves", "expectations hypothesis", "yield spread", "yield spreads", "maturity structure", "bond yield", "bond yields", "treasury yield", "treasury yields")),
    (("interest rate pass through", "interest rate pass-through"), ("interest rate pass through", "interest rate pass-through", "monetary transmission", "bank lending rate", "policy rate pass through")),
    (("exchange rate pass through", "exchange rate pass-through"), ("exchange rate pass through", "exchange rate pass-through", "import price pass through", "pricing to market")),
    (("financial inclusion",), ("financial inclusion", "access to finance", "financial access", "account ownership")),
    (("public procurement",), ("public procurement", "government procurement", "public contracting", "e-procurement", "electronic procurement")),
]


def _is_independent_mode(payload: dict[str, Any]) -> bool:
    return "new independent article" in str(payload.get("source_mode") or "").strip().lower()


def _prepare_payload(payload: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(payload)
    if _is_independent_mode(prepared):
        prepared["thesis_title"] = ""
        prepared["thesis_material"] = ""
    return prepared


def _normalise_match_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(rates|yields|structures|markets|policies|countries|studies)\b", lambda m: m.group(0)[:-1], text)
    return re.sub(r"\s+", " ", text).strip()


def _topic_terms(payload: dict[str, Any]) -> list[str]:
    area = _normalise_match_text(payload.get("research_area"))
    context_terms = set(_normalise_match_text(payload.get("context")).split())
    ordered: list[str] = []
    for token in area.split():
        if len(token) < 3 or token in _TOPIC_STOPWORDS or token in context_terms:
            continue
        if token not in ordered:
            ordered.append(token)
    return ordered[:14]


def _topic_anchor_phrases(payload: dict[str, Any]) -> list[str]:
    area = _normalise_match_text(payload.get("research_area"))
    anchors: list[str] = []
    for triggers, synonyms in _TOPIC_SYNONYM_GROUPS:
        if any(_normalise_match_text(trigger) in area for trigger in triggers):
            anchors.extend(_normalise_match_text(item) for item in synonyms)

    tokens = [token for token in area.split() if token not in _TOPIC_STOPWORDS]
    # Add the strongest topic n-grams. Longer phrases carry more meaning than
    # isolated words such as "interest", "rate", "education", or a country name.
    for size in (4, 3, 2):
        for index in range(max(0, len(tokens) - size + 1)):
            phrase = " ".join(tokens[index:index + size])
            if phrase and phrase not in anchors:
                anchors.append(phrase)
        if anchors:
            break
    return anchors[:18]


def _source_topic_relevance(source: dict[str, Any], payload: dict[str, Any]) -> tuple[float, list[str]]:
    title = _normalise_match_text(source.get("title"))
    abstract = _normalise_match_text(source.get("abstract"))
    venue = _normalise_match_text(source.get("source"))
    full_text = f"{title} {abstract} {venue}".strip()
    if not title or not full_text:
        return 0.0, []

    core_terms = _topic_terms(payload)
    anchors = _topic_anchor_phrases(payload)
    title_terms = set(title.split())
    full_terms = set(full_text.split())
    title_hits = [term for term in core_terms if term in title_terms]
    all_hits = [term for term in core_terms if term in full_terms]
    phrase_hits = [phrase for phrase in anchors if phrase and phrase in full_text]

    area = _normalise_match_text(payload.get("research_area"))
    special_triggered = any(
        any(_normalise_match_text(trigger) in area for trigger in triggers)
        for triggers, _ in _TOPIC_SYNONYM_GROUPS
    )
    if special_triggered and not phrase_hits:
        return 0.0, []

    if not special_triggered:
        required_hits = 1 if len(core_terms) <= 2 else max(2, (len(core_terms) + 1) // 2)
        if len(all_hits) < required_hits:
            return 0.0, []
        if not title_hits and not phrase_hits:
            return 0.0, []

    score = len(title_hits) * 5.0 + max(0, len(all_hits) - len(title_hits)) * 1.4
    score += len(phrase_hits) * 7.0
    if area and area in full_text:
        score += 12.0
    if source.get("doi"):
        score += 1.5
    year = source.get("year")
    try:
        if year and int(str(year)[:4]) >= datetime.now().year - 7:
            score += 1.5
    except Exception:
        pass
    matched = list(dict.fromkeys(phrase_hits[:4] + title_hits[:6] + all_hits[:6]))
    return score, matched


def _filter_topic_sources(
    sources: list[dict[str, Any]], payload: dict[str, Any], limit: int
) -> tuple[list[dict[str, Any]], int]:
    scored: list[tuple[float, dict[str, Any]]] = []
    excluded = 0
    for source in sources:
        score, matched = _source_topic_relevance(source, payload)
        if score <= 0:
            excluded += 1
            continue
        record = dict(source)
        record["topic_match_score"] = round(score, 2)
        record["matched_topic_terms"] = matched
        scored.append((score, record))
    scored.sort(key=lambda item: (item[0], float(item[1].get("relevance_score") or 0)), reverse=True)
    return [record for _, record in scored[:limit]], excluded


def _safe_get_deepseek_client():
    """Return a DeepSeek client used only by the article-topic idea workflow."""
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI

        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
        return OpenAI(api_key=api_key, base_url=base_url)
    except Exception:
        return None


def _select_model(article_type: str = "") -> str:
    # Article-topic ideas always use DeepSeek V4 Pro. The article writer remains on OpenAI.
    return os.getenv("DEEPSEEK_ARTICLE_IDEA_MODEL", "deepseek-v4-pro").strip() or "deepseek-v4-pro"


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
    independent = _is_independent_mode(payload)
    title = str(payload.get("research_area") if independent else (payload.get("thesis_title") or payload.get("research_area") or "")).strip()
    return {
        "title": title,
        "research_area": str(payload.get("research_area") or "").strip(),
        "study_context": str(payload.get("context") or "").strip(),
        "objectives": _clean_list(payload.get("variables_or_themes"), 5),
        "level": "Journal article",
        "discipline": str(payload.get("discipline") or "").strip(),
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
        return [], {
            "provider_errors": [],
            "excluded_retracted_count": 0,
            "excluded_irrelevant_count": 0,
            "quality_filters": [],
        }
    max_results = int(os.getenv("ARTICLEREADY_IDEA_SOURCE_LIMIT", "16"))
    query_parts = [
        str(payload.get("research_area") or "").strip(),
        str(payload.get("variables_or_themes") or "").strip(),
        str(payload.get("keywords") or "").strip(),
    ]
    # Context helps when it is central, but it must not dominate the search.
    context = str(payload.get("context") or "").strip()
    query = " ".join(part for part in query_parts if part)
    if context and _normalise_match_text(context) not in _normalise_match_text(query):
        query = f"{query} {context}".strip()
    query = query[:220]
    try:
        result = search_literature_sources(
            _build_search_profile(payload),
            query=query,
            max_results=max(max_results * 2, 20),
            include_older_foundational=bool(payload.get("include_older_foundational", True)),
        )
    except Exception as exc:
        return [], {
            "provider_errors": [f"Source search failed: {str(exc)[:180]}"],
            "excluded_retracted_count": 0,
            "excluded_irrelevant_count": 0,
            "quality_filters": [],
        }
    safe_sources = [src for src in (result.get("sources") or []) if not _looks_retracted(src)]
    sources, excluded_irrelevant = _filter_topic_sources(safe_sources, payload, max_results)
    result["excluded_irrelevant_count"] = excluded_irrelevant
    result["quality_filters"] = list(result.get("quality_filters") or []) + [
        "Topic-idea records must pass a conservative title/abstract relevance gate.",
        "Country-only and single-common-word matches are excluded.",
        "A smaller relevant list is preferred to a longer noisy list.",
    ]
    if not sources and safe_sources:
        result.setdefault("provider_errors", []).append(
            {
                "provider": "relevance_filter",
                "error": "Scholarly records were found, but none matched the topic closely enough to retain.",
            }
        )
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
                "topic_match_score": src.get("topic_match_score"),
                "matched_topic_terms": src.get("matched_topic_terms") or [],
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
    """Extract final answer text from DeepSeek ChatCompletions or OpenAI-style responses."""
    choices = getattr(response, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None) if message is not None else None
        if content:
            return str(content)

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


def _source_origin_label(payload: dict[str, Any]) -> str:
    mode = str(payload.get("source_mode") or "").lower()
    if _is_independent_mode(payload):
        return "the proposed independent study"
    if "dataset" in mode:
        return "the existing dataset"
    if "project" in mode:
        return "the supplied research project"
    if "ongoing" in mode:
        return "the ongoing thesis or dissertation"
    return "the supplied thesis or dissertation"


def _readiness_from_inputs(payload: dict[str, Any], index: int) -> int:
    score = 32
    weighted_fields = [
        ("research_area", 10),
        ("discipline", 5),
        ("context", 6),
        ("methodology", 10),
        ("data_available", 10),
        ("variables_or_themes", 8),
        ("preferred_contribution", 5),
        ("target_journal", 4),
        ("journal_scope", 5),
    ]
    for field, points in weighted_fields:
        if str(payload.get(field) or "").strip():
            score += points
    if not _is_independent_mode(payload) and str(payload.get("thesis_material") or "").strip():
        score += 8
    if _is_independent_mode(payload) and not any(
        str(payload.get(field) or "").strip() for field in ["methodology", "data_available", "variables_or_themes"]
    ):
        score = min(score, 58)
    return max(35, min(88, score - (index - 1) * 2))


def _clean_source_mode_language(value: Any, payload: dict[str, Any]) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not _is_independent_mode(payload):
        return text
    replacements = [
        (r"\bthe original thesis\b", "the proposed independent study"),
        (r"\bthe supplied thesis\b", "the proposed independent study"),
        (r"\bthe thesis dataset\b", "the proposed dataset"),
        (r"\bthe thesis\b", "the proposed independent study"),
        (r"\bthesis material\b", "planned study information"),
        (r"\bthesis evidence\b", "planned or collected evidence"),
        (r"\bthesis findings\b", "future or uploaded findings"),
        (r"\bdissertation\b", "independent study"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _term_structure_templates(area: str, context: str) -> list[dict[str, Any]]:
    setting = context or "Ghana"
    return [
        {
            "title": f"Testing the Expectations Hypothesis Across {setting}'s Yield Curve",
            "angle": "A focused empirical test of whether forward rates contain information about future short-term rates across maturities.",
            "gap": "A current literature review is needed to establish how recent Ghanaian evidence treats maturity coverage, sample period and model specification.",
            "objective": f"To test the expectations hypothesis of the term structure of interest rates in {setting} across selected maturities.",
            "questions_or_hypotheses": [
                "Do forward rates predict subsequent short-term interest rates?",
                "Does the predictive relationship differ across maturity segments?",
            ],
            "contribution": "Provides a clearly bounded test of a central yield-curve proposition using country-specific maturity data.",
            "method_and_data_route": "Use maturity-matched Treasury bill and government bond yields with forecast regressions, cointegration, VAR or related tests justified by the data frequency and sample length.",
            "research_route": "secondary_data",
        },
        {
            "title": f"Monetary Policy Shocks and the Shape of {setting}'s Yield Curve",
            "angle": "A monetary-transmission article examining how policy-rate changes affect the level, slope and curvature of the yield curve.",
            "gap": "The article should verify whether existing studies identify maturity-specific responses and distinguish anticipated from unanticipated policy changes.",
            "objective": f"To examine how monetary policy shocks affect the level, slope and curvature of the term structure of interest rates in {setting}.",
            "questions_or_hypotheses": [
                "How do short-, medium- and long-term yields respond to policy-rate shocks?",
                "Are the responses persistent or concentrated around policy announcements?",
            ],
            "contribution": "Connects yield-curve dynamics to the transmission of monetary policy across maturities.",
            "method_and_data_route": "Combine policy-rate and maturity-specific yield series using event-study, local-projection, VAR or structural-break methods, depending on data frequency and identification quality.",
            "research_route": "secondary_data",
        },
        {
            "title": f"Inflation Expectations, Term Premia and Government Bond Yields in {setting}",
            "angle": "A macro-finance article separating expectations and risk-premium explanations for long-term yields.",
            "gap": "The proposed paper must establish whether available Ghana evidence adequately distinguishes expected future short rates from inflation and term-premium components.",
            "objective": f"To assess the roles of inflation expectations and term premia in explaining government bond yields in {setting}.",
            "questions_or_hypotheses": [
                "How strongly are long-term yields associated with expected inflation?",
                "Do estimated term premia vary across monetary or fiscal conditions?",
            ],
            "contribution": "Provides a more precise explanation of long-term yield movements than a simple interest-rate correlation.",
            "method_and_data_route": "Use official yield, inflation, policy-rate and macroeconomic series. Apply an expectations-augmented yield model, decomposition approach or carefully justified proxy design.",
            "research_route": "secondary_data",
        },
        {
            "title": f"Structural Breaks and Regime Changes in {setting}'s Term Structure of Interest Rates",
            "angle": "A time-varying article examining whether yield-curve behaviour changes across policy, inflation or market regimes.",
            "gap": "A literature and data check is needed to identify defensible break dates rather than assuming that the full sample is stable.",
            "objective": f"To identify structural breaks and regime-dependent changes in the term structure of interest rates in {setting}.",
            "questions_or_hypotheses": [
                "When do major shifts in yield-curve level, slope or curvature occur?",
                "How do the identified regimes relate to monetary, inflation or fiscal conditions?",
            ],
            "contribution": "Shows when full-period averages conceal economically important changes in yield-curve behaviour.",
            "method_and_data_route": "Use maturity-specific yield series with formal break tests, Markov-switching, rolling estimation or time-varying parameter models supported by the sample size.",
            "research_route": "secondary_data",
        },
        {
            "title": f"Can {setting}'s Yield Curve Predict Inflation and Economic Activity?",
            "angle": "A forecasting article testing whether yield-curve factors contain information about subsequent macroeconomic outcomes.",
            "gap": "The paper should verify the forecasting horizon, benchmark models and out-of-sample evidence missing from or contested in the current literature.",
            "objective": f"To evaluate whether the slope and other factors of {setting}'s yield curve predict inflation and economic activity.",
            "questions_or_hypotheses": [
                "Does the yield-curve slope improve forecasts of inflation or output growth?",
                "Which maturity combinations provide the strongest predictive information?",
            ],
            "contribution": "Tests the practical information content of the yield curve for macroeconomic monitoring and forecasting.",
            "method_and_data_route": "Construct yield-curve factors and compare in-sample and out-of-sample forecasts against transparent benchmark models using official macroeconomic series.",
            "research_route": "secondary_data",
        },
        {
            "title": f"Liquidity, Market Segmentation and Yield Spreads in {setting}'s Government Securities Market",
            "angle": "A market-microstructure article focused on whether liquidity and maturity segmentation help explain yield differentials.",
            "gap": "Feasibility depends on obtaining defensible liquidity, trading, issuance or bid-ask proxies. The literature review must confirm which measures are credible in the local market.",
            "objective": f"To examine whether liquidity and market segmentation explain yield spreads across government-security maturities in {setting}.",
            "questions_or_hypotheses": [
                "Are less liquid maturities associated with higher yields or wider spreads?",
                "Does issuance concentration or investor segmentation alter the maturity-yield relationship?",
            ],
            "contribution": "Adds a market-structure explanation to macroeconomic accounts of the yield curve.",
            "method_and_data_route": "Use secondary issuance, trading or quoted-yield data with appropriate liquidity proxies. Do not proceed unless coverage is adequate across maturities and time.",
            "research_route": "secondary_data",
        },
        {
            "title": f"Modelling {setting}'s Yield Curve with Nelson-Siegel and Svensson Specifications",
            "angle": "A methodological article comparing parsimonious yield-curve models and their stability across maturities and periods.",
            "gap": "The article should establish whether model fit, parameter stability and forecasting performance have been compared using recent local data.",
            "objective": f"To compare the fit and forecasting performance of Nelson-Siegel and Svensson yield-curve models for {setting}.",
            "questions_or_hypotheses": [
                "Which specification best captures the observed maturity structure?",
                "How stable are the estimated level, slope and curvature factors over time?",
            ],
            "contribution": "Provides transparent evidence on model choice for pricing, forecasting and policy analysis.",
            "method_and_data_route": "Use a sufficiently dense set of maturity-specific yields, estimate competing curve specifications and compare fit, stability and forecast errors.",
            "research_route": "secondary_data",
        },
        {
            "title": f"The Term Structure of Interest Rates in {setting}: A Comparative African Perspective",
            "angle": "A comparative article testing whether yield-curve behaviour differs across selected African sovereign-debt markets.",
            "gap": "The comparison is publishable only if countries have sufficiently comparable maturity, frequency and market data. Country selection must be theoretically justified.",
            "objective": f"To compare the dynamics and macroeconomic determinants of the term structure of interest rates in {setting} and selected African markets.",
            "questions_or_hypotheses": [
                "Which yield-curve features are common across the selected markets?",
                "Which institutional or macroeconomic conditions explain cross-country differences?",
            ],
            "contribution": "Distinguishes market-specific patterns from broader regional regularities.",
            "method_and_data_route": "Build a harmonised secondary dataset of maturity-specific sovereign yields and macroeconomic indicators. Use comparable factor, panel or country-specific models.",
            "research_route": "secondary_data",
        },
    ]


def _fallback_ideas(payload: dict[str, Any]) -> list[dict[str, Any]]:
    area = str(payload.get("research_area") or "the selected research area").strip()
    context = str(payload.get("context") or "").strip()
    article_type = str(payload.get("article_type") or "Empirical research article").strip()
    target_journal = str(payload.get("target_journal") or "").strip()
    contribution = str(payload.get("preferred_contribution") or "focused empirical or conceptual evidence").strip()
    variables = _clean_list(payload.get("variables_or_themes"), 8)
    independent = _is_independent_mode(payload)
    origin = _source_origin_label(payload)
    focal = variables[0] if variables else area
    outcome = variables[1] if len(variables) > 1 else ""
    mechanism = variables[2] if len(variables) > 2 else ""
    boundary = variables[3] if len(variables) > 3 else ""

    area_lower = _normalise_match_text(area)
    if "term structure" in area_lower or "yield curve" in area_lower:
        templates = _term_structure_templates(area, context)
    elif outcome:
        templates = [
            {
                "title": f"{focal.title()} and {outcome.title()}: Evidence from {context or 'the Selected Context'}",
                "angle": "A focused direct-relationship article built around one clearly specified empirical claim.",
                "gap": f"A targeted literature review is needed to establish the unresolved article-level question linking {focal} and {outcome}.",
                "objective": _article_objective(area, focal, outcome, context),
                "questions_or_hypotheses": [
                    f"How is {focal} associated with {outcome}{' in ' + context if context else ''}?",
                    f"H1: {focal} is significantly associated with {outcome}.",
                ],
                "contribution": contribution,
                "method_and_data_route": str(payload.get("methodology") or payload.get("data_available") or f"Specify a design and dataset capable of estimating the relationship between {focal} and {outcome}."),
            },
            {
                "title": f"Explaining {outcome.title()}: The Role of {(mechanism or 'a Plausible Mechanism').title()}",
                "angle": "A mechanism-centred article that explains how or why the focal relationship may occur.",
                "gap": "The mechanism must be grounded in theory and measured with data capable of supporting the proposed explanation.",
                "objective": f"To examine whether and how {mechanism or 'a theoretically justified mechanism'} explains variation in {outcome}{' in ' + context if context else ''}.",
                "questions_or_hypotheses": [f"What mechanism links {focal} to {outcome}?"],
                "contribution": f"Clarifies the process through which {focal} may influence {outcome}.",
                "method_and_data_route": "Use mediation, process analysis or qualitative mechanism tracing only when temporal ordering and measurement are defensible.",
            },
            {
                "title": f"When Does {focal.title()} Matter for {outcome.title()}?",
                "angle": "A boundary-condition article focused on heterogeneity, moderation or contextual differences.",
                "gap": "The proposed boundary condition must be theoretically justified and available in the planned or existing evidence.",
                "objective": f"To determine whether the relationship between {focal} and {outcome} varies across {boundary or 'a theoretically relevant condition'}.",
                "questions_or_hypotheses": [f"Under what conditions does the relationship between {focal} and {outcome} strengthen, weaken or reverse?"],
                "contribution": "Identifies a meaningful limit or condition of the focal relationship.",
                "method_and_data_route": "Use interaction, subgroup, multigroup, comparative-case or stratified analysis supported by the design and sample.",
            },
        ]
    else:
        templates = [
            {
                "title": f"Drivers of {area.title()} in {context or 'the Selected Context'}",
                "angle": "A determinants article that converts a broad area into a testable set of theoretically justified explanatory factors.",
                "gap": "The final gap must be established from closely matched literature rather than assumed from the location alone.",
                "objective": f"To identify and estimate the principal drivers of {area}{' in ' + context if context else ''}.",
                "questions_or_hypotheses": [f"Which theoretically justified factors explain variation in {area}?"],
                "contribution": contribution,
                "method_and_data_route": str(payload.get("methodology") or "Define the outcome, explanatory variables, unit of analysis, data source and identification strategy before drafting the article."),
            },
            {
                "title": f"Change over Time in {area.title()}: Patterns and Turning Points",
                "angle": "A temporal article focused on dynamics, phases, shocks or structural change.",
                "gap": "This route is feasible only when the study has adequate longitudinal or repeated observations.",
                "objective": f"To analyse how {area} changes over time and identify meaningful turning points or regimes.",
                "questions_or_hypotheses": [f"How has {area} evolved across the observed period?"],
                "contribution": "Adds temporal precision rather than relying on a full-period average.",
                "method_and_data_route": "Use trend, longitudinal, event, change-point, panel or time-varying methods only when the data support them.",
            },
            {
                "title": f"A Comparative Analysis of {area.title()} Across Relevant Settings",
                "angle": "A comparative article distinguishing general patterns from setting-specific differences.",
                "gap": "The cases must be comparable and selected through a clear theoretical or policy rationale.",
                "objective": f"To compare {area} across selected settings and explain the most important differences.",
                "questions_or_hypotheses": ["Which patterns are shared and which are context-specific?"],
                "contribution": "Clarifies the boundary of existing explanations through a defensible comparison.",
                "method_and_data_route": "Use harmonised data, comparable cases or a transparent comparative design.",
            },
        ]

    templates.extend([
        {
            "title": f"From Evidence to Action: Policy and Practice Implications of {area.title()}",
            "angle": "A policy or practice article centred on a named decision problem and intended user of the evidence.",
            "gap": "The article needs an explicit evidence-to-action chain and must avoid recommendations unsupported by the analysis.",
            "objective": f"To develop evidence-based policy or practice implications concerning {area}{' in ' + context if context else ''}.",
            "questions_or_hypotheses": ["Which decision problem can the evidence address, and under what constraints?"],
            "contribution": "Connects a focused evidence base to an implementable decision problem.",
            "method_and_data_route": "Use empirical findings, policy documents and implementation constraints. Do not draft recommendations before the evidence is available.",
        },
        {
            "title": f"A Focused Review of {area.title()}: Evidence, Tensions and a Research Agenda",
            "angle": "A review article using a transparent search, screening and synthesis method.",
            "gap": "The review must demonstrate fragmentation, disagreement or methodological inconsistency through a reproducible protocol.",
            "objective": f"To synthesise and critically organise evidence on {area}, identify unresolved tensions and propose a focused research agenda.",
            "questions_or_hypotheses": [f"How has {area} been conceptualised and studied?", "Which findings are robust, contested or method-dependent?"],
            "contribution": "Offers critical synthesis and conceptual clarification rather than a descriptive summary.",
            "method_and_data_route": "Use a systematic, scoping, integrative or structured review protocol appropriate to the question and evidence base.",
            "research_route": "review_or_conceptual",
        },
        {
            "title": f"Measurement and Model Choice in Research on {area.title()}",
            "angle": "A methodological article examining how measurement, specification or validation choices affect conclusions.",
            "gap": "The idea is viable only when alternative measures or models can be compared using adequate evidence.",
            "objective": f"To evaluate how measurement or model choices affect conclusions about {area}.",
            "questions_or_hypotheses": ["Which measurement or model choices materially change the results?"],
            "contribution": "Improves the transparency and robustness of future work in the area.",
            "method_and_data_route": "Use validation, robustness analysis, model comparison or simulation only where the required data and assumptions are available.",
        },
        {
            "title": f"Heterogeneous Patterns in {area.title()}: Who, Where or When Does It Differ?",
            "angle": "A distributional or subgroup article examining meaningful heterogeneity rather than only average effects.",
            "gap": "Subgroups or settings must be pre-specified and large enough for credible comparison.",
            "objective": f"To examine whether patterns in {area} differ across theoretically or practically relevant groups, settings or periods.",
            "questions_or_hypotheses": ["Where do the central patterns strengthen, weaken or reverse?"],
            "contribution": "Shows the limits of average findings and identifies meaningful variation.",
            "method_and_data_route": "Use subgroup, quantile, interaction, multigroup, comparative-case or stratified analysis supported by the data.",
        },
    ])

    max_ideas = max(3, min(int(payload.get("max_ideas") or 6), 10))
    output: list[dict[str, Any]] = []
    for index, item in enumerate(templates[:max_ideas], start=1):
        route = str(item.get("research_route") or infer_research_route(payload, str(item.get("method_and_data_route") or "")))
        if route == "undetermined" and "review" in str(item.get("angle") or "").lower():
            route = "review_or_conceptual"
        if independent:
            evidence_needed = [
                "A precisely defined dependent variable, outcome or focal phenomenon",
                "A defensible theoretical or conceptual basis for the proposed relationships",
                "A feasible data source, sampling frame or instrument matched to the research route",
                "Closely matched verified literature that establishes the article-level gap",
                "A target-journal fit check before full drafting",
            ]
            scope_warning = "This is a provisional independent-article idea. Do not present findings until data have been collected or analysed."
        else:
            evidence_needed = [
                f"A clearly bounded result, argument or dataset component from {origin}",
                "Closely matched verified literature that establishes the article-level gap",
                "Complete method and result details needed to support the central claim",
                "A target-journal fit check before submission",
            ]
            scope_warning = f"Use only the part of {origin} needed for one central article contribution. Avoid duplicated claims or salami slicing."
        item.update(
            {
                "idea_number": index,
                "article_type": article_type,
                "journal_fit": f"Assess against {target_journal or 'the selected journal'} aims, scope, recent publications and word limit.",
                "suggested_sections": _suggested_sections(article_type),
                "keywords": _clean_list([area, focal, outcome, mechanism, context], 7),
                "evidence_needed": evidence_needed,
                "scope_warning": scope_warning,
                "readiness_score": _readiness_from_inputs(payload, index),
                "research_route": route,
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
        title = _clean_source_mode_language(raw.get("title"), payload)
        if not title:
            continue
        method_route = _clean_source_mode_language(raw.get("method_and_data_route"), payload)
        route = str(raw.get("research_route") or "").strip()
        if not route or route == "undetermined":
            route = infer_research_route(payload, f"{title} {method_route}")
        score = max(0, min(int(raw.get("readiness_score") or 70), 100))
        if _is_independent_mode(payload):
            # A topic alone cannot be highly ready. Data, method, constructs and a
            # target-journal fit must raise the score.
            score = min(score, _readiness_from_inputs(payload, index) + 5)
        ideas.append(
            {
                "idea_number": index,
                "title": title,
                "article_type": str(raw.get("article_type") or payload.get("article_type") or "Empirical research article"),
                "angle": _clean_source_mode_language(raw.get("angle"), payload),
                "gap": _clean_source_mode_language(raw.get("gap"), payload),
                "objective": _clean_source_mode_language(raw.get("objective"), payload),
                "questions_or_hypotheses": [
                    _clean_source_mode_language(item, payload)
                    for item in _clean_list(raw.get("questions_or_hypotheses"), 5)
                ],
                "contribution": _clean_source_mode_language(raw.get("contribution"), payload),
                "method_and_data_route": method_route,
                "journal_fit": _clean_source_mode_language(raw.get("journal_fit"), payload),
                "suggested_sections": _clean_list(raw.get("suggested_sections"), 10),
                "keywords": _clean_list(raw.get("keywords"), 8),
                "evidence_needed": [
                    _clean_source_mode_language(item, payload)
                    for item in _clean_list(raw.get("evidence_needed"), 8)
                ],
                "scope_warning": _clean_source_mode_language(
                    raw.get("scope_warning") or "Build the article around one central contribution.", payload
                ),
                "readiness_score": score,
                "research_route": route,
            }
        )
    return ideas


def generate_article_ideas(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _prepare_payload(payload)
    if not str(payload.get("research_area") or "").strip():
        raise ValueError("Research area is required.")

    independent = _is_independent_mode(payload)
    sources, source_result = _search_sources(payload)
    source_records = _source_context(sources)
    model = _select_model(str(payload.get("article_type") or ""))
    client = _safe_get_deepseek_client()
    provider_errors: list[Any] = list(source_result.get("provider_errors") or [])
    ideas: list[dict[str, Any]] = []
    mode = "structured_fallback"
    portfolio_note = ""

    if client and os.getenv("ARTICLEREADY_IDEA_USE_AI", "1").strip().lower() not in {"0", "false", "no"}:
        current_year = datetime.now().year
        if independent:
            task = "Generate new, independent journal-article topic ideas from the research area and publication inputs."
            source_mode_rules = [
                "Do not refer to a thesis, dissertation, project, original study, previous findings or thesis dataset.",
                "Treat every idea as a proposed study. Do not imply that results already exist.",
                "When data, variables or methods are not supplied, specify exactly what must be defined or obtained before the idea is ready.",
                "For macroeconomic, financial-market, interest-rate, yield-curve, bond, exchange-rate, stock-price or policy-rate topics, default to secondary or archival data unless the user explicitly requests primary research.",
            ]
        else:
            task = "Generate focused journal-article topic ideas from the supplied study, thesis, project or dataset."
            source_mode_rules = [
                "Refer to the source material according to the selected source mode. Do not call a project or dataset a thesis.",
                "Use only the bounded evidence needed for one article contribution and avoid duplicated claims or salami slicing.",
                "Do not imply that missing findings or analyses are already available.",
            ]

        prompt = {
            "task": task,
            "current_year": current_year,
            "source_mode": payload.get("source_mode"),
            "inputs": payload,
            "source_records": source_records,
            "article_design_rules": source_mode_rules + [
                "Each idea must have one central question or contribution and a feasible evidence route.",
                "Use one clear overall objective and no more than three tightly aligned questions or hypotheses unless the article type requires otherwise.",
                "Do not create novelty merely by adding a country name. State the theoretical, empirical, methodological, policy or contextual contribution.",
                "Match the research route to the subject and proposed evidence. Do not recommend questionnaires or qualitative instruments for market, macroeconomic or official time-series topics unless the user explicitly asks for them.",
                "For review articles, require a transparent and defensible review method.",
                "Do not fabricate findings, citations, journal requirements, samples, variables or statistical results.",
                "Use a supplied source record only when its title or abstract is directly relevant to the research area. If the source list is empty or insufficient, state that a targeted literature search is still needed.",
                "Titles must be concise, searchable and article-like.",
                "The readiness score measures input completeness, evidence feasibility, contribution clarity and target-journal fit. A research area alone must not receive a high score.",
                "Identify whether each idea is best suited to secondary data, survey or scale, qualitative instruments, mixed methods, experimental instruments, or review/conceptual work.",
                "For secondary-data ideas, the app will attach candidate official data sources. For primary or qualitative ideas, it will attach candidate questionnaire, scale, interview-guide or instrument sources that still require verification.",
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
                        "evidence_needed": ["specific evidence, variables, data or results needed"],
                        "scope_warning": "string",
                        "readiness_score": 0,
                        "research_route": "secondary_data | survey_or_scale | qualitative_instrument | mixed_methods | experimental_instrument | review_or_conceptual | undetermined",
                    }
                ],
                "portfolio_note": "Briefly explain how to choose among the ideas and avoid overlap.",
            },
            "output_rule": "Return valid JSON only, with no markdown fences.",
        }
        try:
            thinking_enabled = os.getenv("DEEPSEEK_ARTICLE_IDEA_THINKING", "1").strip().lower() not in {
                "0", "false", "no", "off"
            }
            reasoning_effort = os.getenv("DEEPSEEK_ARTICLE_IDEA_REASONING_EFFORT", "high").strip().lower()
            if reasoning_effort not in {"high", "max"}:
                reasoning_effort = "high"
            max_tokens = max(2000, min(int(os.getenv("DEEPSEEK_ARTICLE_IDEA_MAX_TOKENS", "12000")), 50000))
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are ArticleReady AI's article development editor. Produce focused, ethical and publication-oriented article ideas. "
                        "Follow the selected source mode exactly, reject irrelevant literature signals, avoid invented novelty and return valid JSON only."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, indent=2)},
            ]
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=max_tokens,
                    stream=False,
                    extra_body={
                        "thinking": {"type": "enabled" if thinking_enabled else "disabled"},
                        "reasoning_effort": reasoning_effort,
                    },
                )
            except Exception as first_exc:
                message = str(first_exc).lower()
                retryable = any(term in message for term in [
                    "response_format", "thinking", "reasoning_effort", "unsupported parameter", "unknown parameter", "invalid parameter"
                ])
                if not retryable:
                    raise
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    stream=False,
                )
            parsed = _extract_json(_response_text(response))
            ideas = _normalise_ideas(parsed or {}, payload)
            if ideas:
                mode = "ai_generated"
                portfolio_note = _clean_source_mode_language((parsed or {}).get("portfolio_note"), payload)
        except Exception as exc:
            provider_errors.append(f"DeepSeek article idea generation failed: {str(exc)[:240]}")
    elif os.getenv("ARTICLEREADY_IDEA_USE_AI", "1").strip().lower() not in {"0", "false", "no"} and not client:
        provider_errors.append(
            "DEEPSEEK_API_KEY is not configured. Article ideas were generated with the structured fallback."
        )

    if not ideas:
        ideas = _fallback_ideas(payload)
        if independent:
            portfolio_note = (
                "These are alternative directions for a new independent article. Select one idea, confirm its data and method route, "
                "then establish the gap with closely matched literature before drafting."
            )
        else:
            portfolio_note = (
                "Use the ideas together only when each paper has a distinct question, analysis and contribution. "
                "Avoid duplicated claims or minimally different papers from the same source material."
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
            f"{idea.get('title', '')} {idea.get('objective', '')} {idea.get('method_and_data_route', '')} {idea.get('research_route', '')}"
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

    model_used = model if mode == "ai_generated" else "structured fallback"
    return {
        "ideas": ideas,
        "portfolio_note": portfolio_note,
        "model_used": model_used,
        "mode": mode,
        "source_records_used": source_records,
        "research_resources": resource_result,
        "provider_errors": provider_errors,
        "excluded_retracted_count": int(source_result.get("excluded_retracted_count") or 0),
        "excluded_irrelevant_count": int(source_result.get("excluded_irrelevant_count") or 0),
        "quality_filters": source_result.get("quality_filters") or [
            "Retracted and withdrawn records excluded where detectable.",
            "Country-only and weak keyword matches excluded.",
            "Ideas narrowed to one central article contribution.",
            "Methods and evidence requirements stated explicitly.",
        ],
    }

