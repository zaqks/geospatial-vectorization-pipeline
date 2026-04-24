import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..client.models import Input, OutputFile, OverlayImage
from ..utils._db import get_db
from ..utils.hf_storage import download_from_hf

router = APIRouter(tags=["Files"])


def _as_media_response(filename: str, blob: bytes) -> Response:
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=blob,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/media/{upload_uuid}/preview/image.png")
async def serve_output_preview_image(
    upload_uuid: str,
    db: Session = Depends(get_db),
):
    db_input = db.get(Input, upload_uuid)
    if not db_input or not db_input.image_ref:
        raise HTTPException(status_code=404, detail="Preview image not found")
    try:
        file_bytes = download_from_hf(db_input.image_ref)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Preview image not found") from exc
    return _as_media_response(db_input.image_name or "image.png", file_bytes)


@router.get("/media/{upload_uuid}/{filename}")
async def serve_media_for_upload(
    upload_uuid: str,
    filename: str,
    db: Session = Depends(get_db),
):
    db_file = (
        db.query(OutputFile)
        .filter(OutputFile.output_uuid == upload_uuid, OutputFile.name == filename)
        .first()
    )
    if not db_file:
        raise HTTPException(status_code=404, detail="Media not found")
    try:
        file_bytes = download_from_hf(db_file.file_ref)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Media not found") from exc
    return _as_media_response(filename, file_bytes)


@router.get("/media/{upload_uuid}/overlay/{filename}")
async def serve_overlay_for_upload(
    upload_uuid: str,
    filename: str,
    db: Session = Depends(get_db),
):
    db_file = (
        db.query(OverlayImage)
        .filter(OverlayImage.output_uuid == upload_uuid, OverlayImage.name == filename)
        .first()
    )
    if not db_file:
        raise HTTPException(status_code=404, detail="Overlay image not found")
    try:
        file_bytes = download_from_hf(db_file.image_ref)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Overlay image not found") from exc
    return _as_media_response(filename, file_bytes)
