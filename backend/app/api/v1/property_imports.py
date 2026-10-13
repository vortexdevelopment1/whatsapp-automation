import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.property_import_batch import PropertyImportBatch
from app.models.property_import_row import PropertyImportRow
from app.models.property_source import PropertySource
from app.models.enums import PropertyImportType, PropertyImportBatchStatus, PropertySourceStatus
from app.schemas.property_import import (
    PropertyImportBatchResponse,
    PropertyImportRowResponse,
    PropertyImportPreviewResponse,
)
from app.services.property_import_service import PropertyImportService
from app.services.demo_property_source_adapter import DemoPropertySourceAdapter

router = APIRouter(prefix="/property-imports", tags=["property-imports"])


@router.post("/upload", response_model=PropertyImportBatchResponse, status_code=status.HTTP_201_CREATED)
async def upload_import_file(
    source_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV file for inventory import and validate row structure.
    """
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files (.csv) are supported for property import.",
        )

    # Read content with a reasonable size limit (10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed limit of 10MB.",
        )

    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_text = content.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to decode CSV file. Please ensure UTF-8 or Latin-1 encoding.",
            )

    service = PropertyImportService(db)
    batch = service.parse_and_validate_csv(
        source_id=source_id,
        file_name=file.filename,
        csv_text=csv_text,
        actor_id=x_admin_id,
    )
    return batch


@router.post("/demo-seed", response_model=PropertyImportBatchResponse, status_code=status.HTTP_201_CREATED)
def seed_demo_batch(
    row_count: int = Query(100, ge=5, le=500),
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """
    Seeds a synthetic import batch from DemoPropertySourceAdapter.
    Automatically finds or creates an active DEMO PropertySource.
    """
    # Find or create demo source
    from app.models.enums import PropertySourceType
    source = db.query(PropertySource).filter(PropertySource.external_system_name == DemoPropertySourceAdapter.SOURCE_CODE).first()
    if not source:
        source = PropertySource(
            name=DemoPropertySourceAdapter.SOURCE_NAME,
            source_type=PropertySourceType.DEMO,
            external_system_name=DemoPropertySourceAdapter.SOURCE_CODE,
            status=PropertySourceStatus.ACTIVE,
            configuration_reference="internal://demo-adapter",
        )
        db.add(source)
        db.commit()
        db.refresh(source)


    csv_text = DemoPropertySourceAdapter.generate_csv_content(count=row_count)
    service = PropertyImportService(db)
    batch = service.parse_and_validate_csv(
        source_id=source.id,
        file_name=f"synthetic_demo_{row_count}_rows.csv",
        csv_text=csv_text,
        actor_id=x_admin_id,
    )
    batch.import_type = PropertyImportType.DEMO
    db.commit()
    db.refresh(batch)
    return batch


@router.get("", response_model=List[PropertyImportBatchResponse])
def list_import_batches(
    status_filter: Optional[PropertyImportBatchStatus] = Query(None, alias="status"),
    source_id: Optional[uuid.UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List property import batches with status filters."""
    query = db.query(PropertyImportBatch)
    if status_filter:
        query = query.filter(PropertyImportBatch.status == status_filter)
    if source_id:
        query = query.filter(PropertyImportBatch.source_id == source_id)
    batches = query.order_by(PropertyImportBatch.created_at.desc()).offset(skip).limit(limit).all()
    return batches


@router.get("/{batch_id}", response_model=PropertyImportBatchResponse)
def get_import_batch(
    batch_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get single import batch details."""
    service = PropertyImportService(db)
    return service.get_batch_or_404(batch_id)


@router.post("/{batch_id}/preview", response_model=PropertyImportPreviewResponse)
def preview_import_batch(
    batch_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Run dry-run deduplication and validation analysis on batch rows without mutating catalog inventory.
    """
    service = PropertyImportService(db)
    result = service.preview_batch(batch_id)
    counts = result["counts"]
    sample_rows = []
    for r in result["rows"]:
        dedup_info = r.get("dedup_result") or {}
        sample_rows.append({
            "row_number": r["row_number"],
            "raw_payload": r["raw_payload"],
            "normalized_payload": r["normalized_payload"],
            "status": r["status"],
            "dedup_verdict": dedup_info.get("action"),
            "dedup_confidence": dedup_info.get("confidence"),
            "dedup_reasons": dedup_info.get("reasons"),
            "target_property_id": uuid.UUID(dedup_info["property_id"]) if dedup_info.get("property_id") else None,
            "target_listing_id": uuid.UUID(dedup_info["existing_listing_id"]) if dedup_info.get("existing_listing_id") else None,
            "errors": r.get("errors"),
        })

    return PropertyImportPreviewResponse(
        batch_id=batch_id,
        total_rows=counts["total_rows"],
        valid_rows=counts["valid_rows"],
        invalid_rows=counts["invalid_rows"],
        duplicate_listing_rows=counts["duplicate_listing_rows"],
        matched_existing_property_rows=counts["matched_existing_property_rows"],
        new_property_rows=counts["new_property_rows"],
        manual_review_rows=counts["manual_review_rows"],
        sample_rows=sample_rows,
    )


@router.post("/{batch_id}/commit", response_model=PropertyImportBatchResponse)
def commit_import_batch(
    batch_id: uuid.UUID,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """
    Commit parsed rows to canonical properties and listing records.
    """
    service = PropertyImportService(db)
    return service.commit_batch(batch_id, actor_id=x_admin_id)


@router.post("/{batch_id}/retry", response_model=PropertyImportBatchResponse)
def retry_import_batch(
    batch_id: uuid.UUID,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """
    Safely retry failed or incomplete rows in a batch without duplicating completed ones.
    """
    service = PropertyImportService(db)
    return service.retry_batch(batch_id, actor_id=x_admin_id)


@router.get("/{batch_id}/rows", response_model=List[PropertyImportRowResponse])
def get_import_batch_rows(
    batch_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get parsed and processed rows for a specific import batch."""
    # Ensure batch exists
    service = PropertyImportService(db)
    service.get_batch_or_404(batch_id)

    rows = (
        db.query(PropertyImportRow)
        .filter(PropertyImportRow.batch_id == batch_id)
        .order_by(PropertyImportRow.row_number.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return rows
