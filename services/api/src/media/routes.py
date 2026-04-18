from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter()


@router.get("/media/{filename}")
async def serve_media(filename: str):
    """
    Serve media files from the static directory.
    """
    media_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", filename)
    return FileResponse(media_path)
