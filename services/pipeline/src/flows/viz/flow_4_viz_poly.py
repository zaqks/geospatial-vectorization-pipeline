import asyncio
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from plombery import get_logger, register_pipeline, task
from rasterio.features import rasterize

from ..workspace.common import WorkspaceParams, run_gc_cleanup, workspace_paths
from ...utils.service import notify_api_progress, tirrger_flow, update_input_progress

INPUT_TIFF_PATH = Path("data/georef.tif")
INPUT_LEGEND_PATH = Path("data/legend_class_geo.csv")
INPUT_COLORS_PATH = Path("data/colors.csv")
INPUT_GEOJSON_DIR = Path("output/vect/poly")
OUTPUT_VIZ_DIR = Path("viz")



def _save_mask_png(rgba: np.ndarray, output_path: Path) -> None:
    height, width = rgba.shape[:2]
    resized_size = (max(1, width // 2), max(1, height // 2))
    resampling = getattr(Image, "Resampling", Image).NEAREST
    Image.fromarray(rgba).resize(resized_size, resample=resampling).save(
        output_path,
        format="PNG",
        optimize=True,
        compress_level=9,
    )



def _load_palette(colors_path: Path) -> list[tuple[int, int, int]]:
    df = pd.read_csv(colors_path).dropna(subset=["r", "g", "b"])
    palette = []
    for _, row in df.iterrows():
        rgb = (int(row["r"]), int(row["g"]), int(row["b"]))

        palette.append(rgb)
    if not palette:
        raise ValueError(f"No usable colors found in {colors_path}")
    return palette


def _load_class_z_map(legend_path: Path) -> dict[str, int]:
    df = pd.read_csv(legend_path).dropna(subset=["class", "z"])
    class_z_map = {str(row["class"]): int(row["z"]) for _, row in df.iterrows()}
    if not class_z_map:
        raise ValueError(f"No usable legend classes found in {legend_path}")
    return class_z_map


@task
async def viz_poly_masks(params: WorkspaceParams):
    logger = get_logger()
    upload_uuid = params.uuid
    workspace_dir, _, _ = workspace_paths(upload_uuid)

    input_tiff_path = workspace_dir / INPUT_TIFF_PATH
    input_legend_path = workspace_dir / INPUT_LEGEND_PATH
    input_colors_path = workspace_dir / INPUT_COLORS_PATH
    input_geojson_dir = workspace_dir / INPUT_GEOJSON_DIR
    output_viz_dir = workspace_dir / OUTPUT_VIZ_DIR

    def _run() -> dict:
        logger.info(
            "[viz-poly] Starting polygon visualization masks for uuid=%s", upload_uuid
        )
        output_viz_dir.mkdir(parents=True, exist_ok=True)

        palette = _load_palette(input_colors_path)
        class_z_map = _load_class_z_map(input_legend_path)
        geojson_files = sorted(input_geojson_dir.glob("*.geojson"))
        if not geojson_files:
            logger.info(
                "[viz-poly] No polygon GeoJSON files found under %s", input_geojson_dir
            )
            update_input_progress(upload_uuid, 95)
            notify_api_progress(
                upload_uuid,
                task="4_viz_poly.viz_poly_masks",
                status_percent=95,
            )
            trigger_result = tirrger_flow("5_export_output", upload_uuid)
            return {
                "uuid": upload_uuid,
                "mask_count": 0,
                "next": "5_export_output",
                "trigger": trigger_result,
            }

        with rasterio.open(input_tiff_path) as src:
            transform = src.transform
            crs = src.crs
            height, width = src.height, src.width

        mask_count = 0
        for index, geojson_path in enumerate(geojson_files):
            gdf = gpd.read_file(geojson_path)
            gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]
            if gdf.empty:
                continue

            if gdf.crs != crs:
                gdf = gdf.to_crs(crs)

            mask = rasterize(
                [(geom, 1) for geom in gdf.geometry],
                out_shape=(height, width),
                transform=transform,
                fill=0,
                dtype=np.uint8,
            )
            if mask.sum() == 0:
                continue

            rgba = np.zeros((height, width, 4), dtype=np.uint8)
            color = palette[index % len(palette)]
            rgba[mask == 1] = [color[0], color[1], color[2], 255]

            class_name = geojson_path.stem
            z_index = class_z_map.get(class_name)
            if z_index is None:
                raise ValueError(f"No legend z value found for class '{class_name}'")

            output_name = f"{z_index}_{class_name}_mask.png"
            output_path = output_viz_dir / output_name
            _save_mask_png(rgba, output_path)
            mask_count += 1

        update_input_progress(upload_uuid, 95)
        notify_api_progress(
            upload_uuid,
            task="4_viz_poly.viz_poly_masks",
            status_percent=95,
        )
        logger.info(
            "[viz-poly] Generated %s polygon masks in %s", mask_count, output_viz_dir
        )
        trigger_result = tirrger_flow("5_export_output", upload_uuid)
        return {
            "uuid": upload_uuid,
            "mask_count": mask_count,
            "next": "5_export_output",
            "trigger": trigger_result,
        }

    try:
        return await asyncio.to_thread(_run)
    finally:
        run_gc_cleanup("viz-poly", upload_uuid)


register_pipeline(
    id="4_viz_poly",
    description="Generate polygon layer PNG masks in /tmp/<uuid>/viz before export.",
    tasks=[viz_poly_masks],
    params=WorkspaceParams,
)
