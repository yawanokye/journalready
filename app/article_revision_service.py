from __future__ import annotations

import difflib
import io
import json
import os
import re
from datetime import datetime
from typing import Any

from app.article_service import (
    _article_reference_expectations,
    _finalise_article_text,
    _safe_get_openai_client,
    _search_sources,
    _source_context,
)

_REVISION_BLUE = (0, 112, 192)


def _revision_model() -> str:
    return (
        os.getenv("OPENAI_ARTICLE_REVISION_MODEL")
        or os.getenv("OPENAI_ARTICLE_DOCTORAL_MODEL")
        or os.getenv("OPENAI_ARTICLE_RESEARCH_MODEL")
        or "gpt-5.5"
    ).strip()


def _extract_response_text(response: Any) -> str:
    return str(getattr(response, "output_text", "") or "").strip()


def _strip_code_fences(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()


def _split_revision_package(text: str) -> tuple[str, str, str]:
    raw = _strip_code_fences(text)
    revised_marker = "===REVISED_ARTICLE==="
    report_marker = "===REVISION_REPORT==="
    matrix_marker = "===REVIEWER_RESPONSE_MATRIX==="

    if revised_marker in raw:
        raw = raw.split(revised_marker, 1)[1]
    matrix = ""
    if matrix_marker in raw:
        raw, matrix = raw.split(matrix_marker, 1)
    report = ""
    if report_marker in raw:
        revised, report = raw.split(report_marker, 1)
    else:
        revised = raw
    return revised.strip(), report.strip(), matrix.strip()


def _revision_focus(payload: dict[str, Any]) -> list[str]:
    focus_map = [
        ("strengthen_conceptualisation", "conceptualisation, theoretical framing and the logic connecting the constructs or phenomena"),
        ("strengthen_contribution", "theoretical, empirical, methodological, contextual and practical contribution"),
        ("assess_method_fit", "alignment among the problem, objectives, design, sampling, measurement, identification and validity strategy"),
        ("assess_analysis", "appropriateness, assumptions, robustness and reporting of the analysis"),
        ("deepen_discussion", "interpretive depth, comparison with literature, boundary conditions, alternative explanations and limitations"),
        ("strengthen_recommendations", "evidence-linked implications and feasible recommendations for named actors"),
    ]
    return [description for key, description in focus_map if bool(payload.get(key, True))]


def _fallback_revision_report(payload: dict[str, Any], source_records: list[dict[str, Any]], provider_errors: list[str]) -> str:
    comments = str(payload.get("review_comments") or "").strip()
    source_note = (
        f"{len(source_records)} scholarly record(s) were available for relevance screening, but no sources were inserted automatically in fallback mode."
        if source_records
        else "No scholarly records were available for source-supported revision."
    )
    errors = "\n".join(f"- {item}" for item in provider_errors) or "- The AI revision service was unavailable."
    reviewer_note = (
        "Reviewer comments were supplied, but they were not substantively resolved because the AI revision service was unavailable."
        if comments
        else "No reviewer comments were supplied."
    )
    return f"""# Revision and Publishability Report

## Revision Status

The original article has been returned without substantive rewriting because the revision model was unavailable. Do not treat this fallback as a completed publication-readiness revision.

## Provider or Processing Notes

{errors}

## Priority Review Areas

1. Clarify the article-level problem and the precise conceptual or theoretical gap.
2. State the central contribution in a way that distinguishes it from contextual novelty alone.
3. Confirm that the research design, sampling, measures and analysis directly answer the stated objectives.
4. Check whether robustness, diagnostic, endogeneity, sensitivity, validity or trustworthiness procedures are needed.
5. Rebuild the Discussion around the main findings, mechanisms, competing explanations, boundaries and contribution.
6. Ensure recommendations follow directly from confirmed findings and name the responsible actors.

## Additional Analysis

[review the supplied method and results to determine whether additional analysis is essential, strongly recommended or optional. Do not report any analysis as completed until actual output is supplied]

## Reviewer Comments

{reviewer_note}

## Source Review

{source_note}
""".strip()


def _fallback_reviewer_matrix(review_comments: str) -> str:
    comments = [line.strip(" -\t") for line in str(review_comments or "").splitlines() if line.strip()]
    if not comments:
        return ""
    rows = ["| Reviewer comment | Revision made | Location | Remaining action |", "|---|---|---|---|"]
    for comment in comments[:30]:
        safe = comment.replace("|", "/")
        rows.append(f"| {safe} | [substantive revision not completed in fallback mode] | [identify section] | [action required] |")
    return "\n".join(rows)


def revise_article(payload: dict[str, Any]) -> dict[str, Any]:
    article_text = _finalise_article_text(str(payload.get("article_text") or ""))
    if len(article_text) < 100:
        raise ValueError("Paste or upload the existing article before requesting revision.")

    payload = dict(payload)
    payload["article_text"] = article_text
    payload["academic_level"] = str(payload.get("academic_level") or "PhD")
    payload["source_thesis_title"] = ""
    payload["thesis_source_material"] = ""
    payload["objectives"] = str(payload.get("revision_goals") or "")
    payload["theory_or_framework"] = str(payload.get("contribution_claim") or "")
    payload["key_findings"] = str(payload.get("data_and_results") or "")
    payload["variables_constructs"] = str(payload.get("research_area") or "")

    sources, blocked, search_result = _search_sources(payload)
    source_records = _source_context(sources)[:40]
    provider_errors = list(search_result.get("provider_errors") or [])
    model = _revision_model()
    client = _safe_get_openai_client()

    if not client or os.getenv("ARTICLEREADY_REVISION_USE_AI", "1").strip().lower() in {"0", "false", "no"}:
        revised_article = article_text
        revision_report = _fallback_revision_report(payload, source_records, provider_errors)
        reviewer_matrix = _fallback_reviewer_matrix(str(payload.get("review_comments") or ""))
        mode = "metadata_fallback"
    else:
        current_year = datetime.now().year
        article_inputs = {
            "article_title": str(payload.get("article_title") or "").strip(),
            "article_type": str(payload.get("article_type") or "Empirical research article").strip(),
            "research_area": str(payload.get("research_area") or "").strip(),
            "context": str(payload.get("context") or "").strip(),
            "target_journal": str(payload.get("target_journal") or "").strip(),
            "journal_scope": str(payload.get("journal_scope") or "").strip(),
            "author_guidelines": str(payload.get("author_guidelines") or "").strip(),
            "citation_style": str(payload.get("citation_style") or "APA 7th").strip(),
            "word_limit": str(payload.get("word_limit") or "").strip(),
            "methodology_declared_by_author": str(payload.get("methodology") or "").strip(),
            "confirmed_data_results_or_analysis": str(payload.get("data_and_results") or "").strip(),
            "current_contribution_claim": str(payload.get("contribution_claim") or "").strip(),
            "revision_level": str(payload.get("revision_level") or "Publication-readiness overhaul").strip(),
            "additional_revision_goals": str(payload.get("revision_goals") or "").strip(),
            "reviewer_comments": str(payload.get("review_comments") or "").strip(),
            "existing_article": article_text,
        }
        prompt = {
            "task": "Substantively revise and polish an existing journal article into a stronger, publication-focused manuscript, then provide a transparent publishability report.",
            "current_year": current_year,
            "article_inputs": article_inputs,
            "revision_focus": _revision_focus(payload),
            "scholarly_source_records": source_records,
            "reference_depth_guidance": _article_reference_expectations(str(payload.get("article_type") or "")),
            "strict_revision_rules": [
                "Preserve all confirmed facts, sample details, coefficients, p-values, quotations, table values, dates and study results unless the user supplied evidence that they are wrong.",
                "Do not invent, estimate or silently alter results, data, respondent details, ethics approvals, permissions, citations, references, tables or figures.",
                "Do not report a suggested analysis as though it has been conducted. Insert a concise bracketed action marker in the manuscript only where the missing analysis prevents a defensible claim.",
                "Use the supplied article as the evidential base. Improve coherence, argument, section alignment, academic expression and publication focus without changing the study into a different project.",
                "Strengthen conceptualisation by clarifying the phenomenon, theoretical lens, construct definitions, expected relationships, mechanisms and boundary conditions where the evidence supports them.",
                "State the contribution precisely. Distinguish theoretical, empirical, methodological, contextual and practical contributions, and remove unsupported novelty claims.",
                "Assess whether the design and methods fit the questions, objectives and claims. Check sampling, measurement, construct validity, identification, endogeneity, common method bias, trustworthiness, reproducibility and ethics only where relevant.",
                "Assess analysis appropriateness and reporting. Consider diagnostics, robustness, sensitivity, alternative specifications, mediation, moderation, heterogeneity, endogeneity correction, predictive checks, qualitative saturation or triangulation only when suitable for the design.",
                "Build the Discussion around the confirmed findings. Explain mechanisms and context, compare with relevant literature, acknowledge conflicting evidence, state boundary conditions and avoid causal language when the design supports only association.",
                "Recommendations must follow directly from confirmed findings, identify responsible actors, recognise implementation constraints and avoid generic statements.",
                "Use target-journal scope and author guidance when supplied. Respect the stated word limit and citation style.",
                "Apply a strict relevance gate to scholarly records. Use only records that directly support the article. Never invent bibliographic details or cite a metadata record as evidence for a finding not visible in its title or abstract.",
                "Retain existing valid citations. Do not remove a citation merely because its full record was not supplied, but flag obviously incomplete or unverifiable references in the report.",
                "Address every reviewer comment where possible. When a comment cannot be resolved from supplied evidence, state the precise action or analysis needed rather than pretending it was completed.",
                "Write in polished formal British English with natural academic rhythm. Avoid template-like filler, inflated claims, repetitive transitions and mechanical author-by-author summaries.",
            ],
            "revision_report_requirements": [
                "Begin with an overall publication-readiness assessment that does not guarantee acceptance.",
                "List the most important revisions made by section.",
                "Evaluate conceptualisation and theoretical positioning.",
                "Evaluate the clarity and defensibility of the contribution.",
                "Evaluate method fit and reporting completeness.",
                "Evaluate whether the analysis is adequate for the claims.",
                "List additional analyses under Essential, Strongly recommended and Optional. For each, give the rationale, data required, suitable method, output to report and consequence of omission.",
                "Evaluate the Results-Discussion alignment, implications, limitations and recommendations.",
                "Identify remaining author actions, missing evidence and reference-verification needs.",
                "Do not state that the article is publishable merely because the prose has been revised.",
            ],
            "output_format": [
                "Return plain Markdown and use the exact markers below.",
                "Start with ===REVISED_ARTICLE=== followed by the complete revised article.",
                "Then add ===REVISION_REPORT=== followed by the Revision and Publishability Report.",
                "When reviewer comments were supplied and include_reviewer_response_matrix is true, add ===REVIEWER_RESPONSE_MATRIX=== followed by a Markdown table with columns Reviewer comment, Revision made, Location and Remaining action.",
                "Do not wrap the response in code fences.",
            ],
            "include_reviewer_response_matrix": bool(payload.get("include_reviewer_response_matrix", True)),
        }
        try:
            response = client.responses.create(
                model=model,
                instructions=(
                    "You are ArticleReady AI's senior journal article revision editor. Revise rigorously but preserve the study's confirmed evidence. "
                    "Never invent analysis or results. Clearly separate manuscript revision from recommendations for further analysis."
                ),
                input=json.dumps(prompt, ensure_ascii=False, indent=2),
            )
            raw = _extract_response_text(response)
            revised_article, revision_report, reviewer_matrix = _split_revision_package(raw)
            if not revised_article:
                revised_article = article_text
            if not revision_report:
                revision_report = _fallback_revision_report(payload, source_records, ["The revision model returned no separate report."])
            if payload.get("review_comments") and payload.get("include_reviewer_response_matrix", True) and not reviewer_matrix:
                reviewer_matrix = _fallback_reviewer_matrix(str(payload.get("review_comments") or ""))
            mode = "ai_revision"
        except Exception as exc:
            provider_errors.append(f"OpenAI article revision failed: {str(exc)[:220]}")
            revised_article = article_text
            revision_report = _fallback_revision_report(payload, source_records, provider_errors)
            reviewer_matrix = _fallback_reviewer_matrix(str(payload.get("review_comments") or ""))
            mode = "metadata_fallback_after_ai_error"

    revised_article = _finalise_article_text(revised_article)
    revision_report = _finalise_article_text(revision_report)
    reviewer_matrix = _finalise_article_text(reviewer_matrix) if reviewer_matrix else ""

    return {
        "revised_article_text": revised_article,
        "revision_report": revision_report,
        "reviewer_response_matrix": reviewer_matrix,
        "model_used": model if client else "none",
        "mode": mode,
        "source_records_used": source_records,
        "source_bank_count": len(source_records),
        "excluded_retracted_count": len(blocked),
        "excluded_retracted_titles": [str(item.get("title") or "Untitled") for item in blocked[:10]],
        "provider_errors": provider_errors,
        "revision_colour_note": "In the downloaded DOCX, wording added or changed by ArticleReady AI is shown in blue. Exact unchanged wording remains black.",
        "quality_filters": [
            "Confirmed results and numerical evidence are preserved unless the author supplies a correction.",
            "Suggested additional analyses are not presented as completed analyses.",
            "Reviewer comments are addressed through a transparent response matrix when supplied.",
            "Scholarly records are subject to a relevance gate and retraction screening.",
            "The revision report does not guarantee journal acceptance.",
        ],
    }


def _plain_compare_text(text: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", text.strip())
    text = re.sub(r"^[-*•]\s+", "", text)
    text = re.sub(r"^\d+[.)]\s+", "", text)
    text = text.replace("**", "").replace("*", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _tokenise_for_diff(text: str) -> list[str]:
    return re.findall(r"\s+|[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*|[^\w\s]", text, flags=re.UNICODE)


def _word_key(token: str) -> str:
    if token.isspace():
        return token
    return token.lower()


def _best_original_line(revised_line: str, original_lines: list[str], used: set[int]) -> tuple[str | None, float, int | None]:
    revised_norm = _plain_compare_text(revised_line)
    if not revised_norm:
        return None, 0.0, None
    best_line = None
    best_score = 0.0
    best_index = None
    for index, candidate in enumerate(original_lines):
        if index in used:
            continue
        candidate_norm = _plain_compare_text(candidate)
        if not candidate_norm:
            continue
        score = difflib.SequenceMatcher(None, candidate_norm, revised_norm, autojunk=False).ratio()
        if score > best_score:
            best_score = score
            best_line = candidate
            best_index = index
    return best_line, best_score, best_index


def _append_marked_run(paragraph, text: str, changed: bool, bold: bool = False, italic: bool = False) -> None:
    if not text:
        return
    from docx.shared import RGBColor

    run = paragraph.add_run(text)
    run.bold = bold
    run.italic = italic
    if changed:
        run.font.color.rgb = RGBColor(*_REVISION_BLUE)


def _add_diff_runs(paragraph, revised_text: str, original_text: str | None, changed_default: bool = True) -> None:
    """Write revised text and colour inserted/replaced tokens blue while exact retained tokens remain black."""
    if not original_text:
        _append_marked_run(paragraph, revised_text, True)
        return

    revised_tokens = _tokenise_for_diff(revised_text)
    original_tokens = _tokenise_for_diff(original_text)
    matcher = difflib.SequenceMatcher(
        None,
        [_word_key(token) for token in original_tokens],
        [_word_key(token) for token in revised_tokens],
        autojunk=False,
    )
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        changed = tag != "equal"
        chunk = "".join(revised_tokens[j1:j2])
        _append_marked_run(paragraph, chunk, changed if chunk else changed_default)


def _add_black_inline_runs(paragraph, text: str) -> None:
    position = 0
    token_re = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*)")
    for match in token_re.finditer(text):
        if match.start() > position:
            paragraph.add_run(text[position:match.start()])
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        else:
            run = paragraph.add_run(token[1:-1])
            run.italic = True
        position = match.end()
    if position < len(text):
        paragraph.add_run(text[position:])


def _revision_line_map(original_text: str, revised_lines: list[str]) -> dict[int, str | None]:
    original_lines = [line.rstrip() for line in _finalise_article_text(original_text).splitlines() if line.strip()]
    used: set[int] = set()
    mapping: dict[int, str | None] = {}
    exact_lookup: dict[str, list[int]] = {}
    for index, line in enumerate(original_lines):
        exact_lookup.setdefault(_plain_compare_text(line), []).append(index)

    for revised_index, line in enumerate(revised_lines):
        norm = _plain_compare_text(line)
        exact_candidates = exact_lookup.get(norm, [])
        exact_index = next((idx for idx in exact_candidates if idx not in used), None)
        if exact_index is not None:
            used.add(exact_index)
            mapping[revised_index] = original_lines[exact_index]
            continue
        candidate, score, candidate_index = _best_original_line(line, original_lines, used)
        if candidate is not None and score >= 0.36 and candidate_index is not None:
            used.add(candidate_index)
            mapping[revised_index] = candidate
        else:
            mapping[revised_index] = None
    return mapping


def _add_revision_table(doc, lines: list[str], original_text: str, colour_revisions: bool = True) -> None:
    from docx.shared import RGBColor

    rows: list[list[str]] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            rows.append(cells)
    if not rows:
        return
    width = max(len(row) for row in rows)
    table = doc.add_table(rows=0, cols=width)
    table.style = "Table Grid"
    original_norm = _plain_compare_text(original_text)
    for row_index, cells in enumerate(rows):
        row = table.add_row().cells
        for column in range(width):
            value = cells[column] if column < len(cells) else ""
            paragraph = row[column].paragraphs[0]
            run = paragraph.add_run(value)
            if row_index == 0:
                run.bold = True
            if colour_revisions and _plain_compare_text(value) and _plain_compare_text(value) not in original_norm:
                run.font.color.rgb = RGBColor(*_REVISION_BLUE)


def _write_markdown_document(doc, markdown_text: str, original_text: str | None = None, colour_revisions: bool = False, heading_offset: int = 0) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    lines = _finalise_article_text(markdown_text).splitlines()
    line_map = _revision_line_map(original_text or "", [line for line in lines]) if colour_revisions else {}
    table_buffer: list[str] = []
    code_buffer: list[str] = []
    in_code = False
    equation_buffer: list[str] = []
    in_equation = False

    def add_content(paragraph, content: str, index: int, original_override: str | None = None) -> None:
        original_line = original_override if original_override is not None else line_map.get(index)
        if colour_revisions:
            _add_diff_runs(paragraph, content, original_line)
        else:
            _add_black_inline_runs(paragraph, content)

    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                for code_line in code_buffer:
                    paragraph = doc.add_paragraph()
                    run = paragraph.add_run(code_line)
                    run.font.name = "Consolas"
                    run.font.size = Pt(9)
                    if colour_revisions:
                        run.font.color.rgb = RGBColor(*_REVISION_BLUE)
                code_buffer = []
                in_code = False
            else:
                if table_buffer:
                    _add_revision_table(doc, table_buffer, original_text or "", colour_revisions)
                    table_buffer = []
                in_code = True
            continue
        if in_code:
            code_buffer.append(line)
            continue

        if stripped == "$$":
            if in_equation:
                paragraph = doc.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = paragraph.add_run(" ".join(equation_buffer))
                run.font.name = "Cambria Math"
                run.font.size = Pt(12)
                if colour_revisions and _plain_compare_text(run.text) not in _plain_compare_text(original_text or ""):
                    run.font.color.rgb = RGBColor(*_REVISION_BLUE)
                equation_buffer = []
                in_equation = False
            else:
                if table_buffer:
                    _add_revision_table(doc, table_buffer, original_text or "", colour_revisions)
                    table_buffer = []
                in_equation = True
            continue
        if in_equation:
            equation_buffer.append(stripped)
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            table_buffer.append(line)
            continue
        if table_buffer:
            _add_revision_table(doc, table_buffer, original_text or "", colour_revisions)
            table_buffer = []

        if not stripped:
            continue
        if line.startswith("# "):
            level = min(3, 0 + heading_offset)
            paragraph = doc.add_heading("", level=level)
            if level == 0:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_content(paragraph, line[2:].strip(), index)
        elif line.startswith("## "):
            paragraph = doc.add_heading("", level=min(3, 1 + heading_offset))
            add_content(paragraph, line[3:].strip(), index)
        elif line.startswith("### "):
            paragraph = doc.add_heading("", level=min(3, 2 + heading_offset))
            add_content(paragraph, line[4:].strip(), index)
        elif line.startswith("#### "):
            paragraph = doc.add_heading("", level=3)
            add_content(paragraph, line[5:].strip(), index)
        elif re.match(r"^[-*•]\s+", line):
            content = re.sub(r"^[-*•]\s+", "", line).strip()
            paragraph = doc.add_paragraph(style="List Bullet")
            add_content(paragraph, content, index)
        elif re.match(r"^\d+[.)]\s+", line):
            content = re.sub(r"^\d+[.)]\s+", "", line).strip()
            paragraph = doc.add_paragraph(style="List Number")
            add_content(paragraph, content, index)
        else:
            paragraph = doc.add_paragraph()
            add_content(paragraph, line, index)

    if table_buffer:
        _add_revision_table(doc, table_buffer, original_text or "", colour_revisions)
    if code_buffer:
        for code_line in code_buffer:
            paragraph = doc.add_paragraph()
            run = paragraph.add_run(code_line)
            run.font.name = "Consolas"
            run.font.size = Pt(9)
            if colour_revisions:
                run.font.color.rgb = RGBColor(*_REVISION_BLUE)
    if equation_buffer:
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(" ".join(equation_buffer))
        run.font.name = "Cambria Math"
        run.font.size = Pt(12)
        if colour_revisions:
            run.font.color.rgb = RGBColor(*_REVISION_BLUE)


def export_revised_article_docx(
    original_article_text: str,
    revised_article_text: str,
    title: str = "Revised Journal Article",
    revision_report: str = "",
    reviewer_response_matrix: str = "",
    include_revision_report: bool = True,
) -> tuple[io.BytesIO, str]:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt, RGBColor

    safe_title = re.sub(r"[^A-Za-z0-9_-]+", "_", (title or "revised_article")[:80]).strip("_") or "revised_article"
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5
    for style_name in ["Title", "Heading 1", "Heading 2", "Heading 3"]:
        style = doc.styles[style_name]
        style.font.name = "Times New Roman"
        style.font.color.rgb = RGBColor(0, 0, 0)

    note = doc.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = note.add_run("Revision display: wording added or changed by ArticleReady AI appears in blue. Exact unchanged wording remains black.")
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(89, 98, 115)

    _write_markdown_document(
        doc,
        revised_article_text,
        original_text=original_article_text,
        colour_revisions=True,
    )

    if include_revision_report and (revision_report.strip() or reviewer_response_matrix.strip()):
        doc.add_page_break()
        heading = doc.add_heading("Revision and Publishability Report", level=0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if revision_report.strip():
            clean_report = re.sub(r"^#\s+Revision and Publishability Report\s*", "", revision_report.strip(), count=1, flags=re.IGNORECASE)
            _write_markdown_document(doc, clean_report, colour_revisions=False, heading_offset=1)
        if reviewer_response_matrix.strip():
            doc.add_heading("Response to Reviewer Comments", level=1)
            _write_markdown_document(doc, reviewer_response_matrix, colour_revisions=False, heading_offset=1)

    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream, f"{safe_title}_polished_revision_blue.docx"
