import os

import httpx

from ._db import SessionLocal
from .models import Input


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
    origin = os.getenv("PIPELINE_URL")
    if not origin:
        raise ValueError("PIPELINE_URL is not set")

    response = httpx.post(
        f"{origin.rstrip('/')}/api/pipelines/{pipeline_id}/run",
        json={"params": {"uuid": upload_uuid}},
        timeout=60.0,
    )
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "text": response.text}
