#!/usr/bin/env python
# coding: utf-8

import os
import numpy as np
import pandas as pd
from tqdm import tqdm

import rasterio
from rasterio.features import shapes, rasterize

import geopandas as gpd
from shapely.geometry import shape

from PIL import Image

# -------------------------
# CONFIG
# -------------------------
raster_path = "data/el_harrach_georef.tif"
output_dir = "output/vect/poly"
os.makedirs(output_dir, exist_ok=True)

EXPORT_TO_WGS84 = True

# -------------------------
# LEGEND
# -------------------------
df = pd.read_csv("data/legend_class_geo.csv")
df = df[df.geometry == "polygon"]

def hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

rgb_to_class = {
    hex_to_rgb(row["hex"]): row["class"]
    for _, row in df.iterrows()
}

classes = list(rgb_to_class.values())

class_map = {
    (r << 16 | g << 8 | b): i
    for i, ((r, g, b), _) in enumerate(rgb_to_class.items())
}

# -------------------------
# READ RASTER
# -------------------------
with rasterio.open(raster_path) as src:
    img = src.read()[:3]
    transform = src.transform
    crs = src.crs

img = np.transpose(img, (1, 2, 0)).astype(np.uint8)
h, w, _ = img.shape

# -------------------------
# ENCODE RGB -> CLASS INDEX
# -------------------------
flat = img.reshape(-1, 3)

rgb_int = (
    flat[:, 0].astype(np.int32) << 16 |
    flat[:, 1].astype(np.int32) << 8 |
    flat[:, 2].astype(np.int32)
)

label = np.full(rgb_int.shape, -1, dtype=np.int32)

for rgb_key, idx in class_map.items():
    label[rgb_int == rgb_key] = idx

label = label.reshape(h, w)

# -------------------------
# VECTORIZE
# -------------------------
results = {c: [] for c in classes}

for geom, val in shapes(label, mask=label != -1, transform=transform):
    val = int(val)
    if val == -1:
        continue
    results[classes[val]].append(shape(geom))

# -------------------------
# EXPORT GEOJSONS
# -------------------------
for class_name, geoms in tqdm(results.items()):
    if not geoms:
        continue

    gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
    gdf["class"] = class_name

    if EXPORT_TO_WGS84:
        gdf = gdf.to_crs("EPSG:4326")

    gdf.to_file(os.path.join(output_dir, f"{class_name}.geojson"), driver="GeoJSON")

# -------------------------
# SIMPLE RED MASK PNG (NO ALPHA, NO BLENDING)
# -------------------------
for class_name, geoms in tqdm(results.items()):
    if not geoms:
        continue

    mask = rasterize(
        [(geom, 1) for geom in geoms],
        out_shape=(h, w),
        transform=transform,
        fill=0,
        dtype=np.uint8
    )

    out = np.zeros((h, w, 3), dtype=np.uint8)
    out[mask == 1] = [255, 0, 0]

    Image.fromarray(out).save(
        os.path.join(output_dir, f"{class_name}.png")
    )