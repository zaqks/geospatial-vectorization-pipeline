#!/usr/bin/env python
# coding: utf-8

import os
import numpy as np
import pandas as pd
from tqdm import tqdm

import rasterio
from rasterio.features import shapes, rasterize
from rasterio.transform import Affine

import geopandas as gpd
from shapely.geometry import shape

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

print(f"Loaded {len(rgb_to_class)} classes")

# -------------------------
# READ RASTER
# -------------------------
with rasterio.open(raster_path) as src:
    img = src.read()[:3]
    transform = src.transform
    crs = src.crs
    meta = src.meta.copy()

img = np.transpose(img, (1, 2, 0)).astype(np.uint8)
h, w, _ = img.shape

print("Raster shape:", img.shape)

# -------------------------
# ENCODE RGB -> INT LABEL
# -------------------------
flat = img.reshape(-1, 3)

rgb_int = (
    flat[:, 0].astype(np.int32) << 16 |
    flat[:, 1].astype(np.int32) << 8 |
    flat[:, 2].astype(np.int32)
)

class_map = {
    (r << 16 | g << 8 | b): i
    for i, ((r, g, b), _) in enumerate(rgb_to_class.items())
}

classes = list(rgb_to_class.values())

label = np.full(rgb_int.shape, -1, dtype=np.int32)

for rgb_key, idx in class_map.items():
    label[rgb_int == rgb_key] = idx

label = label.reshape(h, w)

print(f"Classes found: {len(classes)}")

# -------------------------
# VECTORIZE ONCE
# -------------------------
print("Vectorizing raster...")

results = {c: [] for c in classes}

for geom, val in shapes(label, mask=label != -1, transform=transform):
    val = int(val)
    if val == -1:
        continue
    results[classes[val]].append(shape(geom))

# -------------------------
# EXPORT GEOJSONS
# -------------------------
print("Exporting GeoJSONs...")

for class_name, geoms in tqdm(results.items()):
    if not geoms:
        continue

    gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
    gdf["class"] = class_name

    if EXPORT_TO_WGS84:
        gdf = gdf.to_crs("EPSG:4326")

    out_path = os.path.join(output_dir, f"{class_name}.geojson")
    gdf.to_file(out_path, driver="GeoJSON")

# -------------------------
# FAST PNG RASTER OVERLAYS (FIXED APPROACH)
# -------------------------
print("Creating per-class PNG overlays (rasterized)...")

base_img = img  # already numpy RGB

for class_name, geoms in tqdm(results.items()):
    if not geoms:
        continue

    # rasterize polygons directly into image grid
    mask = rasterize(
        [(geom, 1) for geom in geoms],
        out_shape=(h, w),
        transform=transform,
        fill=0,
        dtype=np.uint8
    )

    # build red overlay
    overlay = np.zeros_like(base_img)
    overlay[mask == 1] = [255, 0, 0]

    # blend (numpy, fast)
    alpha = 0.4
    final = (base_img * (1 - alpha) + overlay * alpha).astype(np.uint8)

    out_png = os.path.join(output_dir, f"{class_name}.png")

    from PIL import Image
    Image.fromarray(final).save(out_png)

print("\n✅ DONE — vector + raster pipeline complete")