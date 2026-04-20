import os
import numpy as np
import geopandas as gpd
import rasterio
from shapely.ops import unary_union, linemerge
from shapely.geometry import LineString, MultiLineString
from rasterio.features import rasterize
from PIL import Image

# -------------------------
# CONFIG
# -------------------------
input_geojson = "output/vect/line/railway.geojson"
raster_path = "data/el_harrach_georef.tif"
output_dir = "output/clean/line"

os.makedirs(output_dir, exist_ok=True)

SNAP_TOLERANCE = 2.0
SIMPLIFY_TOLERANCE = 0.3
MIN_LINE_LENGTH = 5  # meters (EPSG:3857)
EXPORT_TO_WGS84 = True

DEBUG = True

# -------------------------
# LOAD VECTOR DATA
# -------------------------
gdf = gpd.read_file(input_geojson)

if gdf.empty:
    raise ValueError("❌ Input GeoJSON is empty")

if gdf.crs is None:
    raise ValueError("❌ CRS is None. Cannot continue safely.")

if DEBUG:
    print(f"[DEBUG] Loaded features: {len(gdf)}")
    print(f"[DEBUG] Original CRS: {gdf.crs}")

# -------------------------
# CONVERT TO METRIC CRS
# -------------------------
gdf = gdf.to_crs("EPSG:3857")

if DEBUG:
    print("[DEBUG] Reprojected to EPSG:3857")

# -------------------------
# CLEAN GEOMETRIES
# -------------------------
geoms = [g for g in gdf.geometry if g is not None]

if not geoms:
    raise ValueError("❌ No valid geometries found")

dissolved = unary_union(geoms)

if DEBUG:
    print(f"[DEBUG] Dissolved type: {dissolved.geom_type}")

# -------------------------
# EXTRACT LINES
# -------------------------
lines = []

if dissolved.geom_type == "LineString":
    lines = [dissolved]

elif dissolved.geom_type == "MultiLineString":
    lines = list(dissolved.geoms)

elif dissolved.geom_type in ["Polygon", "MultiPolygon"]:
    polys = [dissolved] if dissolved.geom_type == "Polygon" else dissolved.geoms
    for p in polys:
        lines.append(p.exterior)

else:
    raise ValueError(f"Unsupported geometry type: {dissolved.geom_type}")

# -------------------------
# MERGE LINES
# -------------------------
merged = linemerge(unary_union(lines))

if isinstance(merged, LineString):
    final_lines = [merged]
elif isinstance(merged, MultiLineString):
    final_lines = list(merged.geoms)
else:
    final_lines = []

if DEBUG:
    print(f"[DEBUG] Final merged lines: {len(final_lines)}")

# -------------------------
# BUILD GEO DATAFRAME
# -------------------------
gdf_out = gpd.GeoDataFrame(geometry=final_lines, crs="EPSG:3857")

# simplify
gdf_out["geometry"] = gdf_out.geometry.simplify(
    SIMPLIFY_TOLERANCE,
    preserve_topology=True
)

# filter short lines
before = len(gdf_out)
gdf_out = gdf_out[gdf_out.length > MIN_LINE_LENGTH]
after = len(gdf_out)

if DEBUG:
    print(f"[DEBUG] Filtered: {before} → {after}")

if gdf_out.empty:
    raise ValueError("❌ All geometries removed. Lower MIN_LINE_LENGTH.")

# -------------------------
# SAVE GEOJSON
# -------------------------
class_name = os.path.splitext(os.path.basename(input_geojson))[0]

out_geojson = os.path.join(output_dir, f"{class_name}.geojson")

gdf_save = gdf_out.to_crs("EPSG:4326") if EXPORT_TO_WGS84 else gdf_out
gdf_save.to_file(out_geojson, driver="GeoJSON")

print(f"\n✅ Saved GeoJSON: {out_geojson}")

# -------------------------
# RASTER-ALIGNED PNG EXPORT (FIXED)
# -------------------------
try:
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        transform = src.transform
        height = src.height
        width = src.width

    # reproject vector to raster CRS
    gdf_raster = gdf_out.to_crs(raster_crs)

    if DEBUG:
        print("[DEBUG] Raster CRS:", raster_crs)
        print("[DEBUG] Raster size:", width, height)

    mask = rasterize(
        [(geom, 1) for geom in gdf_raster.geometry if geom is not None],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype=np.uint8,
        all_touched=True
    )

    if DEBUG:
        print("[DEBUG] Non-zero pixels:", np.count_nonzero(mask))

    if np.count_nonzero(mask) == 0:
        print("⚠️ WARNING: Empty raster result")

    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[mask == 1] = (255, 0, 0)

    out_png = os.path.join(output_dir, f"{class_name}.png")
    Image.fromarray(img).save(out_png)

    print(f"✅ Saved PNG: {out_png}")

except Exception as e:
    print(f"❌ PNG export failed: {e}")

# -------------------------
# DONE
# -------------------------
print("\n🎉 DONE → processing complete")