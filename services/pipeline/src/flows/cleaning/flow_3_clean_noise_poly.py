import gc
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image
from plombery import register_pipeline, task
from rasterio.features import rasterize
from shapely.validation import make_valid
from tqdm import tqdm

from ..workspace.common import WorkspaceParams, workspace_paths
from ...utils.service import tirrger_flow, update_input_progress

INPUT_FOLDER = Path("output/vect/poly")
OUTPUT_FOLDER = Path("output/vect/poly")
REFERENCE_RASTER_PATH = Path("data/georef.tif")
MIN_AREA_M2 = 1


def clean_geometry(gdf: gpd.GeoDataFrame, min_area_m2: float) -> gpd.GeoDataFrame:
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]
    gdf["geometry"] = gdf["geometry"].apply(lambda g: make_valid(g) if not g.is_valid else g)
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]

    original_crs = gdf.crs
    gdf_metric = gdf.to_crs(epsg=3857)
    gdf_metric["area"] = gdf_metric.geometry.area
    gdf_metric = gdf_metric[gdf_metric["area"] >= min_area_m2]
    gdf_metric = gdf_metric.drop(columns=["area"])

    gdf = gdf_metric.to_crs(original_crs)
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]
    return gdf


def clean_and_debug_vector(
    geojson_path: Path,
    output_dir: Path,
    min_area_m2: float,
    reference_raster_path: Path,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = geojson_path.stem

    gdf = gpd.read_file(geojson_path)
    if gdf.empty:
        return

    gdf_cleaned = clean_geometry(gdf, min_area_m2)
    clean_geojson_path = output_dir / f"{base_name}.geojson"
    gdf_cleaned.to_file(clean_geojson_path, driver="GeoJSON")

    with rasterio.open(reference_raster_path) as src:
        h, w = src.height, src.width
        transform = src.transform
        raster_crs = src.crs

    gdf_for_raster = gdf_cleaned.to_crs(raster_crs)
    if not gdf_for_raster.empty:
        mask = rasterize(
            [(geom, 1) for geom in gdf_for_raster.geometry],
            out_shape=(h, w),
            transform=transform,
            fill=0,
            dtype=np.uint8,
        )
        out_img = np.zeros((h, w, 3), dtype=np.uint8)
        out_img[mask == 1] = [255, 0, 0]
        Image.fromarray(out_img).save(output_dir / f"{base_name}.png")


@task
async def clean_noise_poly(params: WorkspaceParams):
    upload_uuid = params.uuid
    workspace_dir, _, _ = workspace_paths(upload_uuid)

    os.chdir(workspace_dir)
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    try:
        geojson_files = list(INPUT_FOLDER.glob("*.geojson"))

        for geojson_path in tqdm(geojson_files, desc="Cleaning polygon geojson"):
            clean_and_debug_vector(
                geojson_path=geojson_path,
                output_dir=OUTPUT_FOLDER,
                min_area_m2=MIN_AREA_M2,
                reference_raster_path=REFERENCE_RASTER_PATH,
            )

        update_input_progress(upload_uuid, 90)
        trigger_result = tirrger_flow("clean_workspace", upload_uuid)
        return {"uuid": upload_uuid, "next": "clean_workspace", "trigger": trigger_result}
    finally:
        gc.collect()


register_pipeline(
    id="3_clean_noise_poly",
    description="Clean polygon noise and export debug masks.",
    tasks=[clean_noise_poly],
    params=WorkspaceParams,
)
