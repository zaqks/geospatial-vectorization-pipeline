import gc
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from plombery import register_pipeline, task
from rasterio.features import rasterize, shapes
from shapely.geometry import shape
from tqdm import tqdm

from ..workspace.common import WorkspaceParams, workspace_paths
from ...utils.service import tirrger_flow, update_input_progress

INPUT_RASTER_PATH = Path("data/georef.tif")
INPUT_LEGEND_PATH = Path("data/legend_class_geo.csv")
OUTPUT_DIR = Path("output/vect/poly")
EXPORT_TO_WGS84 = True


@task
async def vectorize_poly(params: WorkspaceParams):
    upload_uuid = params.uuid
    workspace_dir, _, _ = workspace_paths(upload_uuid)

    os.chdir(workspace_dir)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(INPUT_LEGEND_PATH)
        df = df[df.geometry == "polygon"]

        def hex_to_rgb(h: str) -> tuple[int, int, int]:
            h = h.lstrip("#")
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

        rgb_to_class = {hex_to_rgb(row["hex"]): row["class"] for _, row in df.iterrows()}
        classes = list(rgb_to_class.values())

        class_map = {
            (r << 16 | g << 8 | b): i for i, ((r, g, b), _) in enumerate(rgb_to_class.items())
        }

        with rasterio.open(INPUT_RASTER_PATH) as src:
            img = src.read()[:3]
            transform = src.transform
            crs = src.crs

        img = np.transpose(img, (1, 2, 0)).astype(np.uint8)
        h, w, _ = img.shape

        flat = img.reshape(-1, 3)
        rgb_int = (
            flat[:, 0].astype(np.int32) << 16
            | flat[:, 1].astype(np.int32) << 8
            | flat[:, 2].astype(np.int32)
        )

        label = np.full(rgb_int.shape, -1, dtype=np.int32)
        for rgb_key, idx in class_map.items():
            label[rgb_int == rgb_key] = idx

        label = label.reshape(h, w)
        results = {c: [] for c in classes}

        for geom, val in shapes(label, mask=label != -1, transform=transform):
            val = int(val)
            if val == -1:
                continue
            results[classes[val]].append(shape(geom))

        for class_name, geoms in tqdm(results.items(), desc="Export polygon geojson"):
            if not geoms:
                continue

            gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
            gdf["class"] = class_name
            if EXPORT_TO_WGS84:
                gdf = gdf.to_crs("EPSG:4326")

            gdf.to_file(OUTPUT_DIR / f"{class_name}.geojson", driver="GeoJSON")

        for class_name, geoms in tqdm(results.items(), desc="Export polygon debug"):
            if not geoms:
                continue

            mask = rasterize(
                [(geom, 1) for geom in geoms],
                out_shape=(h, w),
                transform=transform,
                fill=0,
                dtype=np.uint8,
            )
            out = np.zeros((h, w, 3), dtype=np.uint8)
            out[mask == 1] = [255, 0, 0]
            Image.fromarray(out).save(OUTPUT_DIR / f"{class_name}.png")

        update_input_progress(upload_uuid, 55)
        trigger_result = tirrger_flow("3_clean_gapfill", upload_uuid)
        return {"uuid": upload_uuid, "next": "3_clean_gapfill", "trigger": trigger_result}
    finally:
        gc.collect()


register_pipeline(
    id="2_vectorization_poly",
    description="Vectorize polygon classes.",
    tasks=[vectorize_poly],
    params=WorkspaceParams,
)
