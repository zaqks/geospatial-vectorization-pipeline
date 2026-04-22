import uuid
import json
import os
import time
from urllib import error, request

from sqlalchemy.orm import Session

from .models import Input, Output


DEFAULT_TRIGGER_TIMEOUT_SECONDS = 180
DEFAULT_TRIGGER_RETRIES = 3
FIRST_PIPELINE_ID = "0_setup_workspace"


def trigger_pipeline_with_retry(
    upload_uuid: str,
    pipeline_id: str = FIRST_PIPELINE_ID,
    timeout_seconds: int = DEFAULT_TRIGGER_TIMEOUT_SECONDS,
    retries: int = DEFAULT_TRIGGER_RETRIES,
) -> dict:
    pipeline_url = os.getenv("PIPELINE_URL", "").rstrip("/")
    if not pipeline_url:
        raise ValueError("PIPELINE_URL is not set")

    endpoint = f"{pipeline_url}/api/pipelines/{pipeline_id}/run"
    payload = json.dumps({"params": {"UUID": upload_uuid}}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    last_error: Exception | None = None
    total_attempts = max(1, retries + 1)
    for attempt in range(1, total_attempts + 1):
        req = request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
                try:
                    parsed = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    parsed = {"text": body}
                return {
                    "ok": True,
                    "attempt": attempt,
                    "status_code": response.status,
                    "response": parsed,
                }
        except (error.HTTPError, error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < total_attempts:
                time.sleep(min(attempt, 3))

    raise RuntimeError(
        f"Failed to trigger pipeline '{pipeline_id}' for uuid={upload_uuid} "
        f"after {total_attempts} attempts"
    ) from last_error

def save_mock_input(
    db: Session,
    image_bytes: bytes,
    lat1: float,
    lat2: float,
    lng1: float,
    lng2: float,
) -> str:
    upload_uuid = str(uuid.uuid4())

    db_input = Input(
        uuid=upload_uuid,
        image=image_bytes,
        lat1=lat1,
        lat2=lat2,
        lng1=lng1,
        lng2=lng2,
        percent_progress=0,
    )
    db.add(db_input)
    db.commit()

    return upload_uuid


def get_mock_result(db: Session, upload_uuid: str) -> tuple[Input | None, Output | None]:
    db_input = db.get(Input, upload_uuid)
    if not db_input:
        return None, None

    current_progress = int(getattr(db_input, "percent_progress", 0))
    if current_progress < 100:
        return db_input, None

    db_output = db.get(Output, upload_uuid)
    return db_input, db_output


def update_input_progress(db: Session, upload_uuid: str, percent: int) -> Input | None:
    db_input = db.get(Input, upload_uuid)
    if not db_input:
        return None

    clamped_percent = max(0, min(100, int(percent)))
    db_input.percent_progress = clamped_percent
    db.commit()
    db.refresh(db_input)
    return db_input