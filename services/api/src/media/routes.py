import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..client.models import OutputFile
from ..utils._db import get_db

router = APIRouter(tags=["Files"])


def _as_media_response(filename: str, blob: bytes) -> Response:
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=blob,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


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
    return _as_media_response(filename, db_file.file)
