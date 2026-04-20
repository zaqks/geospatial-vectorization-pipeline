import geopandas as gpd
import numpy as np
from shapely.geometry import LineString
from shapely.ops import linemerge
import sys


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
MIN_SEGMENT_LENGTH = 20      # removes fake connectors
ANGLE_TOLERANCE = 15         # degrees for merging collinear roads
SNAP_DIST = 2                # fixes tiny breaks


# ─────────────────────────────────────────────
# UTIL
# ─────────────────────────────────────────────
def line_angle(line):
    x1, y1 = line.coords[0]
    x2, y2 = line.coords[-1]
    return np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180


def angle_diff(a, b):
    d = abs(a - b)
    return min(d, 180 - d)


# ─────────────────────────────────────────────
# CLEAN MAIN FUNCTION
# ─────────────────────────────────────────────
def clean_roads(gdf):

    gdf = gdf.copy()

    print("Initial:", len(gdf))

    # STEP 1 — remove tiny fake connectors
    gdf = gdf[gdf.length >= MIN_SEGMENT_LENGTH]

    print("After removing small segments:", len(gdf))

    # STEP 2 — group by approximate direction (fix broken splits)
    lines = list(gdf.geometry)
    used = [False] * len(lines)

    merged_lines = []

    for i, l1 in enumerate(lines):

        if used[i]:
            continue

        group = [l1]
        used[i] = True
        ang1 = line_angle(l1)

        for j, l2 in enumerate(lines):

            if used[j]:
                continue

            ang2 = line_angle(l2)

            if angle_diff(ang1, ang2) < ANGLE_TOLERANCE:

                # check if close enough to merge logically
                if l1.distance(l2) < SNAP_DIST:
                    group.append(l2)
                    used[j] = True

        # merge group into one line
        merged = linemerge(group)

        if merged.geom_type == "MultiLineString":
            merged_lines.extend(list(merged.geoms))
        else:
            merged_lines.append(merged)

    print("After merging splits:", len(merged_lines))

    return gpd.GeoDataFrame(geometry=merged_lines, crs=gdf.crs)


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":

    input_file = "output/vect/poly/output/vect/line2/route_clean2.geojson"
    output_file = "output/vect/poly/output/vect/line2/route_final_clean.geojson"

    gdf = gpd.read_file(input_file)

    gdf_clean = clean_roads(gdf)

    gdf_clean.to_file(output_file, driver="GeoJSON")

    print("Saved →", output_file)