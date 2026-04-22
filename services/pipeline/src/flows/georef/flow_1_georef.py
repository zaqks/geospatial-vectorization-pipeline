import math
import asyncio
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from plombery import get_logger, register_pipeline, task
from rasterio.transform import from_bounds

from ..workspace.common import WorkspaceParams, run_gc_cleanup, workspace_paths
from ...utils.service import (
    get_input_georef_bounds,
    tirrger_flow,
    update_input_progress_async,
)

INPUT_IMAGE_PATH = Path("data/input.png")
OUTPUT_TIF_PATH = Path("data/georef.tif")

R = 6378137.0


@task
async def georef_main(params: WorkspaceParams):
    logger = get_logger()
    upload_uuid = params.uuid
    workspace_dir, _, _ = workspace_paths(upload_uuid)
    logger.info("Running georef in workspace %s", workspace_dir)

    input_image_path = workspace_dir / INPUT_IMAGE_PATH
    output_tif_path = workspace_dir / OUTPUT_TIF_PATH

    try:
        output_tif_path.parent.mkdir(parents=True, exist_ok=True)

        bounds = await asyncio.to_thread(get_input_georef_bounds, upload_uuid)
        if not bounds:
            raise ValueError(f"No input row found for uuid={upload_uuid}")

        south, north = sorted((bounds.lat1, bounds.lat2))
        west, east = sorted((bounds.lng1, bounds.lng2))

        def lon_to_x(lon: float) -> float:
            return R * math.radians(lon)

        def lat_to_y(lat: float) -> float:
            return R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

        min_x = lon_to_x(west)
        max_x = lon_to_x(east)
        min_y = lat_to_y(south)
        max_y = lat_to_y(north)

        def _render_geotiff() -> None:
            with Image.open(input_image_path).convert("RGB") as img:
                img_np = np.array(img)

            height, width, _ = img_np.shape
            transform = from_bounds(min_x, min_y, max_x, max_y, width, height)

            with rasterio.open(
                output_tif_path,
                "w",
                driver="GTiff",
                height=height,
                width=width,
                count=3,
                dtype=img_np.dtype,
                crs="EPSG:3857",
                transform=transform,
                compress="DEFLATE",
                predictor=2,
                tiled=True,
                blockxsize=256,
                blockysize=256,
            ) as dst:
                dst.write(img_np[:, :, 0], 1)
                dst.write(img_np[:, :, 1], 2)
                dst.write(img_np[:, :, 2], 3)

        await asyncio.to_thread(_render_geotiff)

        await update_input_progress_async(upload_uuid, 10)
        trigger_result = await asyncio.to_thread(
            tirrger_flow, "2_vectorization_line", upload_uuid
        )

        return {
            "uuid": upload_uuid,
            "output_tif": str(output_tif_path),
            "next": "2_vectorization_line",
            "trigger": trigger_result,
        }
    finally:
        run_gc_cleanup("georef", upload_uuid)


register_pipeline(
    id="1_georef",
    description="Georeference input map into a common GeoTIFF.",
    tasks=[georef_main],
    params=WorkspaceParams,
)
