import gc
import os
from pathlib import Path

import cv2
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from plombery import register_pipeline, task
from rasterio.features import rasterize, shapes
from scipy.spatial import KDTree
from shapely.geometry import LineString, shape
from skimage.morphology import skeletonize

from ..workspace.common import WorkspaceParams, workspace_paths
from ...utils.service import tirrger_flow, update_input_progress

INPUT_RASTER_PATH = Path("data/georef.tif")
INPUT_LEGEND_PATH = Path("data/legend_class_geo.csv")
OUTPUT_DIR = Path("output/vect/line")

TARGET_CLASS = "railway"
COLOR_TOLERANCE = 3
BRIDGE_RADIUS = 100
NOISE_RADIUS = 2
MIN_LINE_LENGTH_M = 1
SIMPLIFY_TOLERANCE = 1
EXPORT_TO_WGS84 = True
ENDPOINT_SEARCH_RADIUS_M = 50


@task
async def vectorize_dotted(params: WorkspaceParams):
    upload_uuid = params.uuid
    workspace_dir, _, _ = workspace_paths(upload_uuid)

    os.chdir(workspace_dir)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(INPUT_LEGEND_PATH)
        rail_row = df.loc[df["class"] == TARGET_CLASS].iloc[0]

        def hex_to_rgb(h: str) -> np.ndarray:
            h = h.lstrip("#")
            return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.uint8)

        rgb_val = hex_to_rgb(rail_row["hex"])
        lower_b = np.clip(rgb_val - COLOR_TOLERANCE, 0, 255)
        upper_b = np.clip(rgb_val + COLOR_TOLERANCE, 0, 255)

        with rasterio.open(INPUT_RASTER_PATH) as src:
            img = src.read((1, 2, 3))
            transform = src.transform
            crs = src.crs
            h, w = src.height, src.width

        img = np.moveaxis(img, 0, -1)
        mask = cv2.inRange(img, lower_b, upper_b)
        if not mask.any():
            update_input_progress(upload_uuid, 40)
            trigger_result = tirrger_flow("2_vectorization_poly", upload_uuid)
            return {
                "uuid": upload_uuid,
                "railway_found": False,
                "next": "2_vectorization_poly",
                "trigger": trigger_result,
            }

        open_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (NOISE_RADIUS * 2 + 1, NOISE_RADIUS * 2 + 1),
        )
        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (BRIDGE_RADIUS, BRIDGE_RADIUS))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)
        skeleton = skeletonize(mask > 0).astype(np.uint8)

        lines = []
        for geom, _ in shapes(skeleton, mask=skeleton, transform=transform):
            g = shape(geom)
            if g.geom_type == "LineString":
                lines.append(g)
            elif g.geom_type == "MultiLineString":
                lines.extend(g.geoms)
            elif g.geom_type in ("Polygon", "MultiPolygon"):
                lines.append(g.exterior)

        kernel = np.array(
            [[1, 1, 1], [1, 0, 1], [1, 1, 1]],
            dtype=np.uint8,
        )
        neighbors = cv2.filter2D(skeleton, -1, kernel)
        endpoints = np.argwhere((skeleton == 1) & (neighbors == 1))

        if len(endpoints) > 0:
            rows, cols = endpoints[:, 0], endpoints[:, 1]
            xs, ys = rasterio.transform.xy(transform, rows, cols)
            end_xy = np.column_stack([xs, ys])

            if len(end_xy) > 1:
                tree = KDTree(end_xy)
                pairs = tree.query_pairs(r=ENDPOINT_SEARCH_RADIUS_M)

                used = set()
                for i, j in pairs:
                    if i in used or j in used:
                        continue
                    lines.append(LineString([end_xy[i], end_xy[j]]))
                    used.add(i)
                    used.add(j)

        gdf = gpd.GeoDataFrame({"geometry": lines}, crs=crs)
        if not gdf.empty:
            gdf["length_m"] = gdf.length
            gdf = gdf[gdf["length_m"] >= MIN_LINE_LENGTH_M]
            gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
            gdf["class"] = TARGET_CLASS

            if EXPORT_TO_WGS84:
                gdf = gdf.to_crs("EPSG:4326")

            out_geojson = OUTPUT_DIR / f"{TARGET_CLASS}.geojson"
            gdf.to_file(out_geojson, driver="GeoJSON")

            gdf_r = gdf.to_crs(crs)
            debug_mask = rasterize(
                [(geom, 1) for geom in gdf_r.geometry],
                out_shape=(h, w),
                transform=transform,
                fill=0,
                dtype=np.uint8,
            )
            out_img = np.zeros((h, w, 3), dtype=np.uint8)
            out_img[debug_mask == 1] = (255, 0, 0)
            Image.fromarray(out_img).save(OUTPUT_DIR / f"{TARGET_CLASS}.png")

        update_input_progress(upload_uuid, 40)
        trigger_result = tirrger_flow("2_vectorization_poly", upload_uuid)
        return {
            "uuid": upload_uuid,
            "railway_found": not gdf.empty,
            "next": "2_vectorization_poly",
            "trigger": trigger_result,
        }
    finally:
        gc.collect()


register_pipeline(
    id="2_vectorization_dotted",
    description="Vectorize dotted/railway line class.",
    tasks=[vectorize_dotted],
    params=WorkspaceParams,
)
