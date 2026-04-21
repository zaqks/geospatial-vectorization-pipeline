import shutil

from plombery import get_logger, register_pipeline, task

from ...utils.service import update_input_progress
from .common import WorkspaceParams, workspace_paths


@task
async def clean_workspace(params: WorkspaceParams):
    logger = get_logger()
    upload_uuid = params.uuid
    workspace_dir, _, _ = workspace_paths(upload_uuid)

    existed = workspace_dir.exists()
    if existed:
        shutil.rmtree(workspace_dir)

    update_input_progress(upload_uuid, 100)

    logger.info("Workspace cleaned at %s (existed=%s)", workspace_dir, existed)
    return {
        "uuid": upload_uuid,
        "workspace": str(workspace_dir),
        "deleted": existed,
    }


register_pipeline(
    id="5_clean_workspace",
    description="Delete /tmp/<uuid> workspace folder.",
    tasks=[clean_workspace],
    params=WorkspaceParams,
)