"""Tenant-scoped document page-analysis, chat, and download endpoints."""

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
)

from document_intelligence.analysis.export import (
    ExportFormat,
    document_payload,
    export_document_markdown,
    export_json,
    export_page_markdown,
    page_payload,
)
from document_intelligence.api.identity import Identity
from document_intelligence.api.schemas import (
    AnalysisResponse,
    QueueResponse,
    UploadResponse,
)
from document_intelligence.api.state import AppState
from document_intelligence.domain.analysis import (
    DocumentRecord,
    PageChatRequest,
    PageChatResponse,
)
from document_intelligence.jobs.queue import Job

router = APIRouter(prefix="/documents", tags=["documents"])


def state(request: Request) -> AppState:
    return cast(AppState, request.app.state.app_state)


State = Annotated[AppState, Depends(state)]


@router.post("", response_model=UploadResponse, status_code=201)
async def upload(
    identity: Identity,
    app: State,
    file: Annotated[UploadFile, File(description="Born-digital document PDF")],
) -> UploadResponse:
    content = await file.read(app.settings.max_upload_bytes + 1)
    document, created = app.service.upload(
        identity.tenant_id,
        identity.actor_id,
        file.filename or "document.pdf",
        file.content_type or "",
        content,
    )
    job_id = None
    if created:
        jobs = app.queue.list(identity.tenant_id)
        job_id = next((job.id for job in jobs if job.document_id == document.id), None)
    return UploadResponse(document=document, duplicate=not created, job_id=job_id)


@router.get("", response_model=list[DocumentRecord])
def documents(
    identity: Identity,
    app: State,
    status: Literal["uploaded", "processing", "completed", "failed"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[DocumentRecord]:
    return app.repository.list_documents(identity.tenant_id, status, limit)


@router.get("/queue", response_model=QueueResponse)
def queue(identity: Identity, app: State) -> QueueResponse:
    return QueueResponse(
        documents=app.repository.list_documents(identity.tenant_id),
        jobs=app.queue.list(identity.tenant_id),
    )


@router.get("/{document_id}", response_model=DocumentRecord)
def detail(document_id: UUID, identity: Identity, app: State) -> DocumentRecord:
    return app.service.document(identity.tenant_id, document_id)


@router.get("/{document_id}/content")
def content(document_id: UUID, identity: Identity, app: State) -> Response:
    record = app.service.document(identity.tenant_id, document_id)
    payload = app.blobs.get(record.storage_key)
    return Response(
        payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{record.filename}"'},
    )


@router.get("/{document_id}/analysis", response_model=AnalysisResponse)
def analysis(document_id: UUID, identity: Identity, app: State) -> AnalysisResponse:
    record = app.service.document(identity.tenant_id, document_id)
    stored = app.repository.get_analysis(identity.tenant_id, document_id)
    payload = document_payload(record, stored)
    return AnalysisResponse.model_validate(payload)


@router.post("/{document_id}/reanalyze", response_model=Job, status_code=202)
def reanalyze(document_id: UUID, identity: Identity, app: State) -> Job:
    return app.service.reanalyze(identity.tenant_id, document_id, identity.actor_id)


@router.post("/{document_id}/pages/{page}/chat", response_model=PageChatResponse)
async def page_chat(
    document_id: UUID,
    page: Annotated[int, Path(ge=1)],
    body: PageChatRequest,
    identity: Identity,
    app: State,
) -> PageChatResponse:
    return await app.service.chat(identity.tenant_id, document_id, page, list(body.messages))


@router.get("/{document_id}/analysis/export")
def export_analysis(
    document_id: UUID,
    identity: Identity,
    app: State,
    format: ExportFormat = "json",
) -> Response:
    record = app.service.document(identity.tenant_id, document_id)
    stored = app.repository.get_analysis(identity.tenant_id, document_id)
    if format == "md":
        return Response(
            export_document_markdown(record, stored),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{document_id}.md"'},
        )
    return Response(
        export_json(document_payload(record, stored)),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{document_id}.json"'},
    )


@router.get("/{document_id}/pages/{page}/export")
def export_page(
    document_id: UUID,
    page: Annotated[int, Path(ge=1)],
    identity: Identity,
    app: State,
    format: ExportFormat = "json",
) -> Response:
    record = app.service.document(identity.tenant_id, document_id)
    stored = app.repository.get_analysis(identity.tenant_id, document_id)
    if format == "md":
        markdown = export_page_markdown(record, stored, page)
        if markdown is None:
            raise HTTPException(status_code=404, detail="Page analysis not found")
        return Response(
            markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{document_id}-p{page}.md"'},
        )
    payload = page_payload(record, stored, page)
    if payload is None:
        raise HTTPException(status_code=404, detail="Page analysis not found")
    return Response(
        export_json(payload),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{document_id}-p{page}.json"'},
    )
