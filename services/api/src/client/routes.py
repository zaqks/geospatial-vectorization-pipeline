import json
import os
from typing import Union
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..utils._db import get_db
from .schemas import ProcessingResponse, ResultResponse, UploadResponse
from .service import get_mock_result, save_mock_input

router = APIRouter(prefix="/api", tags=["processing"])

API_URL = os.getenv("API_URL", "").rstrip("/")


def build_media_url(path: str, request: Request) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    if API_URL:
        return f"{API_URL}{normalized_path}"
    return f"{str(request.base_url).rstrip('/')}{normalized_path}"


def build_upload_media_url(upload_uuid: str, filename: str, request: Request) -> str:
    safe_uuid = quote(upload_uuid, safe="")
    safe_filename = quote(filename, safe="")
    return build_media_url(f"/media/{safe_uuid}/{safe_filename}", request)

def _parse_bounding_box(bounding_box: str):
    try:
        payload = json.loads(bounding_box)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid bounding_box JSON") from exc

    points = payload.get("points")
    if not isinstance(points, list) or len(points) != 2:
        raise HTTPException(status_code=400, detail="bounding_box.points must contain exactly 2 points")

    try:
        lat1 = float(points[0]["lat"])
        lng1 = float(points[0]["lng"])
        lat2 = float(points[1]["lat"])
        lng2 = float(points[1]["lng"])
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
        bounding_box: JSON string containing bounding box with exactly 2 points (lat, lng)
        example:
            {"points":[{"lat":36.5897,"lng":2.4475},{"lat":36.5905,"lng":2.4502}]}

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
async def get_result(upload_uuid: str, request: Request, db: Session = Depends(get_db)):
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

    media_url = build_upload_media_url(upload_uuid, "giphy.gif", request)
    return ResultResponse(
        img_url=media_url,
        files=[(f.name, build_upload_media_url(upload_uuid, f.name, request)) for f in db_output.output_files],
        status_percent=100,
    )
