from fastapi import APIRouter, UploadFile, File, Form
from typing import Union
from .schemas import UploadResponse, ResultResponse, ProcessingResponse

router = APIRouter(prefix="/api", tags=["processing"])

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
    return ResultResponse(
        img_url="/static/giphy.gif",
        files=[
            ("output_1.tif", "/static/giphy.gif"),
            ("output_2.tif", "/static/giphy.gif"),
            ("output_3.tif", "/static/giphy.gif"),
            ("output_4.tif", "/static/giphy.gif"),
        ],
        status_percent=100,
    )
