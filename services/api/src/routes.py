from fastapi import APIRouter, UploadFile, File, Form
import uuid as uuid_lib
from .schemas import UploadResponse, ResultResponse, ProcessingResponse

router = APIRouter(prefix="/api", tags=["processing"])

# In-memory counter to track request count per UUID
request_counter = {}


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    bounding_box: str = Form(...)
):
    """
    Upload an image with a bounding box.

    Args:
        file: Image file
        bounding_box: JSON string containing bounding box with 4 points (lat, lng)

    Returns:
        UploadResponse with generated UUID
    """
    generated_uuid = str(uuid_lib.uuid4())
    request_counter[generated_uuid] = 0

    return UploadResponse(uuid=generated_uuid)


@router.get("/result/{upload_uuid}")
async def get_result(upload_uuid: str):
    """
    Get processing result for a given UUID.

    Returns status_percent only until processing is complete (100).
    On third call, returns full result with img_url and files.
    """
    # Initialize counter if UUID doesn't exist
    if upload_uuid not in request_counter:
        return ProcessingResponse(status_percent=0)

    # Increment counter on each call
    request_counter[upload_uuid] += 1
    current_count = request_counter[upload_uuid]

    # Return only status_percent until we reach 3 calls
    if current_count < 3:
        status_percent = (current_count * 33)  # 33, 66
        return ProcessingResponse(status_percent=status_percent)

    # On 3rd call and beyond, return full result with status_percent = 100
    return ResultResponse(
        img_url="/static/giphy.gif",
        files=[
            ("output_1.tif", "/static/giphy.gif"),
            ("output_2.tif", "/static/giphy.gif"),
            ("output_3.tif", "/static/giphy.gif"),
            ("output_4.tif", "/static/giphy.gif"),
        ],
        status_percent=100
    )
