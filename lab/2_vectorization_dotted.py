import os
import cv2
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from shapely.geometry import shape, LineString
from rasterio.features import shapes, rasterize
from skimage.morphology import skeletonize
from PIL import Image
from scipy.spatial import KDTree

# -------------------------
# CONFIG
# -------------------------
raster_path = "data/el_harrach_georef.tif"
output_dir = "output/vect/line"
os.makedirs(output_dir, exist_ok=True)

TARGET_CLASS = "railway"
COLOR_TOLERANCE = 3
BRIDGE_RADIUS = 100
NOISE_RADIUS = 2
MIN_LINE_LENGTH_M = 1
SIMPLIFY_TOLERANCE = 1
EXPORT_TO_WGS84 = True
ENDPOINT_SEARCH_RADIUS_M = 50

# -------------------------
# LOAD LEGEND
# -------------------------
df = pd.read_csv("data/legend_class_geo.csv")
rail_row = df.loc[df["class"] == TARGET_CLASS].iloc[0]

def hex_to_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i+2], 16) for i in (0, 2, 4)], dtype=np.uint8)

rgb_val = hex_to_rgb(rail_row["hex"])
lower_b = np.clip(rgb_val - COLOR_TOLERANCE, 0, 255)
upper_b = np.clip(rgb_val + COLOR_TOLERANCE, 0, 255)

# -------------------------
# LOAD RASTER
# -------------------------
with rasterio.open(raster_path) as src:
    img = src.read((1, 2, 3))
    transform = src.transform
    crs = src.crs
    h, w = src.height, src.width

img = np.moveaxis(img, 0, -1)

# -------------------------
# MASK
# -------------------------
mask = cv2.inRange(img, lower_b, upper_b)
if not mask.any():
    print("No railway pixels found.")
    exit()

# -------------------------
# MORPHOLOGY (faster kernels reused)
# -------------------------
open_kernel = cv2.getStructuringElement(
    cv2.MORPH_ELLIPSE, (NOISE_RADIUS*2+1, NOISE_RADIUS*2+1)
)
close_kernel = cv2.getStructuringElement(
    cv2.MORPH_ELLIPSE, (BRIDGE_RADIUS, BRIDGE_RADIUS)
)

mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

# -------------------------
# SKELETON
# -------------------------
skeleton = skeletonize(mask > 0).astype(np.uint8)

# -------------------------
# VECTORIZE LINES (FAST PATH)
# -------------------------
lines = []

for geom, val in shapes(skeleton, mask=skeleton, transform=transform):
    g = shape(geom)
    if g.geom_type == "LineString":
        lines.append(g)
    elif g.geom_type == "MultiLineString":
        lines.extend(g.geoms)
    elif g.geom_type in ("Polygon", "MultiPolygon"):
        lines.append(g.exterior)

# -------------------------
# ENDPOINT DETECTION (NUMPY FAST)
# -------------------------
kernel = np.array([[1,1,1],
                   [1,0,1],
                   [1,1,1]], dtype=np.uint8)

neighbors = cv2.filter2D(skeleton, -1, kernel)
endpoints = np.argwhere((skeleton == 1) & (neighbors == 1))

# -------------------------
# VECTORIZED PIXEL → COORDINATES (MAJOR SPEEDUP)
# -------------------------
if len(endpoints) > 0:
    rows, cols = endpoints[:, 0], endpoints[:, 1]
    xs, ys = rasterio.transform.xy(transform, rows, cols)
    end_xy = np.column_stack([xs, ys])

    # -------------------------
    # KDTree CONNECTIONS
    # -------------------------
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

# -------------------------
# BUILD GEO DATAFRAME
# -------------------------
gdf = gpd.GeoDataFrame({"geometry": lines}, crs=crs)

if gdf.empty:
    print("No valid geometries.")
    exit()

gdf["length_m"] = gdf.length
gdf = gdf[gdf["length_m"] >= MIN_LINE_LENGTH_M]

gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
gdf["class"] = TARGET_CLASS

if EXPORT_TO_WGS84:
    gdf = gdf.to_crs("EPSG:4326")

# -------------------------
# EXPORT
# -------------------------
out_geojson = os.path.join(output_dir, f"{TARGET_CLASS}.geojson")
gdf.to_file(out_geojson, driver="GeoJSON")

# -------------------------
# DEBUG IMAGE (FASTER RASTERIZE)
# -------------------------
gdf_r = gdf.to_crs(crs)

debug_mask = rasterize(
    [(geom, 1) for geom in gdf_r.geometry],
    out_shape=(h, w),
    transform=transform,
    fill=0,
    dtype=np.uint8
)

out_img = np.zeros((h, w, 3), dtype=np.uint8)
out_img[debug_mask == 1] = (255, 0, 0)

Image.fromarray(out_img).save(
    os.path.join(output_dir, f"{TARGET_CLASS}.png")
)

print(f"SUCCESS: {len(gdf)} railway segments generated.")