from __future__ import annotations

import re
from typing import Any

try:
    from app.source_finder import search_literature_sources
except Exception:  # pragma: no cover
    search_literature_sources = None


_STOPWORDS = {
    "and", "the", "of", "in", "on", "for", "to", "a", "an", "with", "from", "by", "or",
    "study", "research", "article", "effects", "effect", "relationship", "among", "using", "analysis",
}


DATA_SOURCE_CATALOG: list[dict[str, Any]] = [
    {
        "name": "World Development Indicators",
        "provider": "World Bank",
        "url": "https://databank.worldbank.org/source/world-development-indicators",
        "coverage": "Cross-country annual indicators on development, macroeconomics, trade, population, education, health, infrastructure and environment.",
        "keywords": ["macroeconomic", "gdp", "inflation", "exchange rate", "trade", "population", "education", "health", "environment", "development", "cross-country"],
        "access_note": "Open data. Check indicator definitions, country coverage, revisions and missing years before analysis.",
    },
    {
        "name": "Worldwide Governance Indicators",
        "provider": "World Bank",
        "url": "https://www.worldbank.org/en/publication/worldwide-governance-indicators",
        "coverage": "Country-level governance measures, including government effectiveness, regulatory quality, rule of law and control of corruption.",
        "keywords": ["governance", "corruption", "rule of law", "government effectiveness", "regulatory quality", "institution", "public sector"],
        "access_note": "Open aggregate indicators. Review the methodological cautions and uncertainty intervals.",
    },
    {
        "name": "World Bank Enterprise Surveys",
        "provider": "World Bank",
        "url": "https://www.enterprisesurveys.org/",
        "coverage": "Firm-level survey data on business conditions, finance, innovation, regulation, corruption, infrastructure and performance.",
        "keywords": ["firm", "enterprise", "business", "sme", "finance", "innovation", "productivity", "corruption", "private sector", "manager"],
        "access_note": "Microdata access is available under stated terms. Check country-wave comparability and sampling weights.",
    },
    {
        "name": "International Financial Statistics and IMF Data",
        "provider": "International Monetary Fund",
        "url": "https://www.imf.org/en/Data",
        "coverage": "Macroeconomic, monetary, balance-of-payments, exchange-rate, fiscal and financial indicators.",
        "keywords": ["inflation", "exchange rate", "interest rate", "money", "fiscal", "debt", "balance of payments", "financial", "macroeconomic"],
        "access_note": "Some series are openly accessible while others may require institutional access. Verify frequency and vintage.",
    },
    {
        "name": "OECD Data Explorer",
        "provider": "Organisation for Economic Co-operation and Development",
        "url": "https://data-explorer.oecd.org/",
        "coverage": "Comparable economic, education, labour, public governance, tax, health, environment and social indicators.",
        "keywords": ["oecd", "education", "labour", "tax", "public governance", "health", "social", "productivity", "innovation", "policy"],
        "access_note": "Open metadata and many downloadable series. Confirm whether the study context is covered.",
    },
    {
        "name": "UN SDG Global Database",
        "provider": "United Nations Statistics Division",
        "url": "https://unstats.un.org/sdgs/dataportal",
        "coverage": "Official indicators for the Sustainable Development Goals across countries and years.",
        "keywords": ["sdg", "sustainable development", "poverty", "gender", "inequality", "climate", "education", "health", "institutions"],
        "access_note": "Open data. Review disaggregation, estimation status and national versus internationally harmonised series.",
    },
    {
        "name": "UN Comtrade",
        "provider": "United Nations Statistics Division",
        "url": "https://comtradeplus.un.org/",
        "coverage": "Detailed bilateral merchandise trade flows by product, reporter, partner and period.",
        "keywords": ["trade", "export", "import", "commodity", "bilateral", "tariff", "market", "currency"],
        "access_note": "Open access with API and download limits. Harmonise product classifications across years.",
    },
    {
        "name": "ILOSTAT",
        "provider": "International Labour Organization",
        "url": "https://ilostat.ilo.org/data/",
        "coverage": "Employment, unemployment, wages, labour force participation, informality, working conditions and related indicators.",
        "keywords": ["employment", "unemployment", "labour", "wage", "informal", "work", "occupation", "productivity"],
        "access_note": "Open data. Check indicator definitions, modelled estimates and subgroup coverage.",
    },
    {
        "name": "UNESCO Institute for Statistics",
        "provider": "UNESCO",
        "url": "https://uis.unesco.org/",
        "coverage": "Internationally comparable education, science, culture and communication indicators.",
        "keywords": ["education", "school", "student", "teacher", "enrolment", "literacy", "learning", "university", "science"],
        "access_note": "Open data. Confirm level-of-education coding and country-year completeness.",
    },
    {
        "name": "WHO Global Health Observatory",
        "provider": "World Health Organization",
        "url": "https://www.who.int/data/gho",
        "coverage": "Global health status, disease burden, health systems, service coverage and risk-factor indicators.",
        "keywords": ["health", "disease", "mortality", "hospital", "healthcare", "nursing", "public health", "risk factor"],
        "access_note": "Open data. Distinguish observed, modelled and estimated values.",
    },
    {
        "name": "Demographic and Health Surveys",
        "provider": "The DHS Program",
        "url": "https://dhsprogram.com/data/",
        "coverage": "Household and individual microdata on population, fertility, maternal and child health, nutrition, gender and related topics.",
        "keywords": ["household", "women", "child", "maternal", "fertility", "nutrition", "health", "gender", "demographic"],
        "access_note": "Registration and project approval are normally required for microdata. Use survey weights and account for the complex design.",
    },
    {
        "name": "Multiple Indicator Cluster Surveys",
        "provider": "UNICEF",
        "url": "https://mics.unicef.org/surveys",
        "coverage": "Household survey microdata on children, women, education, health, protection, water, sanitation and social conditions.",
        "keywords": ["child", "women", "household", "education", "health", "water", "sanitation", "poverty", "protection"],
        "access_note": "Microdata availability varies by survey. Apply weights and retain the survey design variables.",
    },
    {
        "name": "Living Standards Measurement Study",
        "provider": "World Bank",
        "url": "https://www.worldbank.org/en/programs/lsms",
        "coverage": "Household and agricultural microdata on welfare, income, consumption, labour, assets and livelihoods.",
        "keywords": ["household", "income", "consumption", "poverty", "agriculture", "welfare", "livelihood", "labour"],
        "access_note": "Open or registered access depending on the survey. Check panel identifiers and questionnaire changes between waves.",
    },
    {
        "name": "Afrobarometer Data",
        "provider": "Afrobarometer",
        "url": "https://www.afrobarometer.org/data/",
        "coverage": "Public opinion microdata on democracy, governance, public services, trust, economy, corruption and citizenship across African countries.",
        "keywords": ["africa", "public opinion", "governance", "trust", "democracy", "corruption", "citizen", "public service", "ghana"],
        "access_note": "Open data with attribution requirements. Compare question wording and country coverage across rounds.",
    },
    {
        "name": "Ghana Statistical Service Data",
        "provider": "Ghana Statistical Service",
        "url": "https://statsghana.gov.gh/",
        "coverage": "Ghana census, household, labour, price, national accounts, demographic and sector statistics.",
        "keywords": ["ghana", "census", "household", "labour", "population", "inflation", "regional", "district", "national accounts"],
        "access_note": "Use official releases and microdata access procedures. Record the survey edition and geographic coding used.",
    },
    {
        "name": "Bank of Ghana Economic Data",
        "provider": "Bank of Ghana",
        "url": "https://www.bog.gov.gh/economic-data/",
        "coverage": "Ghana monetary, financial, banking, exchange-rate, interest-rate and macroeconomic series.",
        "keywords": ["ghana", "bank", "exchange rate", "interest rate", "inflation", "credit", "financial", "monetary", "currency"],
        "access_note": "Official series. Document the release date, frequency, rebasing and any subsequent revisions.",
    },
    {
        "name": "Open Contracting Data Registry",
        "provider": "Open Contracting Partnership",
        "url": "https://data.open-contracting.org/",
        "coverage": "Public procurement and contracting records published in the Open Contracting Data Standard by participating jurisdictions.",
        "keywords": ["procurement", "contract", "tender", "public expenditure", "supplier", "award", "e-procurement", "open contracting"],
        "access_note": "Open data, but completeness differs across publishers. Assess coverage of planning, tender, award, contract and implementation stages.",
    },
    {
        "name": "Tenders Electronic Daily",
        "provider": "European Union Publications Office",
        "url": "https://ted.europa.eu/",
        "coverage": "European public procurement notices, awards and related contract information.",
        "keywords": ["procurement", "tender", "contract", "supplier", "award", "europe", "public sector"],
        "access_note": "Open notices and downloadable data. Check threshold coverage and changes in notice forms over time.",
    },
    {
        "name": "Global Public Procurement Database",
        "provider": "World Bank",
        "url": "https://www.worldbank.org/en/topic/governance/brief/global-public-procurement-database",
        "coverage": "Cross-country information on public procurement systems, legal frameworks, institutions and practices.",
        "keywords": ["procurement", "public procurement", "governance", "e-procurement", "central purchasing", "public expenditure", "cross-country"],
        "access_note": "Check the latest release, country coverage and whether variables are comparable across years.",
    },
    {
        "name": "FRED Economic Data",
        "provider": "Federal Reserve Bank of St. Louis",
        "url": "https://fred.stlouisfed.org/",
        "coverage": "Macroeconomic and financial time series from many official national and international providers.",
        "keywords": ["time series", "inflation", "interest rate", "exchange rate", "stock", "finance", "gdp", "unemployment"],
        "access_note": "Open data and API. Cite the original source and record the vintage where revisions matter.",
    },
    {
        "name": "Penn World Table",
        "provider": "Groningen Growth and Development Centre",
        "url": "https://www.rug.nl/ggdc/productivity/pwt/",
        "coverage": "Cross-country national accounts, productivity, capital, labour and purchasing-power-parity measures.",
        "keywords": ["productivity", "gdp", "capital", "labour", "ppp", "growth", "cross-country", "development"],
        "access_note": "Open data. State the version used because historical values may change between releases.",
    },
    {
        "name": "Our World in Data",
        "provider": "Global Change Data Lab",
        "url": "https://ourworldindata.org/",
        "coverage": "Documented, downloadable datasets compiled from official and research sources across social, economic, health and environmental topics.",
        "keywords": ["global", "climate", "energy", "health", "education", "poverty", "inequality", "population", "environment"],
        "access_note": "Use the cited original data provider where possible and inspect the metadata and processing notes.",
    },
]


INSTRUMENT_RESOURCE_CATALOG: list[dict[str, Any]] = [
    {
        "name": "International Personality Item Pool",
        "provider": "Oregon Research Institute",
        "url": "https://ipip.ori.org/",
        "purpose": "Public-domain personality items and scales that can support personality and behavioural construct measurement.",
        "keywords": ["personality", "behaviour", "behavior", "trait", "attitude", "psychology"],
        "permission_note": "Items are generally public domain, but users should still cite the relevant scale documentation and validate the adapted version.",
    },
    {
        "name": "PROMIS measures",
        "provider": "HealthMeasures",
        "url": "https://www.healthmeasures.net/explore-measurement-systems/promis",
        "purpose": "Validated patient-reported measures of physical, mental and social health.",
        "keywords": ["health", "quality of life", "wellbeing", "well-being", "mental", "physical", "patient", "social health"],
        "permission_note": "Check the current terms, language availability, scoring manuals and any administration requirements before use.",
    },
    {
        "name": "NIH Toolbox",
        "provider": "HealthMeasures",
        "url": "https://www.healthmeasures.net/explore-measurement-systems/nih-toolbox",
        "purpose": "Assessment tools for cognition, emotion, motor and sensory functioning.",
        "keywords": ["cognition", "emotion", "motor", "sensory", "health", "function", "psychology"],
        "permission_note": "Review licensing, platform and scoring requirements before adopting any measure.",
    },
    {
        "name": "WHO STEPS Instrument",
        "provider": "World Health Organization",
        "url": "https://www.who.int/teams/noncommunicable-diseases/surveillance/systems-tools/steps/instrument",
        "purpose": "Standardised questionnaire and measurement framework for noncommunicable disease risk-factor surveillance.",
        "keywords": ["health", "risk factor", "ncd", "noncommunicable", "tobacco", "alcohol", "diet", "physical activity"],
        "permission_note": "Use the official instrument and adaptation guidance. Retain core items where comparability is required.",
    },
    {
        "name": "DHS model questionnaires",
        "provider": "The DHS Program",
        "url": "https://dhsprogram.com/methodology/survey-types/dhs-questionnaires.cfm",
        "purpose": "Model household, woman, man and biomarker questionnaires covering demographic and health topics.",
        "keywords": ["household", "demographic", "health", "women", "men", "child", "fertility", "nutrition"],
        "permission_note": "Adopt only relevant modules, document adaptations and preserve validated wording when comparability is needed.",
    },
    {
        "name": "MICS questionnaire and survey tools",
        "provider": "UNICEF",
        "url": "https://mics.unicef.org/tools",
        "purpose": "Standard survey modules and implementation tools for household, women and child indicators.",
        "keywords": ["child", "household", "women", "education", "health", "protection", "water", "sanitation"],
        "permission_note": "Use the current official modules and adaptation instructions. Pilot locally and document deviations.",
    },
    {
        "name": "Afrobarometer questionnaires",
        "provider": "Afrobarometer",
        "url": "https://www.afrobarometer.org/survey-resource/",
        "purpose": "Public-opinion questions on governance, democracy, trust, public services, economy and citizenship in African settings.",
        "keywords": ["africa", "ghana", "governance", "trust", "democracy", "corruption", "public service", "citizen", "opinion"],
        "permission_note": "Cite the survey source, verify wording for the selected round and avoid presenting adapted items as the original validated scale.",
    },
    {
        "name": "World Bank Enterprise Surveys questionnaires",
        "provider": "World Bank",
        "url": "https://www.enterprisesurveys.org/en/methodology",
        "purpose": "Firm-level questionnaire modules on finance, regulation, innovation, corruption, infrastructure and performance.",
        "keywords": ["firm", "enterprise", "business", "sme", "finance", "innovation", "corruption", "productivity", "manager"],
        "permission_note": "Review questionnaire versions and country-specific modules before adapting items.",
    },
    {
        "name": "European Social Survey questionnaires",
        "provider": "European Social Survey",
        "url": "https://www.europeansocialsurvey.org/methodology/ess-methodology/data-collection",
        "purpose": "Cross-national social-attitude, values, trust, wellbeing and institutional-question modules.",
        "keywords": ["attitude", "trust", "wellbeing", "social", "institution", "public opinion", "values"],
        "permission_note": "Check module documentation, translation protocols and country applicability before adaptation.",
    },
    {
        "name": "OECD PISA questionnaires",
        "provider": "OECD",
        "url": "https://www.oecd.org/pisa/data/",
        "purpose": "Student, school, teacher and parent contextual questionnaires linked to learning outcomes.",
        "keywords": ["student", "school", "teacher", "parent", "learning", "education", "achievement", "literacy"],
        "permission_note": "Use official released questionnaires and scaling documentation. Confirm age group and educational context fit.",
    },
]


def _tokenise(text: str) -> set[str]:
    tokens = set()
    lowered = re.sub(r"[^a-z0-9+\- ]+", " ", str(text or "").lower())
    for token in lowered.split():
        token = token.strip("-+")
        if len(token) >= 3 and token not in _STOPWORDS:
            tokens.add(token)
    return tokens


def _haystack(payload: dict[str, Any], extra_text: str = "") -> str:
    fields = [
        "research_area", "article_title", "title", "objective", "objectives", "variables_constructs",
        "variables_or_themes", "methodology", "data_available", "context", "source_mode", "article_type",
        "research_route", "instrument_requirements", "extraction_focus",
    ]
    return " ".join(str(payload.get(key) or "") for key in fields) + " " + str(extra_text or "")


def infer_research_route(payload: dict[str, Any], extra_text: str = "") -> str:
    explicit = str(payload.get("research_route") or "").strip().lower()
    if explicit and explicit not in {"auto", "automatic", "let the app determine"}:
        if "secondary" in explicit or "existing data" in explicit or "dataset" in explicit:
            return "secondary_data"
        if "survey" in explicit or "questionnaire" in explicit:
            return "survey_or_scale"
        if "qualitative" in explicit or "interview" in explicit or "focus group" in explicit:
            return "qualitative_instrument"
        if "mixed" in explicit:
            return "mixed_methods"
        if "review" in explicit or "conceptual" in explicit:
            return "review_or_conceptual"
        if "experiment" in explicit:
            return "experimental_instrument"

    text = _haystack(payload, extra_text).lower()
    if any(term in text for term in ["mixed method", "mixed-method"]):
        return "mixed_methods"
    if any(term in text for term in [
        "secondary data", "existing dataset", "archival", "administrative data", "panel data", "time series",
        "cross-country", "macro data", "financial database", "stock market data", "public records", "documentary data",
    ]):
        return "secondary_data"
    if any(term in text for term in ["survey", "questionnaire", "likert", "scale", "pls-sem", "structural equation", "respondent"]):
        return "survey_or_scale"
    if any(term in text for term in ["interview", "focus group", "qualitative", "thematic analysis", "phenomenology", "grounded theory"]):
        return "qualitative_instrument"
    if any(term in text for term in ["systematic review", "scoping review", "conceptual article", "literature review", "meta-analysis", "meta analysis"]):
        return "review_or_conceptual"
    if any(term in text for term in ["experiment", "randomised", "randomized", "laboratory", "field trial"]):
        return "experimental_instrument"
    if "develop from an existing dataset" in text:
        return "secondary_data"
    return "undetermined"


def _rank_catalog(catalog: list[dict[str, Any]], query_text: str, limit: int) -> list[dict[str, Any]]:
    query_lower = query_text.lower()
    tokens = _tokenise(query_text)
    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for item in catalog:
        matched: list[str] = []
        score = 0.0
        for keyword in item.get("keywords") or []:
            kw = str(keyword).lower()
            if kw in query_lower:
                score += 3.0 if " " in kw else 2.0
                matched.append(keyword)
            elif any(part in tokens for part in kw.split() if len(part) >= 4):
                score += 0.65
        if "ghana" in query_lower and "ghana" in [str(k).lower() for k in item.get("keywords") or []]:
            score += 4.0
        if score > 0:
            scored.append((score, item, matched))
    if not scored:
        # Broad, generally useful fallbacks. They remain labelled as possibilities, not confirmed matches.
        scored = [(0.1, item, []) for item in catalog[: min(limit, 5)]]
    scored.sort(key=lambda entry: entry[0], reverse=True)
    output: list[dict[str, Any]] = []
    for score, item, matched in scored[:limit]:
        record = {k: v for k, v in item.items() if k != "keywords"}
        record["match_score"] = round(score, 2)
        record["matched_terms"] = matched[:6]
        if "coverage" in record:
            record["suitability"] = (
                "Potentially suitable because it covers " + ", ".join(matched[:4]) + "."
                if matched else "A broad data source that may be suitable after checking variable, unit, period and geographic coverage."
            )
        else:
            record["suitability"] = (
                "Potentially suitable for measuring " + ", ".join(matched[:4]) + "."
                if matched else "A possible instrument source. Confirm construct fit, population fit, validity evidence and permission before use."
            )
        output.append(record)
    return output


def _instrument_search_query(payload: dict[str, Any], extra_text: str = "") -> str:
    focus = " ".join(
        str(payload.get(key) or "")
        for key in ["variables_constructs", "variables_or_themes", "research_area", "article_title", "objectives", "context"]
    )
    route = infer_research_route(payload, extra_text)
    if route == "qualitative_instrument":
        suffix = "semi-structured interview guide development qualitative instrument"
    elif route == "experimental_instrument":
        suffix = "experimental manipulation measure validation instrument"
    else:
        suffix = "validated scale questionnaire instrument development validation"
    return re.sub(r"\s+", " ", f"{focus} {extra_text} {suffix}").strip()[:220]


def _instrument_like(source: dict[str, Any]) -> bool:
    text = " ".join(str(source.get(key) or "") for key in ["title", "abstract", "source"]).lower()
    return any(term in text for term in [
        "scale", "questionnaire", "instrument", "measure", "measurement", "validation", "validity", "reliability",
        "interview guide", "survey", "inventory", "index", "assessment",
    ])


def _scholarly_instrument_candidates(payload: dict[str, Any], extra_text: str, max_results: int) -> tuple[list[dict[str, Any]], list[Any]]:
    if search_literature_sources is None:
        return [], ["Scholarly instrument search is unavailable."]
    profile = {
        "title": str(payload.get("article_title") or payload.get("title") or payload.get("research_area") or ""),
        "research_area": str(payload.get("research_area") or ""),
        "study_context": str(payload.get("context") or ""),
        "objectives": [str(payload.get("objectives") or payload.get("objective") or "")],
        "level": "Journal article",
        "research_approach": str(payload.get("methodology") or ""),
        "data_type": str(payload.get("article_type") or ""),
        "notes": str(payload.get("variables_constructs") or payload.get("variables_or_themes") or ""),
    }
    try:
        result = search_literature_sources(
            profile=profile,
            query=_instrument_search_query(payload, extra_text),
            max_results=max(6, min(max_results * 2, 20)),
            include_older_foundational=True,
        )
    except Exception as exc:
        return [], [f"Instrument source search failed: {str(exc)[:180]}"]
    candidates: list[dict[str, Any]] = []
    for src in result.get("sources") or []:
        if not isinstance(src, dict) or not _instrument_like(src):
            continue
        candidates.append({
            "name": src.get("title") or "Untitled instrument source",
            "provider": src.get("source") or src.get("database") or "Scholarly source",
            "url": src.get("url") or (f"https://doi.org/{src.get('doi')}" if src.get("doi") else ""),
            "year": src.get("year"),
            "authors": src.get("authors") or [],
            "doi": src.get("doi") or "",
            "purpose": "A scholarly publication that may contain, validate or discuss a relevant scale, measure, questionnaire or data-collection instrument.",
            "suitability": "Inspect the full text to confirm that the actual instrument, items, scoring, population and validation evidence match the proposed study.",
            "permission_note": "Do not reproduce proprietary items without permission. Cite the original instrument source and document any adaptation and revalidation.",
            "source_record": src,
        })
        if len(candidates) >= max_results:
            break
    return candidates, result.get("provider_errors") or []


def discover_research_resources(
    payload: dict[str, Any],
    *,
    extra_text: str = "",
    max_results: int = 6,
    include_live_search: bool = True,
) -> dict[str, Any]:
    max_results = max(3, min(int(max_results or 6), 12))
    query_text = _haystack(payload, extra_text)
    route = infer_research_route(payload, extra_text)

    show_data = route in {"secondary_data", "mixed_methods", "undetermined"}
    show_instruments = route in {
        "survey_or_scale", "qualitative_instrument", "experimental_instrument", "mixed_methods", "undetermined"
    }

    data_sources = _rank_catalog(DATA_SOURCE_CATALOG, query_text, max_results) if show_data else []
    instrument_sources = _rank_catalog(INSTRUMENT_RESOURCE_CATALOG, query_text, max_results) if show_instruments else []
    scholarly_candidates: list[dict[str, Any]] = []
    provider_errors: list[Any] = []
    if show_instruments and include_live_search:
        scholarly_candidates, provider_errors = _scholarly_instrument_candidates(payload, extra_text, max_results)

    combined_instruments = instrument_sources + scholarly_candidates
    # Deduplicate by URL/name while preserving curated resources before publication candidates.
    seen: set[str] = set()
    deduped_instruments: list[dict[str, Any]] = []
    for item in combined_instruments:
        key = str(item.get("url") or item.get("name") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped_instruments.append(item)
        if len(deduped_instruments) >= max_results:
            break

    route_labels = {
        "secondary_data": "Secondary or archival research",
        "survey_or_scale": "Primary survey or scale-based research",
        "qualitative_instrument": "Qualitative interview or focus-group research",
        "experimental_instrument": "Experimental research",
        "mixed_methods": "Mixed-methods research",
        "review_or_conceptual": "Review or conceptual research",
        "undetermined": "Research route not yet determined",
    }
    return {
        "research_route": route,
        "research_route_label": route_labels.get(route, route.replace("_", " ").title()),
        "data_sources": data_sources,
        "instrument_sources": deduped_instruments,
        "provider_errors": provider_errors,
        "search_note": (
            "These are candidate resources, not automatic endorsements. Confirm variable coverage, population fit, period, unit of analysis, access conditions, ethics, licensing and citation requirements before adoption."
        ),
        "instrument_adaptation_rules": [
            "Prefer the original instrument publication and the most relevant validation study for the intended population.",
            "Check copyright or licensing before reproducing items. Do not assume that a published scale is free to use.",
            "Document translation, cultural adaptation, expert review, pilot testing and revalidation.",
            "Do not change item wording, response anchors or scoring without explaining and validating the change.",
            "Use a new provisional instrument only when no suitable validated measure exists, and subject it to content, construct and reliability assessment.",
        ],
        "data_source_checks": [
            "Confirm that the dataset contains the required variables at the correct unit of analysis.",
            "Check geographic, sectoral and time coverage, missingness, revisions and comparability.",
            "Review access terms, citation requirements and any restrictions on redistribution.",
            "Record dataset version, extraction date, transformations and merge keys.",
        ],
    }


def resources_for_idea(idea: dict[str, Any], aggregate: dict[str, Any], limit: int = 5) -> dict[str, Any]:
    idea_text = " ".join(
        str(idea.get(key) or "")
        for key in ["title", "objective", "method_and_data_route", "angle", "keywords"]
    )
    route = infer_research_route({"research_route": idea.get("research_route") or ""}, idea_text)
    if route == "undetermined":
        route = str(aggregate.get("research_route") or "undetermined")
    data_sources = aggregate.get("data_sources") or []
    instrument_sources = aggregate.get("instrument_sources") or []
    if route == "secondary_data":
        instrument_sources = []
    elif route in {"survey_or_scale", "qualitative_instrument", "experimental_instrument"}:
        data_sources = []
    elif route == "review_or_conceptual":
        data_sources = []
        instrument_sources = []
    return {
        "research_route": route,
        "research_route_label": route.replace("_", " ").title(),
        "possible_data_sources": data_sources[:limit],
        "possible_instruments": instrument_sources[:limit],
        "guidance_note": aggregate.get("search_note") or "Verify every proposed research resource before use.",
    }
