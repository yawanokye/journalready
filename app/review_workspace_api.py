from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.file_extractor import extract_uploaded_text, read_upload_limited
from app.review_workspace_store import (
    attach_full_text,
    bulk_update_records,
    calculate_summary,
    create_project,
    create_search_run,
    delete_project,
    export_audit_json,
    export_protocol_docx,
    export_records_csv,
    get_project,
    get_record,
    import_records,
    list_records,
    resolve_duplicate,
    update_project,
    update_record,
    verify_project,
    writer_payload,
)
from app.schemas import (
    ReviewBulkDecisionRequest,
    ReviewDuplicateDecisionRequest,
    ReviewProjectCreateRequest,
    ReviewProjectUpdateRequest,
    ReviewRecordUpdateRequest,
)

router = APIRouter(prefix="/api/review-workspace", tags=["Review Evidence Workspace"])


def _token(value: str | None) -> str:
    return str(value or "").strip()


def _authorise(project_id: str, token: str | None) -> dict[str, Any]:
    try:
        return verify_project(project_id, _token(token))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/projects")
def create_review_project(payload: ReviewProjectCreateRequest) -> dict[str, Any]:
    try:
        return create_project(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{project_id}")
def read_review_project(project_id: str, x_review_workspace_token: str | None = Header(default=None)) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    return get_project(project_id, _token(x_review_workspace_token))


@router.patch("/projects/{project_id}")
def patch_review_project(
    project_id: str,
    payload: ReviewProjectUpdateRequest,
    x_review_workspace_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    try:
        return update_project(project_id, _token(x_review_workspace_token), payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/projects/{project_id}")
def remove_review_project(project_id: str, x_review_workspace_token: str | None = Header(default=None)) -> dict[str, bool]:
    _authorise(project_id, x_review_workspace_token)
    delete_project(project_id, _token(x_review_workspace_token))
    return {"deleted": True}


@router.post("/projects/{project_id}/imports")
async def import_review_records(
    project_id: str,
    file: UploadFile = File(...),
    database_name: str = Form(...),
    platform: str = Form(""),
    source_route: str = Form("database"),
    search_string: str = Form(""),
    search_date: str = Form(""),
    date_limits: str = Form(""),
    language_limits: str = Form(""),
    document_types: str = Form(""),
    reported_result_count: str = Form(""),
    notes: str = Form(""),
    x_review_workspace_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    try:
        content = await read_upload_limited(file, 50 * 1024 * 1024)
        run = create_search_run(
            project_id,
            {
                "database_name": database_name,
                "platform": platform,
                "source_route": source_route,
                "search_string": search_string,
                "search_date": search_date,
                "date_limits": date_limits,
                "language_limits": language_limits,
                "document_types": document_types,
                "reported_result_count": reported_result_count,
                "notes": notes,
            },
        )
        result = import_records(project_id, run["id"], file.filename or "records.csv", content)
        run["imported_record_count"] = result["records_imported"]
        result["search_run"] = run
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Record import failed: {str(exc)[:240]}") from exc


@router.get("/projects/{project_id}/records")
def read_review_records(
    project_id: str,
    stage: str = Query(default="all"),
    decision: str = Query(default=""),
    search: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    x_review_workspace_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    return list_records(project_id, stage=stage, decision=decision, search=search, limit=limit, offset=offset)


@router.get("/projects/{project_id}/records/{record_id}")
def read_review_record(project_id: str, record_id: str, x_review_workspace_token: str | None = Header(default=None)) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    try:
        return get_record(project_id, record_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/projects/{project_id}/records/{record_id}")
def patch_review_record(
    project_id: str,
    record_id: str,
    payload: ReviewRecordUpdateRequest,
    x_review_workspace_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    try:
        return update_record(project_id, record_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/records/bulk-decision")
def bulk_review_decision(
    project_id: str,
    payload: ReviewBulkDecisionRequest,
    x_review_workspace_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    try:
        return bulk_update_records(project_id, payload.record_ids, payload.stage, payload.decision, payload.reason, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/records/{record_id}/duplicate")
def decide_duplicate(
    project_id: str,
    record_id: str,
    payload: ReviewDuplicateDecisionRequest,
    x_review_workspace_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    try:
        return resolve_duplicate(project_id, record_id, payload.action, payload.duplicate_of)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/records/{record_id}/full-text")
async def upload_full_text(
    project_id: str,
    record_id: str,
    file: UploadFile = File(...),
    x_review_workspace_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    try:
        content = await read_upload_limited(file, 25 * 1024 * 1024)
        extracted = extract_uploaded_text(file.filename or "full_text.pdf", content)
        return attach_full_text(project_id, record_id, extracted.get("filename") or file.filename or "full_text", extracted.get("text") or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Full-text extraction failed: {str(exc)[:240]}") from exc


@router.get("/projects/{project_id}/summary")
def review_summary(project_id: str, x_review_workspace_token: str | None = Header(default=None)) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    return calculate_summary(project_id)


@router.get("/projects/{project_id}/writer-payload")
def review_writer_payload(project_id: str, x_review_workspace_token: str | None = Header(default=None)) -> dict[str, Any]:
    _authorise(project_id, x_review_workspace_token)
    return writer_payload(project_id)


@router.get("/projects/{project_id}/export/records.csv")
def download_review_records(
    project_id: str,
    scope: str = Query(default="all"),
    x_review_workspace_token: str | None = Header(default=None),
) -> StreamingResponse:
    _authorise(project_id, x_review_workspace_token)
    if scope not in {"all", "included", "excluded", "duplicates"}:
        scope = "all"
    stream, filename = export_records_csv(project_id, scope)
    return StreamingResponse(stream, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/projects/{project_id}/export/audit.json")
def download_review_audit(project_id: str, x_review_workspace_token: str | None = Header(default=None)) -> StreamingResponse:
    _authorise(project_id, x_review_workspace_token)
    stream, filename = export_audit_json(project_id)
    return StreamingResponse(stream, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/projects/{project_id}/export/protocol.docx")
def download_review_protocol(project_id: str, x_review_workspace_token: str | None = Header(default=None)) -> StreamingResponse:
    _authorise(project_id, x_review_workspace_token)
    stream, filename = export_protocol_docx(project_id)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

