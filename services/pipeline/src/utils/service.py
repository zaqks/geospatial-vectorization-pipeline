import os
import asyncio

import httpx
from pydantic import BaseModel

from ._db import SessionLocal
from .models import Input


class GeorefBounds(BaseModel):
    lat1: float
    lat2: float
    lng1: float
    lng2: float


def get_input_georef_bounds(upload_uuid: str) -> GeorefBounds | None:
    db = SessionLocal()
    try:
        db_input = db.get(Input, upload_uuid)
        if not db_input:
            return None

        return GeorefBounds(
            lat1=float(db_input.lat1),
            lat2=float(db_input.lat2),
            lng1=float(db_input.lng1),
            lng2=float(db_input.lng2),
        )
    finally:
        db.close()


def update_input_progress(upload_uuid: str, percent: int) -> Input | None:
    db = SessionLocal()
    try:
        db_input = db.get(Input, upload_uuid)
        if not db_input:
            return None

        clamped_percent = max(0, min(100, int(percent)))
        db_input.percent_progress = clamped_percent
        db.commit()
        db.refresh(db_input)
        return db_input
    finally:
        db.close()


def tirrger_flow(pipeline_id: str, upload_uuid: str) -> dict:
    # origin = os.getenv("PIPELINE_URL")
    # if not origin:
    #     raise ValueError("PIPELINE_URL is not set")

    # response = httpx.post(
    #     f"{origin.rstrip('/')}/api/pipelines/{pipeline_id}/run",
    #     json={"params": {"uuid": upload_uuid}},
    #     timeout=60.0,
    # )
    # response.raise_for_status()

    # try:
    #     return response.json()
    # except ValueError:
    #     return {"status_code": response.status_code, "text": response.text}
    print("yoo")


async def update_input_progress_async(upload_uuid: str, percent: int) -> Input | None:
    return await asyncio.to_thread(update_input_progress, upload_uuid, percent)
