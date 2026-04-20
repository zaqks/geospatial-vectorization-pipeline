import geopandas as gpd
from shapely.geometry import LineString
from shapely.ops import snap
from tqdm import tqdm


# ─────────────────────────────────────────────
# CONFIG (tune these only)
# ─────────────────────────────────────────────
SNAP_TOLERANCE = 3      # how far endpoints can snap (map units)
MAX_GAP        = 8      # max distance to bridge gaps
CHUNK_SIZE     = 300    # prevents memory spikes


# ─────────────────────────────────────────────
# LOAD
# ─────────────────────────────────────────────
def load_roads(path):
    gdf = gpd.read_file(path)
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[gdf.geometry.is_empty == False]
    return gdf


# ─────────────────────────────────────────────
# SAFE GAP FIX (NO GLOBAL UNION)
# ─────────────────────────────────────────────
def fix_gaps_safe(gdf):

    gdf = gdf.copy()

    # spatial index = fast neighbor search
    sindex = gdf.sindex

    new_geoms = []

    print("Fixing gaps locally...")

    for i, geom in tqdm(enumerate(gdf.geometry), total=len(gdf)):

        if geom is None:
            new_geoms.append(None)
            continue

        # find only nearby geometries (VERY IMPORTANT)
        possible_idx = list(sindex.intersection(geom.bounds))
        neighbors = gdf.iloc[possible_idx].geometry

        fixed = geom

        # snap ONLY locally
        for n in neighbors:
            if n is geom:
                continue

            dist = fixed.distance(n)

            # only fix small gaps
            if 0 < dist <= MAX_GAP:
                fixed = snap(fixed, n, SNAP_TOLERANCE)

        new_geoms.append(fixed)

    gdf["geometry"] = new_geoms
    return gdf


# ─────────────────────────────────────────────
# OPTIONAL: REMOVE TINY ARTIFACTS
# ─────────────────────────────────────────────
def remove_noise(gdf, min_length=10):

    gdf = gdf.copy()
    gdf["length"] = gdf.length

    gdf = gdf[gdf["length"] >= min_length]

    return gdf.drop(columns=["length"])


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────
def clean_roads(input_path, output_path):

    print("Loading:", input_path)
    gdf = load_roads(input_path)

    print("Initial roads:", len(gdf))

    # STEP 1 — remove tiny fake segments (rail artifacts etc.)
    gdf = remove_noise(gdf, min_length=10)

    print("After noise removal:", len(gdf))

    # STEP 2 — fix gaps safely (NO UNION)
    gdf = fix_gaps_safe(gdf)

    # STEP 3 — final cleanup
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]

    print("Final roads:", len(gdf))

    # SAVE
    gdf.to_file(output_path, driver="GeoJSON")
    print("Saved →", output_path)


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":

    input_file = "output/vect/line/route nationale.geojson"
    output_file = "output/vect/line/route_clean2.geojson"

    clean_roads(input_file, output_file)