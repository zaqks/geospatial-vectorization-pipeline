import asyncio
from pathlib import Path

from plombery import get_logger
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import load_only

from ._db import SessionLocal
from .models import Input, Output, OutputFile, OverlayImage


import os
import httpx


GEOJSON_INSERT_BATCH_SIZE = 8


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

    origin = os.getenv("PIPELINE_URL")
    if not origin:
        raise ValueError("PIPELINE_URL is not set")

    payload = {"params": {"UUID": upload_uuid}}

    response = httpx.post(
        f"{origin.rstrip('/')}/api/pipelines/{pipeline_id}/run",
        json=payload,
        timeout=10,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "[trigger] Pipeline trigger failed for %s (status=%s, body=%s)",
            pipeline_id,
            response.status_code,
            response.text,
        )
        raise exc

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "text": response.text}
    # print("plo9") # don't touch this leave the trgger commented bc i don't want auto trigger


async def tirrger_flow_async(
    pipeline_id: str,
    upload_uuid: str,
    *,
    timeout_seconds: float = 30,
    allow_read_timeout_success: bool = False,
) -> dict:
    logger = get_logger()
    logger.info(
        "[trigger] Requested next pipeline '%s' for uuid=%s (async)",
        pipeline_id,
        upload_uuid,
    )

    origin = os.getenv("PIPELINE_URL")
    if not origin:
        raise ValueError("PIPELINE_URL is not set")

    payload = {"params": {"UUID": upload_uuid}}
    timeout = httpx.Timeout(connect=5.0, read=timeout_seconds, write=10.0, pool=5.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{origin.rstrip('/')}/api/pipelines/{pipeline_id}/run",
                json=payload,
            )
    except httpx.ReadTimeout as exc:
        if not allow_read_timeout_success:
            raise exc
        logger.warning(
            "[trigger] Read timeout while waiting for '%s' response for uuid=%s; "
            "continuing because timeout is allowed for this handoff",
            pipeline_id,
            upload_uuid,
        )
        return {
            "accepted": True,
            "pipeline_id": pipeline_id,
            "uuid": upload_uuid,
            "warning": "read_timeout_while_waiting_for_response",
        }

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "[trigger] Pipeline trigger failed for %s (status=%s, body=%s)",
            pipeline_id,
            response.status_code,
            response.text,
        )
        raise exc

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "text": response.text}

def upsert_output_from_workspace(upload_uuid: str, workspace_output_dir: Path) -> dict:
    logger = get_logger()
    db = SessionLocal()
    try:
        if not workspace_output_dir.exists():
            raise FileNotFoundError(
                f"Workspace output directory not found: {workspace_output_dir}"
            )

        upload_exists = db.scalar(select(Input.uuid).where(Input.uuid == upload_uuid))
        if not upload_exists:
            raise ValueError(f"Upload not found for uuid={upload_uuid}")

        db_output = db.scalar(
            select(Output).options(load_only(Output.uuid)).where(Output.uuid == upload_uuid)
        )
        if not db_output:
            db_output = Output(uuid=upload_uuid)
            db.add(db_output)
            db.flush()
        else:
            # Bulk delete avoids materializing previous OutputFile.file BLOBs.
            db.execute(delete(OutputFile).where(OutputFile.output_uuid == upload_uuid))
            db.execute(delete(OverlayImage).where(OverlayImage.output_uuid == upload_uuid))
            db.flush()

        inserted_count = 0
        batch_count = 0
        for geojson_path in workspace_output_dir.rglob("*.geojson"):
            relative_path = geojson_path.relative_to(workspace_output_dir)
            stored_name = str(relative_path).replace("/", "__")
            file_bytes = geojson_path.read_bytes()
            db.add(
                OutputFile(output_uuid=upload_uuid, name=stored_name, file=file_bytes)
            )
            inserted_count += 1
            batch_count += 1

            if batch_count >= GEOJSON_INSERT_BATCH_SIZE:
                db.flush()
                db.expunge_all()
                batch_count = 0

        if inserted_count == 0:
            raise FileNotFoundError(
                f"No GeoJSON files found under {workspace_output_dir}"
            )

        workspace_viz_dir = workspace_output_dir.parent / "viz"
        overlay_count = 0
        if workspace_viz_dir.exists():
            for overlay_path in sorted(workspace_viz_dir.glob("*.png")):
                db.add(
                    OverlayImage(
                        output_uuid=upload_uuid,
                        name=overlay_path.name,
                        image=overlay_path.read_bytes(),
                    )
                )
                overlay_count += 1

        if batch_count:
            db.flush()
            db.expunge_all()

        db.commit()
        logger.info(
            "[export] Upserted output for uuid=%s with %s GeoJSON files and %s overlays",
            upload_uuid,
            inserted_count,
            overlay_count,
        )
        return {
            "uuid": upload_uuid,
            "output_uuid": upload_uuid,
            "geojson_count": inserted_count,
            "overlay_count": overlay_count,
        }
    finally:
        db.close()


async def upsert_output_from_workspace_async(
    upload_uuid: str, workspace_output_dir: Path
) -> dict:
    return await asyncio.to_thread(
        upsert_output_from_workspace, upload_uuid, workspace_output_dir
    )


def upsert_output_archive_from_workspace(
    upload_uuid: str,
    workspace_output_dir: Path,
    archive_path: Path,
) -> dict:
    logger = get_logger()
    db = SessionLocal()
    try:
        if not workspace_output_dir.exists():
            raise FileNotFoundError(
                f"Workspace output directory not found: {workspace_output_dir}"
            )
        if not archive_path.exists():
            raise FileNotFoundError(f"Output archive not found: {archive_path}")

        upload_exists = db.scalar(select(Input.uuid).where(Input.uuid == upload_uuid))
        if not upload_exists:
            raise ValueError(f"Upload not found for uuid={upload_uuid}")

        db_output = db.scalar(
            select(Output).options(load_only(Output.uuid)).where(Output.uuid == upload_uuid)
        )
        if not db_output:
            db_output = Output(uuid=upload_uuid)
            db.add(db_output)
            db.flush()
        else:
            db.execute(delete(OutputFile).where(OutputFile.output_uuid == upload_uuid))
            db.execute(delete(OverlayImage).where(OverlayImage.output_uuid == upload_uuid))
            db.flush()

        archive_bytes = archive_path.read_bytes()
        db.add(
            OutputFile(
                output_uuid=upload_uuid,
                name=archive_path.name,
                file=archive_bytes,
            )
        )

        workspace_viz_dir = workspace_output_dir.parent / "viz"
        overlay_count = 0
        if workspace_viz_dir.exists():
            for overlay_path in sorted(workspace_viz_dir.glob("*.png")):
                db.add(
                    OverlayImage(
                        output_uuid=upload_uuid,
                        name=overlay_path.name,
                        image=overlay_path.read_bytes(),
                    )
                )
                overlay_count += 1

        db.commit()
        logger.info(
            "[export] Upserted output archive for uuid=%s as %s with %s overlays",
            upload_uuid,
            archive_path.name,
            overlay_count,
        )
        return {
            "uuid": upload_uuid,
            "output_uuid": upload_uuid,
            "archive_name": archive_path.name,
            "archive_size": len(archive_bytes),
            "overlay_count": overlay_count,
        }
    finally:
        db.close()


async def upsert_output_archive_from_workspace_async(
    upload_uuid: str,
    workspace_output_dir: Path,
    archive_path: Path,
) -> dict:
    return await asyncio.to_thread(
        upsert_output_archive_from_workspace,
        upload_uuid,
        workspace_output_dir,
        archive_path,
    )


async def update_input_progress_async(upload_uuid: str, percent: int) -> Input | None:
    return await asyncio.to_thread(update_input_progress, upload_uuid, percent)
