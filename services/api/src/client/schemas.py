from pydantic import BaseModel
from typing import List, Tuple, Optional


class Point(BaseModel):
    lat: float
    lng: float


class BoundingBox(BaseModel):
    points: List[Point]  # 2 points with (lat, lng)


class UploadResponse(BaseModel):
    uuid: str


class ResultResponse(BaseModel):
    img_url: str
    overlays: List[Tuple[str, str]]  # List of (overlay_name, url) tuples
    files: List[Tuple[str, str]]  # List of (filename, url) tuples
    status_percent: int


class ProcessingResponse(BaseModel):
    status_percent: int
