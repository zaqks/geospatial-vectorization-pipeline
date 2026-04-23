from PIL import Image

# -------------------------
# INPUT GRID CONFIG
# -------------------------
bbox = [36.69154743547263, 3.113250732421875,
        36.732280756072015, 3.165435791015625]

min_lat, min_lon, max_lat, max_lon = bbox

nrows = 2
ncols = 2

# Target cell (0-based indexing)
col_idx = 0   # 1st column
row_idx = 0   # 2nd row (middle row)

# -------------------------
# GRID STEP SIZE
# -------------------------
lat_step = (max_lat - min_lat) / nrows
lon_step = (max_lon - min_lon) / ncols

# -------------------------
# CELL BOUNDING BOX
# -------------------------
cell_min_lat = min_lat + (row_idx * lat_step)
cell_max_lat = min_lat + ((row_idx + 1) * lat_step)

cell_min_lon = min_lon + (col_idx * lon_step)
cell_max_lon = min_lon + ((col_idx + 1) * lon_step)

cell_bbox = [cell_min_lat, cell_min_lon, cell_max_lat, cell_max_lon]

print("Cell Bounding Box:")
print(cell_bbox)


# =========================================================
# PNG CROPPING (simple pixel crop example)
# =========================================================

input_png_path = "../data/el_harrach_highres_map_orignal.png"
output_png_path = "../data/map_cropped.png"

img = Image.open(input_png_path)

# If you already have pixel coordinates corresponding to bbox,
# replace these with computed pixel bounds.
# Example placeholders:
img_width, img_height = img.size

# Dummy conversion example (ASSUMES full image == bbox extent)
left = int((col_idx / ncols) * img_width)
right = int(((col_idx + 1) / ncols) * img_width)

top = int((row_idx / nrows) * img_height)
bottom = int(((row_idx + 1) / nrows) * img_height)

cropped_img = img.crop((left, top, right, bottom))
cropped_img.save(output_png_path)

print(f"Cropped image saved to: {output_png_path}")