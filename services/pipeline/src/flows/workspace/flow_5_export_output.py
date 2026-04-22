import asyncio
from pathlib import Path
import shutil

from plombery import get_logger, register_pipeline, task

from ...utils.service import (
    tirrger_flow,
    update_input_progress,
    upsert_output_archive_from_workspace_async,
)
from .common import WorkspaceParams, run_gc_cleanup, workspace_paths

WORKSPACE_OUTPUT_DIR = Path("output")
OUTPUT_ARCHIVE_NAME = "output.zip"


@task
async def zip_output(params: WorkspaceParams):
    logger = get_logger()
    upload_uuid = params.uuid
    workspace_dir, _, _ = workspace_paths(upload_uuid)
    workspace_output_dir = workspace_dir / WORKSPACE_OUTPUT_DIR
    archive_path = workspace_dir / OUTPUT_ARCHIVE_NAME

    if not workspace_output_dir.exists():
        raise FileNotFoundError(
            f"Workspace output directory not found: {workspace_output_dir}"
        )

    await asyncio.to_thread(
        shutil.make_archive,
        str(archive_path.with_suffix("")),
        "zip",
        workspace_dir,
        str(WORKSPACE_OUTPUT_DIR),
    )

    logger.info("[export] Created output archive at %s", archive_path)
    return {
        "uuid": upload_uuid,
        "archive": str(archive_path),
    }


@task
async def export_output(params: WorkspaceParams):
    logger = get_logger()
    upload_uuid = params.uuid
    workspace_dir, _, _ = workspace_paths(upload_uuid)
    workspace_output_dir = workspace_dir / WORKSPACE_OUTPUT_DIR
    archive_path = workspace_dir / OUTPUT_ARCHIVE_NAME

    async def _run() -> dict:
        logger.info("[export] Starting output export for uuid=%s", upload_uuid)
        export_result = await upsert_output_archive_from_workspace_async(
            upload_uuid,
            workspace_output_dir,
            archive_path,
        )

        update_input_progress(upload_uuid, 95)
        logger.info("[export] Progress updated to 95%%")

        trigger_result = tirrger_flow("6_clean_workspace", upload_uuid)
        return {
            "uuid": upload_uuid,
            "export": export_result,
            "next": "6_clean_workspace",
            "trigger": trigger_result,
        }

    try:
        return await _run()
    finally:
        run_gc_cleanup("export", upload_uuid)


register_pipeline(
    id="5_export_output",
    description="Create output archive and upload ZIP file to output DB records.",
    tasks=[zip_output, export_output],
    params=WorkspaceParams,
)
