import asyncio
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from plombery import get_logger, register_pipeline, task
from rasterio.features import shapes
from shapely.geometry import shape
from skimage.morphology import closing, disk, remove_small_objects, skeletonize
from tqdm import tqdm

from ..workspace.common import WorkspaceParams, run_gc_cleanup, workspace_paths
from ...utils.service import notify_api_progress, tirrger_flow, update_input_progress

INPUT_RASTER_PATH = Path("data/georef.tif")
INPUT_LEGEND_PATH = Path("data/legend_class_geo.csv")
OUTPUT_DIR = Path("output/vect/line")

COLOR_TOLERANCE = 1
CLOSING_RADIUS = 5
MIN_OBJECT_SIZE_M2 = 500
MIN_LINE_LENGTH = 2
SIMPLIFY_TOLERANCE = 0.3
EXPORT_TO_WGS84 = True


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


@task
async def vectorize_line(params: WorkspaceParams):
    logger = get_logger()
    upload_uuid = params.uuid
    workspace_dir, _, _ = workspace_paths(upload_uuid)

    input_raster_path = workspace_dir / INPUT_RASTER_PATH
    input_legend_path = workspace_dir / INPUT_LEGEND_PATH
    output_dir = workspace_dir / OUTPUT_DIR

    def _run() -> dict:
        logger.info("[line] Starting line vectorization for uuid=%s", upload_uuid)
        output_dir.mkdir(parents=True, exist_ok=True)

        df = pd.read_csv(input_legend_path)
        df = df[(df["geometry"] == "line") & (df["class"] != "railway")]
        color_class_map = {hex_to_rgb(row["hex"]): row["class"] for _, row in df.iterrows()}
        logger.info("[line] Found %s line classes to process", len(color_class_map))

        with rasterio.open(input_raster_path) as src:
            img = src.read()
            transform = src.transform
            crs = src.crs
            h, w = src.height, src.width
            pixel_area = abs(transform[0] * transform[4])
            min_object_pixels = int(MIN_OBJECT_SIZE_M2 / pixel_area)

        img_np = np.transpose(img, (1, 2, 0))[:, :, :3].astype(np.int16)

        for rgb, class_name in tqdm(color_class_map.items(), desc="Processing line classes"):
            target = np.array(rgb, dtype=np.int16)
            mask = np.all(np.abs(img_np - target) <= COLOR_TOLERANCE, axis=2)
            if not np.any(mask):
                continue

            cleaned_mask = closing(mask, disk(CLOSING_RADIUS))
            if min_object_pixels > 0:
                cleaned_mask = remove_small_objects(cleaned_mask, min_size=min_object_pixels)

            skeleton = skeletonize(cleaned_mask).astype(np.uint8)

            results = (
                {"properties": {"raster_val": v}, "geometry": s}
                for s, v in shapes(skeleton, mask=skeleton > 0, transform=transform)
            )

            line_geoms = []
            for g in results:
                poly_shape = shape(g["geometry"])
                if poly_shape.geom_type == "Polygon":
                    line_geoms.append(poly_shape.exterior)
                elif poly_shape.geom_type == "MultiPolygon":
                    for part in poly_shape.geoms:
                        line_geoms.append(part.exterior)

            if not line_geoms:
                continue

            gdf = gpd.GeoDataFrame(geometry=line_geoms, crs=crs)
            gdf["geometry"] = gdf.simplify(tolerance=SIMPLIFY_TOLERANCE, preserve_topology=True)
            gdf = gdf[gdf.length > MIN_LINE_LENGTH]
            gdf["class"] = class_name

            if EXPORT_TO_WGS84:
                gdf = gdf.to_crs("EPSG:4326")
            
            out_geojson = output_dir / f"{class_name}.geojson"
            gdf.to_file(out_geojson, driver="GeoJSON")
            logger.info(
                "[line] Exported %s with %s features to %s",
                class_name,
                len(gdf),
                out_geojson,
            )

            # gdf_for_raster = gdf.to_crs(crs)
            # if not gdf_for_raster.empty:
            #     debug_mask = rasterize(
            #         [(geom, 1) for geom in gdf_for_raster.geometry],
            #         out_shape=(h, w),
            #         transform=transform,
            #         fill=0,
            #         dtype=np.uint8,
            #     )
            #     out_img = np.zeros((h, w, 3), dtype=np.uint8)
            #     out_img[debug_mask == 1] = (255, 0, 0)
            #     Image.fromarray(out_img).save(output_dir / f"{class_name_safe}.png")

        update_input_progress(upload_uuid, 25)
        notify_api_progress(
            upload_uuid,
            task="2_vectorization_line.vectorize_line",
            status_percent=25,
        )
        logger.info("[line] Progress updated to 25%%")
        trigger_result = tirrger_flow("2_vectorization_dotted", upload_uuid)
        return {"uuid": upload_uuid, "next": "2_vectorization_dotted", "trigger": trigger_result}

    try:
        return await asyncio.to_thread(_run)
    finally:
        run_gc_cleanup("line", upload_uuid)


register_pipeline(
    id="2_vectorization_line",
    description="Vectorize non-railway line classes.",
    tasks=[vectorize_line],
    params=WorkspaceParams,
)
