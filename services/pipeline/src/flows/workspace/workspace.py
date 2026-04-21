import shutil
from io import BytesIO
from pathlib import Path
from uuid import UUID

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, validator
from plombery import get_logger, register_pipeline, task

from ...utils._db import SessionLocal
from ...utils.models import Input


class WorkspaceParams(BaseModel):
    uuid: str = Field(..., alias="UUID")

    @validator("uuid")
    def validate_uuid(cls, value: str) -> str:
        return str(UUID(value))

    class Config:
        allow_population_by_field_name = True


def _workspace_paths(upload_uuid: str) -> tuple[Path, Path, Path]:
    workspace_dir = Path("/tmp") / upload_uuid
    data_dir = workspace_dir / "data"
    input_png = data_dir / "input.png"
    return workspace_dir, data_dir, input_png


@task
async def setup_workspace(params: WorkspaceParams):
    logger = get_logger()
    upload_uuid = params.uuid
    workspace_dir, data_dir, input_png = _workspace_paths(upload_uuid)
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

    logger.info("Workspace prepared at %s", workspace_dir)
    return {
        "uuid": upload_uuid,
        "workspace": str(workspace_dir),
        "data_dir": str(data_dir),
        "input_png": str(input_png),
    }


@task
async def clean_workspace(params: WorkspaceParams):
    logger = get_logger()
    upload_uuid = params.uuid
    workspace_dir, _, _ = _workspace_paths(upload_uuid)

    existed = workspace_dir.exists()
    if existed:
        shutil.rmtree(workspace_dir)

    logger.info("Workspace cleaned at %s (existed=%s)", workspace_dir, existed)
    return {
        "uuid": upload_uuid,
        "workspace": str(workspace_dir),
        "deleted": existed,
    }


register_pipeline(
    id="setup_workspace",
    description="Create /tmp/<uuid>/data and export DB input image as PNG.",
    tasks=[setup_workspace],
    params=WorkspaceParams,
)


register_pipeline(
    id="clean_workspace",
    description="Delete /tmp/<uuid> workspace folder.",
    tasks=[clean_workspace],
    params=WorkspaceParams,
)
