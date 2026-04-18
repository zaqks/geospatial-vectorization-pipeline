from fastapi import APIRouter, UploadFile, File, Form
from typing import Union
import os
from .schemas import UploadResponse, ResultResponse, ProcessingResponse

router = APIRouter(prefix="/api", tags=["processing"])

API_URL = os.getenv("API_URL", "").rstrip("/")


def build_media_url(path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{API_URL}{normalized_path}" if API_URL else normalized_path

# Hardcoded UUID
HARDCODED_UUID = "550e8400-e29b-41d4-a716-446655440000"

# In-memory counter to track request count per UUID
request_counter = {HARDCODED_UUID: 0}


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...), bounding_box: str = Form(...)):
    """
    Upload an image with a bounding box.

    Args:
        file: Image file
        bounding_box: JSON string containing bounding box with 4 points (lat, lng)

    Returns:
        UploadResponse with hardcoded UUID
    """
    request_counter[HARDCODED_UUID] = 0

    return UploadResponse(uuid=HARDCODED_UUID)


@router.get(
    "/result/{upload_uuid}", response_model=Union[ProcessingResponse, ResultResponse]
)
async def get_result(upload_uuid: str):
    """
    Get processing result for a given UUID.

    Returns status_percent only until processing is complete (100).
    On third call, returns full result with img_url and files.
    """
    # Initialize counter if UUID doesn't exist
    # if upload_uuid not in request_counter:
    #     return ProcessingResponse(status_percent=0)
    upload_uuid = HARDCODED_UUID

    # Increment counter on each call
    request_counter[upload_uuid] += 1
    current_count = request_counter[upload_uuid]

    # Return only status_percent until we reach 3 calls
    if current_count < 5:
        status_percent = current_count * 20  # 33, 66        
        return ProcessingResponse(status_percent=status_percent)

    # On 3rd call and beyond, return full result with status_percent = 100
    request_counter[upload_uuid] = 0
    media_url = build_media_url("/media/giphy.gif")
    return ResultResponse(
        img_url=media_url,
        files=[
            ("output_1.tif", media_url),
            ("output_2.tif", media_url),
            ("output_3.tif", media_url),
            ("output_4.tif", media_url),
        ],
        status_percent=100,
    )
