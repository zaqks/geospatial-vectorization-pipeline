import gc
import asyncio
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image
from plombery import register_pipeline, task
from rasterio.features import rasterize
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from ..workspace.common import WorkspaceParams, workspace_paths
from ...utils.service import tirrger_flow, update_input_progress

INPUT_GEOJSON_PATH = Path("output/vect/poly/water.geojson")
OUTPUT_GEOJSON_PATH = Path("output/vect/poly/water.geojson")
# OUTPUT_MASK_PATH = Path("output/vect/poly/water.png")
REFERENCE_RASTER_PATH = Path("data/georef.tif")

BUFFER_DIST = 20
SIMPLIFY_TOL = 0.5


def remove_holes(geom):
    if isinstance(geom, Polygon):
        return Polygon(geom.exterior)
    if isinstance(geom, MultiPolygon):
        return MultiPolygon([Polygon(p.exterior) for p in geom.geoms])
    return geom


@task
async def clean_gapfill(params: WorkspaceParams):
    upload_uuid = params.uuid
    workspace_dir, _, _ = workspace_paths(upload_uuid)

    input_geojson_path = workspace_dir / INPUT_GEOJSON_PATH
    output_geojson_path = workspace_dir / OUTPUT_GEOJSON_PATH
    # output_mask_path = workspace_dir / OUTPUT_MASK_PATH
    reference_raster_path = workspace_dir / REFERENCE_RASTER_PATH

    def _run() -> dict:
        output_geojson_path.parent.mkdir(parents=True, exist_ok=True)

        gdf = gpd.read_file(input_geojson_path)
        if gdf.empty:
            raise ValueError(f"GeoJSON is empty: {input_geojson_path}")

        with rasterio.open(reference_raster_path) as src:
            transform = src.transform
            h, w = src.height, src.width
            raster_crs = src.crs
            raster_bounds = src.bounds

        if gdf.crs is None:
            raise ValueError("Input GeoJSON has no CRS")
        if gdf.crs != raster_crs:
            gdf = gdf.to_crs(raster_crs)

        vxmin, vymin, vxmax, vymax = gdf.total_bounds
        rxmin, rymin, rxmax, rymax = raster_bounds
        overlap = not (vxmax < rxmin or vxmin > rxmax or vymax < rymin or vymin > rymax)
        if not overlap:
            raise ValueError("Vector and raster do not overlap")

        merged = unary_union(gdf.geometry)
        filled = merged.buffer(BUFFER_DIST).buffer(-BUFFER_DIST)
        if filled.is_empty:
            raise ValueError("Geometry became empty after buffering")

        filled = remove_holes(filled)
        if filled.is_empty:
            raise ValueError("Geometry empty after hole removal")

        filled = filled.simplify(SIMPLIFY_TOL)
        if filled.is_empty:
            raise ValueError("Geometry empty after simplify")

        out_gdf = gpd.GeoDataFrame(geometry=[filled], crs=gdf.crs)
        out_gdf["class"] = "water"
        out_gdf.to_file(output_geojson_path, driver="GeoJSON")

        # mask = rasterize(
        #     [(filled, 1)],
        #     out_shape=(h, w),
        #     transform=transform,
        #     fill=0,
        #     dtype=np.uint8,
        # )
        # if mask.sum() == 0:
        #     raise ValueError("Empty mask after rasterize")
        #
        # out = np.zeros((h, w, 3), dtype=np.uint8)
        # out[mask == 1] = [255, 0, 0]
        # Image.fromarray(out).save(output_mask_path)

        update_input_progress(upload_uuid, 70)
        trigger_result = tirrger_flow("3_clean_noise_poly", upload_uuid)
        return {"uuid": upload_uuid, "next": "3_clean_noise_poly", "trigger": trigger_result}

    try:
        return await asyncio.to_thread(_run)
    finally:
        gc.collect()


register_pipeline(
    id="3_clean_gapfill",
    description="Gap-fill and clean the water polygon.",
    tasks=[clean_gapfill],
    params=WorkspaceParams,
)
