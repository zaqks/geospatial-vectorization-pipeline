#!/usr/bin/env python
# coding: utf-8

import os
import numpy as np
import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon
from rasterio.features import rasterize
from PIL import Image
import rasterio

# -------------------------
# CONFIG
# -------------------------
input_geojson = "output/clean/poly/water_cleaned.geojson"
output_geojson = "output/gapfill/water.geojson"
output_mask = "output/gapfill/water_filled.png"

reference_raster = "data/el_harrach_georef.tif"

BUFFER_DIST_PROJECTED = 2        # meters
BUFFER_DIST_GEO = 0.00001        # degrees
SIMPLIFY_PROJECTED = 0.5
SIMPLIFY_GEO = 0.000005

os.makedirs(os.path.dirname(output_geojson), exist_ok=True)

# -------------------------
# LOAD GEOJSON
# -------------------------
gdf = gpd.read_file(input_geojson)

if gdf.empty:
    raise ValueError("❌ GeoJSON is empty")

print("\n--- VECTOR INFO ---")
print("CRS:", gdf.crs)
print("Bounds:", gdf.total_bounds)

# -------------------------
# LOAD RASTER
# -------------------------
with rasterio.open(reference_raster) as src:
    transform = src.transform
    h, w = src.height, src.width
    raster_crs = src.crs
    raster_bounds = src.bounds

print("\n--- RASTER INFO ---")
print("CRS:", raster_crs)
print("Bounds:", raster_bounds)
print("Shape:", (h, w))

# -------------------------
# REPROJECT IF NEEDED
# -------------------------
if gdf.crs != raster_crs:
    print("\n⚠️ CRS mismatch → reprojecting vector to raster CRS")
    gdf = gdf.to_crs(raster_crs)

print("\n--- AFTER CRS ALIGNMENT ---")
print("Vector CRS:", gdf.crs)
print("Vector bounds:", gdf.total_bounds)

# -------------------------
# CHECK OVERLAP
# -------------------------
vxmin, vymin, vxmax, vymax = gdf.total_bounds
rxmin, rymin, rxmax, rymax = raster_bounds

overlap = not (vxmax < rxmin or vxmin > rxmax or vymax < rymin or vymin > rymax)

print("\n--- OVERLAP CHECK ---")
print("Overlap:", overlap)

if not overlap:
    raise ValueError("❌ Vector and raster DO NOT overlap → mask will be empty")

# -------------------------
# MERGE + FILL GAPS
# -------------------------
merged = unary_union(gdf.geometry)

# choose correct buffer depending on CRS
if gdf.crs.is_geographic:
    BUFFER_DIST = BUFFER_DIST_GEO
    SIMPLIFY_TOL = SIMPLIFY_GEO
    print("\nUsing geographic units (degrees)")
else:
    BUFFER_DIST = BUFFER_DIST_PROJECTED
    SIMPLIFY_TOL = SIMPLIFY_PROJECTED
    print("\nUsing projected units (meters)")

print(f"Buffer distance: {BUFFER_DIST}")

filled = merged.buffer(BUFFER_DIST).buffer(-BUFFER_DIST)

if filled.is_empty:
    raise ValueError("❌ Geometry became empty after buffering")

# -------------------------
# REMOVE HOLES
# -------------------------
def remove_holes(geom):
    if isinstance(geom, Polygon):
        return Polygon(geom.exterior)
    elif isinstance(geom, MultiPolygon):
        return MultiPolygon([Polygon(p.exterior) for p in geom.geoms])
    return geom

filled = remove_holes(filled)

# -------------------------
# SIMPLIFY
# -------------------------
filled = filled.simplify(SIMPLIFY_TOL)

if filled.is_empty:
    raise ValueError("❌ Geometry became empty after simplify")

# -------------------------
# SAVE GEOJSON
# -------------------------
out_gdf = gpd.GeoDataFrame(geometry=[filled], crs=gdf.crs)
out_gdf["class"] = "water"

out_gdf.to_file(output_geojson, driver="GeoJSON")
print(f"\n✅ Saved filled GeoJSON: {output_geojson}")

# -------------------------
# RASTERIZE
# -------------------------
print("\n--- RASTERIZING ---")

mask = rasterize(
    [(filled, 1)],
    out_shape=(h, w),
    transform=transform,
    fill=0,
    dtype=np.uint8
)

print("Mask sum (should be >0):", mask.sum())

if mask.sum() == 0:
    raise ValueError("❌ Mask is empty → something still wrong")

# -------------------------
# RED MASK PNG
# -------------------------
out = np.zeros((h, w, 3), dtype=np.uint8)
out[mask == 1] = [255, 0, 0]

Image.fromarray(out).save(output_mask)

print(f"✅ Saved mask PNG: {output_mask}")
print("\n🎯 Done successfully\n")