import asyncio
from pathlib import Path

from plombery import get_logger
from pydantic import BaseModel

from ._db import SessionLocal
from .models import Input, Output, OutputFile


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
    logger = get_logger()
    logger.info(
        "[trigger] Requested next pipeline '%s' for uuid=%s (disabled)",
        pipeline_id,
        upload_uuid,
    )

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
    return {
        "pipeline_id": pipeline_id,
        "uuid": upload_uuid,
        "triggered": False,
        "reason": "disabled",
    }


def upsert_output_from_workspace(upload_uuid: str, workspace_output_dir: Path) -> dict:
    logger = get_logger()
    db = SessionLocal()
    try:
        db_input = db.get(Input, upload_uuid)
        if not db_input:
            raise ValueError(f"Upload not found for uuid={upload_uuid}")

        if not workspace_output_dir.exists():
            raise FileNotFoundError(f"Workspace output directory not found: {workspace_output_dir}")

        geojson_paths = sorted(workspace_output_dir.rglob("*.geojson"))
        if not geojson_paths:
            raise FileNotFoundError(f"No GeoJSON files found under {workspace_output_dir}")

        db_output = db.get(Output, upload_uuid)
        if not db_output:
            db_output = Output(uuid=upload_uuid, image=db_input.image)
            db.add(db_output)
            db.flush()
        else:
            db_output.image = db_input.image
            for existing in list(db_output.output_files):
                db.delete(existing)
            db.flush()

        inserted_count = 0
        for geojson_path in geojson_paths:
            relative_path = geojson_path.relative_to(workspace_output_dir)
            stored_name = str(relative_path).replace("/", "__")
            file_bytes = geojson_path.read_bytes()
            db.add(OutputFile(output_uuid=upload_uuid, name=stored_name, file=file_bytes))
            inserted_count += 1

        db.commit()
        logger.info(
            "[export] Upserted output for uuid=%s with %s GeoJSON files",
            upload_uuid,
            inserted_count,
        )
        return {
            "uuid": upload_uuid,
            "output_uuid": upload_uuid,
            "geojson_count": inserted_count,
            "image_source": "input.image",
        }
    finally:
        db.close()


async def upsert_output_from_workspace_async(upload_uuid: str, workspace_output_dir: Path) -> dict:
    return await asyncio.to_thread(upsert_output_from_workspace, upload_uuid, workspace_output_dir)


async def update_input_progress_async(upload_uuid: str, percent: int) -> Input | None:
    return await asyncio.to_thread(update_input_progress, upload_uuid, percent)
