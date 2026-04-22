# Original bounding box: [min_lat, min_lon, max_lat, max_lon]
bbox = [36.69154743547263, 3.113250732421875, 36.732280756072015, 3.165435791015625]

min_lat, min_lon, max_lat, max_lon = bbox

# Calculate the width and height of each cell
lat_step = (max_lat - min_lat) / 3
lon_step = (max_lon - min_lon) / 3

# Define target indices (0-based)
# 1st column -> index 0
# 2nd row -> index 1
col_idx = 0
row_idx = 1 

# Calculate the cell boundaries
# Note: For rows, we calculate from the bottom (south) up.
# Row 0: Bottom, Row 1: Middle, Row 2: Top
cell_min_lat = min_lat + (row_idx * lat_step)
cell_max_lat = min_lat + ((row_idx + 1) * lat_step)

cell_min_lon = min_lon + (col_idx * lon_step)
cell_max_lon = min_lon + ((col_idx + 1) * lon_step)

cell_bbox = [cell_min_lat, cell_min_lon, cell_max_lat, cell_max_lon]

print(f"Cell Bounding Box (1st col, 2nd row):")
print(f"min_lat: {cell_min_lat}")
print(f"min_lon: {cell_min_lon}")
print(f"max_lat: {cell_max_lat}")
print(f"max_lon: {cell_max_lon}")
print(f"\nFull list: {cell_bbox}")