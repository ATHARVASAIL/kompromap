"""Upload-and-ingest endpoints — one per parser (spec §5 MVP: "Import
parsers: Nmap XML, Nuclei JSON, Amass/Subfinder output, Burp/ZAP XML
export"). Each parses the uploaded file, then hands the result to the
ingestion service to actually create nodes/edges.
"""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.parsers import parse_amass_output, parse_burp_zap_xml, parse_nmap_xml, parse_nuclei_json
from app.schemas.ingest import IngestSummaryResponse
from app.services.engagements import resolve_engagement_id
from app.services.ingestion import ingest_parse_result

router = APIRouter(prefix="/ingest", tags=["ingest"])

# Cap on uploaded scan files. Real Nmap/Burp XML from a large engagement can
# legitimately run to tens of MB, so this is generous — but it must exist:
# a bare `await file.read()` buffers the *entire* upload into memory, so
# without a limit anyone can exhaust the server's RAM by POSTing a large
# file. Read in chunks and abort as soon as the cap is passed, rather than
# reading it all and then checking the size (which would defeat the point).
MAX_UPLOAD_BYTES = 64 * 1024 * 1024  # 64 MB
_CHUNK = 1024 * 1024  # 1 MB


async def _read_upload(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                413,
                f"Uploaded file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            )
        chunks.append(chunk)

    content = b"".join(chunks)
    if not content:
        raise HTTPException(422, "Uploaded file is empty")
    return content


@router.post("/nmap", response_model=IngestSummaryResponse)
async def ingest_nmap(
    file: UploadFile = File(...),
    engagement_id: uuid.UUID | None = Form(default=None, description="Defaults to the active engagement"),
    db: Session = Depends(get_db),
):
    content = await _read_upload(file)
    try:
        result = parse_nmap_xml(content)
    except Exception as e:  # noqa: BLE001 - surface as a 422, not a 500
        raise HTTPException(422, f"Failed to parse Nmap XML: {e}") from e
    resolved_engagement_id = resolve_engagement_id(db, engagement_id)
    summary = ingest_parse_result(db, result, resolved_engagement_id)
    return IngestSummaryResponse(**summary.__dict__)


@router.post("/nuclei", response_model=IngestSummaryResponse)
async def ingest_nuclei(
    file: UploadFile = File(...),
    engagement_id: uuid.UUID | None = Form(default=None, description="Defaults to the active engagement"),
    db: Session = Depends(get_db),
):
    content = await _read_upload(file)
    try:
        result = parse_nuclei_json(content)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Failed to parse Nuclei output: {e}") from e
    resolved_engagement_id = resolve_engagement_id(db, engagement_id)
    summary = ingest_parse_result(db, result, resolved_engagement_id)
    return IngestSummaryResponse(**summary.__dict__)


@router.post("/amass", response_model=IngestSummaryResponse)
async def ingest_amass(
    file: UploadFile = File(...),
    engagement_id: uuid.UUID | None = Form(default=None, description="Defaults to the active engagement"),
    db: Session = Depends(get_db),
):
    content = await _read_upload(file)
    try:
        result = parse_amass_output(content)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Failed to parse Amass/Subfinder output: {e}") from e
    resolved_engagement_id = resolve_engagement_id(db, engagement_id)
    summary = ingest_parse_result(db, result, resolved_engagement_id)
    return IngestSummaryResponse(**summary.__dict__)


@router.post("/burp", response_model=IngestSummaryResponse)
async def ingest_burp(
    file: UploadFile = File(...),
    engagement_id: uuid.UUID | None = Form(default=None, description="Defaults to the active engagement"),
    db: Session = Depends(get_db),
):
    content = await _read_upload(file)
    try:
        result = parse_burp_zap_xml(content)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Failed to parse Burp/ZAP XML: {e}") from e
    resolved_engagement_id = resolve_engagement_id(db, engagement_id)
    summary = ingest_parse_result(db, result, resolved_engagement_id)
    return IngestSummaryResponse(**summary.__dict__)
