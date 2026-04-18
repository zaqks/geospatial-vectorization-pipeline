import json
import os
from typing import Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..utils._db import get_db
from .schemas import ProcessingResponse, ResultResponse, UploadResponse
from .service import get_mock_result, save_mock_input

router = APIRouter(prefix="/api", tags=["processing"])

API_URL = os.getenv("API_URL", "").rstrip("/")


def build_media_url(path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{API_URL}{normalized_path}" if API_URL else normalized_path

def _parse_bounding_box(bounding_box: str):
    try:
        payload = json.loads(bounding_box)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid bounding_box JSON") from exc

    points = payload.get("points")
    if not isinstance(points, list) or len(points) < 4:
        raise HTTPException(status_code=400, detail="bounding_box.points must contain 4 points")

    try:
        lat1 = float(points[0]["lat"])
        lng1 = float(points[0]["lng"])
        lat2 = float(points[2]["lat"])
        lng2 = float(points[2]["lng"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid point format in bounding_box") from exc

    return lat1, lat2, lng1, lng2


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    bounding_box: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload an image with a bounding box.

    Args:
        file: Image file
        bounding_box: JSON string containing bounding box with 4 points (lat, lng)

    Returns:
        UploadResponse with generated UUID
    """
    lat1, lat2, lng1, lng2 = _parse_bounding_box(bounding_box)
    image_bytes = await file.read()
    upload_uuid = save_mock_input(db, image_bytes, lat1, lat2, lng1, lng2)
    return UploadResponse(uuid=upload_uuid)


@router.get(
    "/result/{upload_uuid}", response_model=Union[ProcessingResponse, ResultResponse]
)
async def get_result(upload_uuid: str, db: Session = Depends(get_db)):
    """
    Get processing result for a given UUID.

    Returns status_percent only until processing is complete (100).
    On third call, returns full result with img_url and files.
    """
    db_input, db_output = get_mock_result(db, upload_uuid)
    if not db_input:
        raise HTTPException(status_code=404, detail="Upload not found")

    if db_input.percent_progress < 100:
        return ProcessingResponse(status_percent=db_input.percent_progress)

    media_url = build_media_url("/media/giphy.gif")
    return ResultResponse(
        img_url=media_url,
        files=[(f.name, media_url) for f in db_output.output_files],
        status_percent=100,
    )
