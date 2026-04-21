from io import BytesIO

from PIL import Image, UnidentifiedImageError
from plombery import get_logger, register_pipeline, task

from ...utils._db import SessionLocal
from ...utils.models import Input
from ...utils.service import update_input_progress
from .common import WorkspaceParams, workspace_paths


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


register_pipeline(
    id="setup_workspace",
    description="Create /tmp/<uuid>/data and export DB input image as PNG.",
    tasks=[setup_workspace],
    params=WorkspaceParams,
)