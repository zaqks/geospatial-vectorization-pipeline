import geopandas as gpd
import numpy as np
from shapely.geometry import LineString
from shapely.ops import linemerge
import sys


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
SPIKE_ANGLE_THRESHOLD = 45   # sharper = likely bretelle spike
WINDOW_SIZE = 5              # smoothing window
MIN_KEEP_LENGTH = 15


# ─────────────────────────────────────────────
# ANGLE HELPERS
# ─────────────────────────────────────────────
def angle(p1, p2):
    return np.degrees(np.arctan2(p2[1]-p1[1], p2[0]-p1[0]))


def is_spike(p_prev, p, p_next):
    a1 = angle(p_prev, p)
    a2 = angle(p, p_next)
    diff = abs(a1 - a2)
    diff = min(diff, 360 - diff)
    return diff > (180 - SPIKE_ANGLE_THRESHOLD)


# ─────────────────────────────────────────────
# REMOVE LOCAL SPIKES
# ─────────────────────────────────────────────
def smooth_line(line):

    coords = list(line.coords)

    if len(coords) < 4:
        return line

    new_coords = [coords[0]]

    for i in range(1, len(coords) - 1):

        prev_pt = coords[i - 1]
        curr_pt = coords[i]
        next_pt = coords[i + 1]

        if is_spike(prev_pt, curr_pt, next_pt):
            # skip spike point (this removes bretelle distortion)
            continue

        new_coords.append(curr_pt)

    new_coords.append(coords[-1])

    if len(new_coords) < 2:
        return line

    return LineString(new_coords)


# ─────────────────────────────────────────────
# MAIN CLEANER
# ─────────────────────────────────────────────
def clean_bretelle_spikes(gdf):

    print("Initial:", len(gdf))

    cleaned = []

    for geom in gdf.geometry:

        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == "LineString":

            if geom.length < MIN_KEEP_LENGTH:
                continue

            cleaned.append(smooth_line(geom))

        elif geom.geom_type == "MultiLineString":

            for part in geom.geoms:
                if part.length >= MIN_KEEP_LENGTH:
                    cleaned.append(smooth_line(part))

    result = gpd.GeoDataFrame(geometry=cleaned, crs=gdf.crs)

    print("After spike removal:", len(result))

    return result


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":

    input_file = "output/vect/poly/output/vect/line/route_final_clean.geojson"
    output_file = "output/vect/poly/output/vect/line/route_final_clean2.geojson"

    gdf = gpd.read_file(input_file)

    gdf_clean = clean_bretelle_spikes(gdf)

    gdf_clean.to_file(output_file, driver="GeoJSON")

    print("Saved →", output_file)