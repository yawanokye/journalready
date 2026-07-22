from __future__ import annotations

import re
from datetime import datetime
from typing import Any


_REVIEW_TERMS = (
    "systematic",
    "scoping",
    "review",
    "conceptual",
    "theory",
    "integrative",
    "bibliometric",
    "scientometric",
)


def is_review_evidence_article(article_type: str) -> bool:
    value = str(article_type or "").strip().lower()
    return any(term in value for term in _REVIEW_TERMS)


def review_evidence_kind(article_type: str) -> str:
    value = str(article_type or "").strip().lower()
    if "bibliometric" in value or "scientometric" in value:
        return "bibliometric"
    if "systematic" in value or "meta-analysis" in value or "meta analysis" in value:
        return "systematic"
    if "scoping" in value:
        return "scoping"
    if "conceptual" in value or "theory" in value:
        return "conceptual"
    return "integrative"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _multiline(value: Any) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(value or "").splitlines()]
    return "\n".join(line for line in lines if line)


def _action(message: str) -> str:
    text = _clean(message).rstrip(".")
    return f"[Author action: {text}.]"


def _format_date(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%d %B %Y")
    except Exception:
        return text


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = _multiline(value)
        if text:
            return text
    return ""


def _count(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None or value == "":
        return None
    try:
        return max(0, int(value))
    except Exception:
        return None


def _positioning(payload: dict[str, Any], kind: str) -> str:
    supplied = _clean(payload.get("review_protocol_positioning"))
    if supplied and supplied.lower() != "auto":
        return supplied
    return {
        "systematic": "Systematic review protocol",
        "scoping": "Scoping review protocol",
        "bibliometric": "Bibliometric search and analysis protocol",
        "conceptual": "Structured conceptual evidence base",
        "integrative": "Integrative review protocol",
    }[kind]


def _design_statement(kind: str) -> str:
    if kind == "systematic":
        return (
            "The article is positioned as a systematic review. Reproducible database searching, explicit eligibility criteria, "
            "documented screening, an appraisal decision and a traceable synthesis are therefore required."
        )
    if kind == "scoping":
        return (
            "The article is positioned as a scoping review. The method should transparently map the breadth, characteristics, "
            "concepts and gaps of the evidence base without implying effect estimation unless such analysis is actually performed."
        )
    if kind == "bibliometric":
        return (
            "The article is positioned as a bibliometric study. The database export, query, cleaning rules, final corpus, software, "
            "thresholds, normalisation and network interpretation must be reproducible."
        )
    if kind == "conceptual":
        return (
            "The article is positioned as an integrative, theory-building conceptual synthesis. It should not be labelled a systematic "
            "review unless the recorded search, screening and appraisal procedures genuinely satisfy that standard."
        )
    return (
        "The article is positioned as an integrative review. The search and selection process should be transparent enough to show "
        "how the evidence base supports the synthesis, while avoiding claims of systematic exhaustiveness unless justified."
    )


def _search_log(search_result: dict[str, Any], source_count: int) -> list[str]:
    databases = search_result.get("databases") or []
    query = _clean(search_result.get("query"))
    searched_at = _format_date(search_result.get("searched_at"))
    lines: list[str] = []
    if databases or query or searched_at or source_count:
        lines.append(
            "The ArticleReady discovery search used open scholarly metadata services only. It supports source discovery and drafting, "
            "but it does not by itself establish a formal systematic-review search or PRISMA record flow."
        )
        if databases:
            lines.append(f"- Metadata services queried: {', '.join(str(item) for item in databases)}")
        if query:
            lines.append(f"- Exact ArticleReady metadata query: `{query}`")
        if searched_at:
            lines.append(f"- Metadata search date: {searched_at}")
        if source_count:
            lines.append(f"- Deduplicated records available to the drafting source bank: {source_count}")
        quality = search_result.get("quality_filters") or []
        if quality:
            lines.append(f"- Automated metadata filters: {'; '.join(str(item) for item in quality)}")
    return lines


def _flow_counts(payload: dict[str, Any]) -> dict[str, int | None]:
    return {
        "identified": _count(payload, "review_records_identified"),
        "duplicates": _count(payload, "review_duplicates_removed"),
        "screened": _count(payload, "review_records_screened"),
        "excluded": _count(payload, "review_records_excluded"),
        "full_text": _count(payload, "review_full_text_assessed"),
        "full_text_excluded": _count(payload, "review_full_text_excluded"),
        "additions": _count(payload, "review_citation_tracking_additions"),
        "final": _count(payload, "review_final_corpus_size"),
    }


def _flow_audit(counts: dict[str, int | None]) -> list[str]:
    warnings: list[str] = []
    identified = counts["identified"]
    duplicates = counts["duplicates"]
    screened = counts["screened"]
    excluded = counts["excluded"]
    full_text = counts["full_text"]
    full_text_excluded = counts["full_text_excluded"]
    additions = counts["additions"] or 0
    final = counts["final"]

    if identified is not None and duplicates is not None and duplicates > identified:
        warnings.append("Duplicate-removal count exceeds the number of records identified")
    if identified is not None and screened is not None and screened > identified:
        warnings.append("Screened-record count exceeds the number of records identified")
    if screened is not None and excluded is not None and excluded > screened:
        warnings.append("Title-and-abstract exclusions exceed the number of records screened")
    if screened is not None and full_text is not None and full_text > screened:
        warnings.append("Full-text assessments exceed the number of records screened")
    if full_text is not None and full_text_excluded is not None and full_text_excluded > full_text:
        warnings.append("Full-text exclusions exceed the number of full texts assessed")
    if identified is not None and duplicates is not None and screened is not None:
        expected = identified - duplicates
        if expected != screened:
            warnings.append(
                f"Records screened ({screened}) do not equal identified records minus duplicates ({expected})"
            )
    if full_text is not None and full_text_excluded is not None and final is not None:
        expected = full_text - full_text_excluded + additions
        if expected != final:
            warnings.append(
                f"Final corpus ({final}) does not equal full texts assessed minus full-text exclusions plus citation-tracking additions ({expected})"
            )
    return warnings


def _theme_rows(payload: dict[str, Any]) -> list[str]:
    raw = _first_nonempty(payload.get("variables_constructs"), payload.get("key_findings"))
    if not raw:
        return [
            "| [Author action: Name a principal theme or construct.] | [Author action: List the included studies.] | [Author action: Summarise contexts and methods.] | [Author action: State the supported mechanism or argument.] | [Author action: Record contradictions, limits and gaps.] |"
        ]
    pieces = [
        re.sub(r"^[\d.()\-•\s]+", "", item).strip()
        for item in re.split(r"\n|;|,(?=\s*[A-Za-z][A-Za-z\- ]{2,40}(?:,|$))", raw)
    ]
    pieces = [item for item in pieces if 2 < len(item) < 120][:8]
    if not pieces:
        pieces = [raw[:100]]
    rows = []
    for theme in pieces:
        rows.append(
            f"| {theme} | [Author action: List the verified included studies supporting this theme.] | "
            "[Author action: Summarise the relevant settings and designs.] | "
            "[Author action: State the evidence-based mechanism, pattern or conceptual role.] | "
            "[Author action: Record contradictions, boundary conditions and unresolved gaps.] |"
        )
    return rows


def build_review_protocol_documentation(
    payload: dict[str, Any],
    search_result: dict[str, Any] | None,
    source_records: list[dict[str, Any]] | None,
) -> tuple[str, dict[str, Any]]:
    """Build a non-fabricating review-method and evidence-audit package.

    User-entered formal search and screening information is treated as confirmed input.
    ArticleReady metadata discovery is reported separately and is never converted into
    formal database counts, PRISMA counts or an included-study corpus.
    """
    article_type = _clean(payload.get("article_type"))
    if not is_review_evidence_article(article_type) or not bool(payload.get("include_review_protocol_package", True)):
        return "", {"enabled": False, "complete": False, "missing_items": [], "flow_warnings": []}

    kind = review_evidence_kind(article_type)
    search_result = search_result if isinstance(search_result, dict) else {}
    source_records = [item for item in (source_records or []) if isinstance(item, dict)]
    missing: list[str] = []

    def supplied_or_action(value: Any, instruction: str) -> str:
        text = _multiline(value)
        if text:
            return text
        missing.append(instruction)
        return _action(instruction)

    positioning = _positioning(payload, kind)
    databases = supplied_or_action(
        payload.get("review_databases"),
        "List every formal database or platform searched and distinguish database coverage from publisher websites or supplementary discovery tools",
    )
    search_strings = supplied_or_action(
        payload.get("review_search_strings"),
        "Insert the complete reproducible search string for each formal database, preserving field codes, Boolean operators, truncation and proximity commands",
    )
    search_date = supplied_or_action(
        payload.get("review_search_date"),
        "Confirm the final date on which each formal search was executed",
    )
    date_limits = supplied_or_action(
        payload.get("review_date_limits"),
        "State and justify the publication-date limits or confirm that no date restriction was applied",
    )
    language_limits = supplied_or_action(
        payload.get("review_language_limits"),
        "State and justify the language limits or confirm that no language restriction was applied",
    )
    document_types = supplied_or_action(
        payload.get("review_document_types"),
        "State the eligible document and publication types",
    )
    eligibility = supplied_or_action(
        payload.get("review_eligibility_criteria"),
        "Provide operational inclusion and exclusion criteria covering topic, setting, population or unit, evidence type and publication status",
    )
    screening = supplied_or_action(
        payload.get("review_screening_process"),
        "Document title-and-abstract screening, full-text assessment, reviewer roles, disagreement resolution and reasons for full-text exclusion",
    )
    appraisal = supplied_or_action(
        payload.get("review_quality_appraisal"),
        "State the quality-appraisal or critical-evaluation approach, or justify why formal appraisal is not appropriate for this review design",
    )
    citation_tracking = supplied_or_action(
        payload.get("review_citation_tracking"),
        "Document backward and forward citation tracking, the platform used, the stopping rule and how additions entered screening",
    )
    duplicate_removal = supplied_or_action(
        payload.get("review_duplicate_removal"),
        "Document the software, matching fields, normalisation rules and manual checks used to remove duplicates",
    )
    synthesis = supplied_or_action(
        payload.get("review_synthesis_method"),
        "Explain the extraction, coding, comparison and synthesis procedure used to move from included records to themes, mechanisms, propositions or bibliometric structures",
    )
    software = supplied_or_action(
        payload.get("review_software"),
        "Identify the reference-management, screening, qualitative-coding, statistical or bibliometric software and record the relevant version and settings",
    )

    counts = _flow_counts(payload)
    count_labels = [
        ("Records identified through formal database searching", counts["identified"]),
        ("Duplicates removed", counts["duplicates"]),
        ("Records screened by title and abstract", counts["screened"]),
        ("Records excluded at title and abstract stage", counts["excluded"]),
        ("Full-text records assessed", counts["full_text"]),
        ("Full-text records excluded", counts["full_text_excluded"]),
        ("Backward or forward citation additions", counts["additions"]),
        ("Final conceptual or review corpus", counts["final"]),
    ]
    flow_warnings = _flow_audit(counts)
    if not any(value is not None for _, value in count_labels):
        missing.append("Enter the verified record-flow counts and final corpus size")

    lines = [
        "# Review Protocol and Evidence Audit",
        "",
        "## 1. Review positioning",
        "",
        f"**Selected positioning:** {positioning}",
        "",
        _design_statement(kind),
        "",
        "The documentation below separates formal review procedures from ArticleReady's metadata-discovery support. Only procedures actually performed and counts taken from the screening record should be reported as completed methodology.",
        "",
        "## 2. Search strategy and execution",
        "",
        "### Formal databases and platforms",
        "",
        databases,
        "",
        "### Complete search strings",
        "",
        search_strings,
        "",
        "### Search date and limits",
        "",
        f"- Search date: {search_date}",
        f"- Date limits: {date_limits}",
        f"- Language limits: {language_limits}",
        f"- Eligible document types: {document_types}",
        "",
    ]

    discovery_log = _search_log(search_result, len(source_records))
    if discovery_log:
        lines.extend(["### ArticleReady metadata-discovery log", "", *discovery_log, ""])

    lines.extend([
        "## 3. Eligibility, screening and appraisal",
        "",
        "### Eligibility criteria",
        "",
        eligibility,
        "",
        "### Screening process",
        "",
        screening,
        "",
        "### Quality appraisal or critical evaluation",
        "",
        appraisal,
        "",
        "## 4. Citation tracking and duplicate removal",
        "",
        "### Backward and forward citation procedures",
        "",
        citation_tracking,
        "",
        "### Duplicate-removal procedure",
        "",
        duplicate_removal,
        "",
        "## 5. Record flow and final corpus",
        "",
        "| Review-flow stage | Verified count |",
        "|---|---:|",
    ])
    for label, value in count_labels:
        lines.append(f"| {label} | {value if value is not None else _action('Insert the verified count for this stage')} |")

    if flow_warnings:
        lines.extend(["", "### Record-flow consistency checks", ""])
        lines.extend(f"- {_action(warning + ' and correct the screening log or the reported count')}" for warning in flow_warnings)

    lines.extend([
        "",
        "## 6. Synthesis and analytical procedure",
        "",
        synthesis,
        "",
        f"**Software and reproducibility tools:** {software}",
        "",
        "## 7. Conceptual or evidence matrix",
        "",
        "| Theme, construct or cluster | Included studies | Contexts and methods | Evidence-based role or finding | Contradictions, limits and gaps |",
        "|---|---|---|---|---|",
        *_theme_rows(payload),
        "",
        "## 8. Audit trail and reproducibility",
        "",
        "Retain the database exports, complete search strings, dated search log, deduplication file, screening decisions, reasons for exclusion, appraisal records, extraction matrix, coding framework, analysis files and the final included-record list. Do not replace these records with reconstructed counts after drafting.",
    ])

    notes = _multiline(payload.get("review_protocol_notes"))
    if notes:
        lines.extend(["", "### Additional protocol notes", "", notes])

    lines.extend(["", "## Completion audit", ""])
    if missing:
        lines.extend(f"- {_action(item)}" for item in missing)
    if not missing and not flow_warnings:
        lines.append("- All core protocol fields were supplied. Verify them against the retained search and screening files before submission.")

    audit = {
        "enabled": True,
        "kind": kind,
        "positioning": positioning,
        "complete": not missing and not flow_warnings,
        "missing_items": missing,
        "flow_counts": counts,
        "flow_warnings": flow_warnings,
        "metadata_discovery_databases": search_result.get("databases") or [],
        "metadata_discovery_query": _clean(search_result.get("query")),
        "source_bank_count": len(source_records),
    }
    return "\n".join(lines).strip(), audit
