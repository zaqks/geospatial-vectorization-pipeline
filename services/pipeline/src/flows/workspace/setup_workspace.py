from io import BytesIO
from pathlib import Path
import shutil

from PIL import Image, UnidentifiedImageError
from plombery import get_logger, register_pipeline, task

from ...utils._db import SessionLocal
from ...utils.models import Input
from ...utils.service import tirrger_flow, update_input_progress
from .common import WorkspaceParams, workspace_paths


LEGEND_SOURCE_PATH = Path("/app/src/data/legend_class_geo.csv")


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
        image_bytes = db_input.image
    finally:
        db.close()

    try:
        with Image.open(BytesIO(image_bytes)) as uploaded_image:
            uploaded_image.convert("RGBA").save(input_png, format="PNG")
    except UnidentifiedImageError as exc:
        raise ValueError(f"Stored upload is not a valid image for uuid={upload_uuid}") from exc

    update_input_progress(upload_uuid, 1)

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

    legend_target_path = data_dir / "legend_class_geo.csv"
    shutil.copy2(LEGEND_SOURCE_PATH, legend_target_path)
    trigger_result = tirrger_flow("1_georef", upload_uuid)

    logger.info("Legend initialized at %s", legend_target_path)
    return {
        "uuid": upload_uuid,
        "legend_csv": str(legend_target_path),
        "next": "1_georef",
        "trigger": trigger_result,
    }


register_pipeline(
    id="setup_workspace",
    description="Create /tmp/<uuid>/data and export DB input image as PNG.",
    tasks=[setup_workspace, init_legend],
    params=WorkspaceParams,
)