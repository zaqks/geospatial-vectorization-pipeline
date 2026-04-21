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
# CONFIG (PROJECTED CRS ONLY)
# -------------------------
input_geojson = "output/vect/poly/water.geojson"
output_geojson = "output/vect/poly/water.geojson"
output_mask = "output/vect/poly/water.png"

reference_raster = "data/el_harrach_georef.tif"

BUFFER_DIST = 20        # meters
SIMPLIFY_TOL = 0.5     # meters

os.makedirs(os.path.dirname(output_geojson), exist_ok=True)

# -------------------------
# LOAD VECTOR
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
# FORCE CRS ALIGNMENT
# -------------------------
if gdf.crs is None:
    raise ValueError("❌ Input GeoJSON has no CRS")

if gdf.crs != raster_crs:
    print("\n⚠️ Reprojecting vector to raster CRS...")
    gdf = gdf.to_crs(raster_crs)

print("\n--- AFTER REPROJECTION ---")
print("CRS:", gdf.crs)
print("Bounds:", gdf.total_bounds)

# -------------------------
# OVERLAP CHECK
# -------------------------
vxmin, vymin, vxmax, vymax = gdf.total_bounds
rxmin, rymin, rxmax, rymax = raster_bounds

overlap = not (
    vxmax < rxmin or vxmin > rxmax or
    vymax < rymin or vymin > rymax
)

print("\n--- OVERLAP CHECK ---")
print("Overlap:", overlap)

if not overlap:
    raise ValueError("❌ Vector and raster do NOT overlap")

# -------------------------
# MERGE + FILL GAPS
# -------------------------
merged = unary_union(gdf.geometry)

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

if filled.is_empty:
    raise ValueError("❌ Geometry empty after hole removal")

# -------------------------
# SIMPLIFY
# -------------------------
filled = filled.simplify(SIMPLIFY_TOL)

if filled.is_empty:
    raise ValueError("❌ Geometry empty after simplify")

# -------------------------
# SAVE GEOJSON
# -------------------------
out_gdf = gpd.GeoDataFrame(geometry=[filled], crs=gdf.crs)
out_gdf["class"] = "water"

out_gdf.to_file(output_geojson, driver="GeoJSON")

print(f"\n✅ Saved GeoJSON: {output_geojson}")

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

print("Mask sum (should be > 0):", int(mask.sum()))

if mask.sum() == 0:
    raise ValueError("❌ Empty mask → geometry not aligned with raster")

# -------------------------
# EXPORT MASK (RED)
# -------------------------
out = np.zeros((h, w, 3), dtype=np.uint8)
out[mask == 1] = [255, 0, 0]

Image.fromarray(out).save(output_mask)

print(f"✅ Saved mask: {output_mask}")
print("\n🎯 Done successfully")