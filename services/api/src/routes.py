import json
import os
from typing import Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .db import get_db
from .models import Input, Output, OutputFile
from .schemas import ProcessingResponse, ResultResponse, UploadResponse

router = APIRouter(prefix="/api", tags=["processing"])

API_URL = os.getenv("API_URL", "").rstrip("/")


def build_media_url(path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{API_URL}{normalized_path}" if API_URL else normalized_path

HARDCODED_UUID = "550e8400-e29b-41d4-a716-446655440000"
PROGRESS_STEP = 20
MOCK_FILE_NAMES = [
    "output_1.tif",
    "output_2.tif",
    "output_3.tif",
    "output_4.tif",
]


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
        UploadResponse with hardcoded UUID
    """
    lat1, lat2, lng1, lng2 = _parse_bounding_box(bounding_box)
    image_bytes = await file.read()

    existing = db.get(Input, HARDCODED_UUID)
    if existing:
        db.query(OutputFile).filter(OutputFile.output_uuid == existing.uuid).delete()
        db.query(Output).filter(Output.uuid == existing.uuid).delete()
        db.delete(existing)
        db.flush()

    db_input = Input(
        uuid=HARDCODED_UUID,
        image=image_bytes,
        lat1=lat1,
        lat2=lat2,
        lng1=lng1,
        lng2=lng2,
        percent_progress=0,
    )
    db.add(db_input)
    db.commit()

    return UploadResponse(uuid=HARDCODED_UUID)


@router.get(
    "/result/{upload_uuid}", response_model=Union[ProcessingResponse, ResultResponse]
)
async def get_result(upload_uuid: str, db: Session = Depends(get_db)):
    """
    Get processing result for a given UUID.

    Returns status_percent only until processing is complete (100).
    On third call, returns full result with img_url and files.
    """
    upload_uuid = HARDCODED_UUID
    db_input = db.get(Input, upload_uuid)
    if not db_input:
        raise HTTPException(status_code=404, detail="Upload not found")

    if db_input.percent_progress < 100:
        db_input.percent_progress = min(100, db_input.percent_progress + PROGRESS_STEP)
        db.commit()
        db.refresh(db_input)

    if db_input.percent_progress < 100:
        return ProcessingResponse(status_percent=db_input.percent_progress)

    db_output = db.get(Output, upload_uuid)
    if not db_output:
        db_output = Output(uuid=upload_uuid, image=db_input.image)
        db.add(db_output)
        db.flush()

        for file_name in MOCK_FILE_NAMES:
            db.add(OutputFile(output_uuid=upload_uuid, name=file_name, file=db_input.image))
        db.commit()
        db.refresh(db_output)

    media_url = build_media_url("/media/giphy.gif")
    return ResultResponse(
        img_url=media_url,
        files=[(f.name, media_url) for f in db_output.output_files],
        status_percent=100,
    )
