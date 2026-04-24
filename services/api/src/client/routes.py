import asyncio
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Union
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..utils._db import get_db
from .schemas import ProcessingResponse, ResultResponse, UploadResponse
from .service import get_mock_result, save_mock_input, trigger_pipeline_with_retry

router = APIRouter(prefix="/api", tags=["processing"])

API_URL = os.getenv("API_URL", "").rstrip("/")


@dataclass
class ProgressEvent:
    uuid: str
    task: str | None
    event: str
    status_percent: int | None = None
    result_ready: bool | None = None


class NotifyEventPayload(BaseModel):
    uuid: str
    task: str | None = None
    event: str = "task_completed"
    status_percent: int | None = None
    result_ready: bool | None = None


_pending_events: dict[str, list[ProgressEvent]] = defaultdict(list)
_stream_signals: dict[str, asyncio.Event] = {}
_event_lock = asyncio.Lock()


def _format_sse_message(data: dict[str, Any], event: str | None = None) -> bytes:
    payload = json.dumps(data, separators=(",", ":"))
    if event:
        return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
    return f"data: {payload}\n\n".encode("utf-8")


async def _enqueue_progress_event(progress_event: ProgressEvent) -> None:
    async with _event_lock:
        _pending_events[progress_event.uuid].append(progress_event)
        signal = _stream_signals.get(progress_event.uuid)
        if signal is None:
            signal = asyncio.Event()
            _stream_signals[progress_event.uuid] = signal
        signal.set()


async def _pop_progress_event(upload_uuid: str) -> ProgressEvent | None:
    async with _event_lock:
        queued = _pending_events.get(upload_uuid)
        if not queued:
            return None
        event = queued.pop(0)
        if not queued:
            _pending_events.pop(upload_uuid, None)
        return event


async def _wait_for_progress_signal(upload_uuid: str, timeout_seconds: float = 20.0) -> None:
    async with _event_lock:
        signal = _stream_signals.get(upload_uuid)
        if signal is None:
            signal = asyncio.Event()
            _stream_signals[upload_uuid] = signal

    try:
        await asyncio.wait_for(signal.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return

    async with _event_lock:
        signal.clear()


def build_media_url(path: str, request: Request) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    if API_URL:
        return f"{API_URL}{normalized_path}"
    return f"{str(request.base_url).rstrip('/')}{normalized_path}"


def build_upload_media_url(upload_uuid: str, filename: str, request: Request) -> str:
    safe_uuid = quote(upload_uuid, safe="")
    safe_filename = quote(filename, safe="")
    return build_media_url(f"/media/{safe_uuid}/{safe_filename}", request)


def build_upload_preview_url(upload_uuid: str, request: Request) -> str:
    safe_uuid = quote(upload_uuid, safe="")
    return build_media_url(f"/media/{safe_uuid}/preview/image.png", request)


def build_upload_overlay_url(upload_uuid: str, filename: str, request: Request) -> str:
    safe_uuid = quote(upload_uuid, safe="")
    safe_filename = quote(filename, safe="")
    return build_media_url(f"/media/{safe_uuid}/overlay/{safe_filename}", request)

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
    upload_uuid = save_mock_input(
        db,
        image_bytes,
        file.filename or "input",
        lat1,
        lat2,
        lng1,
        lng2,
    )

    try:
        await asyncio.to_thread(trigger_pipeline_with_retry, upload_uuid)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upload saved but failed to trigger pipeline: {exc}",
        ) from exc

    return UploadResponse(uuid=upload_uuid)


@router.get(
    "/result/{upload_uuid}", response_model=Union[ProcessingResponse, ResultResponse]
)
async def get_result(upload_uuid: str, request: Request, db: Session = Depends(get_db)):
    """
    Get processing result for a given UUID.

    Returns status_percent from DB until processing output is available.
    """
    db_input, db_output = get_mock_result(db, upload_uuid)
    if not db_input:
        raise HTTPException(status_code=404, detail="Upload not found")

    if db_input.percent_progress < 100 or not db_output:
        return ProcessingResponse(status_percent=db_input.percent_progress)

    output_files = db_output.output_files or []
    overlay_images = db_output.overlay_images or []
    return ResultResponse(
        img_url=build_upload_preview_url(upload_uuid, request),
        overlays=[
            (img.name, build_upload_overlay_url(upload_uuid, img.name, request))
            for img in overlay_images
        ],
        files=[(f.name, build_upload_media_url(upload_uuid, f.name, request)) for f in output_files],
        status_percent=db_input.percent_progress,
    )


@router.post("/events/notify")
async def notify_event(payload: NotifyEventPayload):
    progress_event = ProgressEvent(
        uuid=payload.uuid,
        task=payload.task,
        event=payload.event,
        status_percent=payload.status_percent,
        result_ready=payload.result_ready,
    )
    await _enqueue_progress_event(progress_event)
    return {"ok": True}


@router.get("/events/{upload_uuid}")
async def stream_events(upload_uuid: str, request: Request, db: Session = Depends(get_db)):
    db_input, db_output = get_mock_result(db, upload_uuid)
    if not db_input:
        raise HTTPException(status_code=404, detail="Upload not found")

    initial_payload = {
        "uuid": upload_uuid,
        "event": "snapshot",
        "task": None,
        "status_percent": int(db_input.percent_progress),
        "result_ready": bool(db_output),
        "source": "db_snapshot",
    }

    async def event_generator():
        yield _format_sse_message(initial_payload)

        while True:
            if await request.is_disconnected():
                break

            pending = await _pop_progress_event(upload_uuid)
            if pending is not None:
                event_payload = {
                    "uuid": pending.uuid,
                    "event": pending.event,
                    "task": pending.task,
                    "status_percent": pending.status_percent,
                    "result_ready": bool(pending.result_ready),
                    "source": "webhook",
                }
                yield _format_sse_message(event_payload)
                continue

            await _wait_for_progress_signal(upload_uuid)
            yield b": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
