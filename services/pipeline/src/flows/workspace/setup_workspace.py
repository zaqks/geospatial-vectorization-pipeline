from io import BytesIO
from pathlib import Path
import shutil
import asyncio

from PIL import Image, UnidentifiedImageError
from plombery import get_logger, register_pipeline, task

from ...utils._db import SessionLocal
from ...utils.models import Input
from ...utils.hf_storage import download_from_hf
from ...utils.service import tirrger_flow, update_input_progress_async
from .common import WorkspaceParams, workspace_paths


LEGEND_SOURCE_PATH = Path("/app/src/data/legend_class_geo.csv")
COLORS_SOURCE_PATH = Path("/app/src/data/colors.csv")


@task
async def setup_workspace(params: WorkspaceParams):
    logger = get_logger()
    upload_uuid = params.uuid
    workspace_dir, data_dir, input_png = workspace_paths(upload_uuid)
    data_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        db_input = db.get(Input, upload_uuid)
        if not db_input:
            raise ValueError(f"Upload not found for uuid={upload_uuid}")
        image_bytes = download_from_hf(db_input.image_ref)
    finally:
        db.close()

    def _save_png() -> None:
        try:
            with Image.open(BytesIO(image_bytes)) as uploaded_image:
                uploaded_image.convert("RGBA").save(input_png, format="PNG")
        except UnidentifiedImageError as exc:
            raise ValueError(
                f"Stored upload is not a valid image for uuid={upload_uuid}"
            ) from exc

    await asyncio.to_thread(_save_png)
    await update_input_progress_async(upload_uuid, 1)

    logger.info("Workspace prepared at %s", workspace_dir)
    return {
        "uuid": upload_uuid,
        "workspace": str(workspace_dir),
        "data_dir": str(data_dir),
        "input_png": str(input_png),
    }


@task
async def init_legend(params: WorkspaceParams):
    logger = get_logger()
    upload_uuid = params.uuid
    _, data_dir, _ = workspace_paths(upload_uuid)
    data_dir.mkdir(parents=True, exist_ok=True)

    if not LEGEND_SOURCE_PATH.exists():
        raise FileNotFoundError(f"Legend source file not found at {LEGEND_SOURCE_PATH}")
    if not COLORS_SOURCE_PATH.exists():
        raise FileNotFoundError(f"Colors source file not found at {COLORS_SOURCE_PATH}")

    legend_target_path = data_dir / "legend_class_geo.csv"
    colors_target_path = data_dir / "colors.csv"
    await asyncio.to_thread(shutil.copy2, LEGEND_SOURCE_PATH, legend_target_path)
    await asyncio.to_thread(shutil.copy2, COLORS_SOURCE_PATH, colors_target_path)
    trigger_result = await asyncio.to_thread(tirrger_flow, "1_georef", upload_uuid)

    logger.info(
        "Workspace data initialized at %s (legend=%s, colors=%s)",
        data_dir,
        legend_target_path.name,
        colors_target_path.name,
    )
    return {
        "uuid": upload_uuid,
        "legend_csv": str(legend_target_path),
        "colors_csv": str(colors_target_path),
        "next": "1_georef",
        "trigger": trigger_result,
    }


register_pipeline(
    id="0_setup_workspace",
    description="Create /tmp/<uuid>/data and export DB input image as PNG.",
    tasks=[setup_workspace, init_legend],
    params=WorkspaceParams,
)
