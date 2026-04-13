import math
import numpy as np
from PIL import Image
import rasterio
from rasterio.transform import from_bounds

# -----------------------------
# INPUT
# -----------------------------
input_image = "./data/el_harrach_highres_map.png"
output_tif = "./data/el_harrach_georef.tif"

place_name = "El Harrach, Algeria"

# Your original bbox (same as your script)
south, north, west, east = 36.65, 36.78, 3.05, 3.20  # fallback if needed

# -----------------------------
# WEB MERCATOR CONVERSION
# -----------------------------
R = 6378137.0

def lon_to_x(lon):
    return R * math.radians(lon)

def lat_to_y(lat):
    return R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

# Convert bbox → EPSG:3857
min_x = lon_to_x(west)
max_x = lon_to_x(east)
min_y = lat_to_y(south)
max_y = lat_to_y(north)

# -----------------------------
# LOAD IMAGE
# -----------------------------
img = Image.open(input_image).convert("RGB")
img_np = np.array(img)

height, width, bands = img_np.shape

# -----------------------------
# AFFINE TRANSFORM
# -----------------------------
transform = from_bounds(
    min_x, min_y,
    max_x, max_y,
    width,
    height
)

# -----------------------------
# WRITE GEOREFERENCED TIFF
# -----------------------------
with rasterio.open(
    output_tif,
    "w",
    driver="GTiff",
    height=height,
    width=width,
    count=3,
    dtype=img_np.dtype,
    crs="EPSG:3857",
    transform=transform,
) as dst:
    dst.write(img_np[:, :, 0], 1)  # Red
    dst.write(img_np[:, :, 1], 2)  # Green
    dst.write(img_np[:, :, 2], 3)  # Blue

print("Done!")
print("Saved GeoTIFF:", output_tif)