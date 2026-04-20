#!/usr/bin/env python
# coding: utf-8

import os
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from tqdm import tqdm
from skimage.morphology import skeletonize
from shapely.geometry import LineString
import networkx as nx
from rasterio.features import rasterize
from PIL import Image

# -------------------------
# CONFIG
# -------------------------
raster_path = "data/el_harrach_georef.tif"
output_dir = "output/vect/line"

os.makedirs(output_dir, exist_ok=True)

COLOR_TOLERANCE = 1
EXPORT_TO_WGS84 = True

# SAME DIRECTORY FOR EVERYTHING
geojson_dir = output_dir
debug_dir = output_dir

# -------------------------
# LEGEND
# -------------------------
df = pd.read_csv("data/legend_class_geo.csv")
df = df[df["geometry"] == "line"]

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16)
    )

color_class_map = {
    hex_to_rgb(row["hex"]): row["class"]
    for _, row in df.iterrows()
}

print(f"Loaded {len(color_class_map)} line classes")

# -------------------------
# READ RASTER
# -------------------------
with rasterio.open(raster_path) as src:
    img = src.read()
    transform = src.transform
    crs = src.crs
    h, w = src.height, src.width

img_np = np.transpose(img, (1, 2, 0))[:, :, :3].astype(np.int16)

print("Raster loaded:", img_np.shape)

# -------------------------
# SKELETON → GRAPH → LINES
# -------------------------
def skeleton_to_lines_graph(skel):
    G = nx.Graph()

    neighbors = [(-1,-1), (-1,0), (-1,1),
                 (0,-1),         (0,1),
                 (1,-1), (1,0), (1,1)]

    ys, xs = np.where(skel)

    for y, x in zip(ys, xs):
        for dy, dx in neighbors:
            ny, nx_ = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx_ < w and skel[ny, nx_]:
                G.add_edge((x, y), (nx_, ny))

    lines = []
    for comp in nx.connected_components(G):
        sub = G.subgraph(comp)
        start = list(sub.nodes())[0]
        path = list(nx.dfs_preorder_nodes(sub, start))

        if len(path) >= 2:
            lines.append(LineString(path))

    return lines

# -------------------------
# PROCESS EACH CLASS
# -------------------------
for rgb, class_name in tqdm(color_class_map.items(), desc="Processing classes"):

    target = np.array(rgb, dtype=np.int16)

    # MASK
    mask = np.all(np.abs(img_np - target) <= COLOR_TOLERANCE, axis=2)
    if not np.any(mask):
        continue

    # SKELETON
    skel = skeletonize(mask > 0)

    # VECTORIZE
    pixel_lines = skeleton_to_lines_graph(skel)
    if not pixel_lines:
        continue

    # PIXEL → GEO
    geo_lines = []
    for line in pixel_lines:
        coords = [transform * (x, y) for x, y in line.coords]
        if len(coords) >= 2:
            geo_lines.append(LineString(coords))

    gdf = gpd.GeoDataFrame(geometry=geo_lines, crs=crs)
    gdf["class"] = class_name

    if EXPORT_TO_WGS84:
        gdf = gdf.to_crs("EPSG:4326")

    # SAVE GEOJSON (same folder as images)
    out_geojson = os.path.join(geojson_dir, f"{class_name}.geojson")
    gdf.to_file(out_geojson, driver="GeoJSON")

    # -------------------------
    # DEBUG PLOT (RED ON BLACK)
    # -------------------------
    gdf_for_raster = gdf.to_crs(crs)

    if not gdf_for_raster.empty:
        mask_raster = rasterize(
            [(geom, 1) for geom in gdf_for_raster.geometry],
            out_shape=(h, w),
            transform=transform,
            fill=0,
            dtype=np.uint8
        )

        out_img = np.zeros((h, w, 3), dtype=np.uint8)  # black background
        out_img[mask_raster == 1] = (255, 0, 0)        # red lines

        out_png = os.path.join(debug_dir, f"{class_name}.png")
        Image.fromarray(out_img).save(out_png)

    print(f"Saved: {class_name}")

print("DONE — GeoJSON + red-on-black debug images saved in same directory")