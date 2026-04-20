import os
import numpy as np
import geopandas as gpd

from shapely.ops import unary_union, linemerge
from sklearn.cluster import DBSCAN

# -------------------------
# CONFIG
# -------------------------
INPUT_GEOJSON = "output/vect/line/autoroute.geojson"

OUTPUT_DIR = "output/vect_clean/line"
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_GEOJSON = os.path.join(OUTPUT_DIR, "final_clean.geojson")

CRS_TARGET = "EPSG:3857"

CLUSTER_EPS = 3.0      # meters
MIN_LENGTH = 5.0       # meters


# -------------------------
# LOAD + BASIC CLEAN
# -------------------------
def load_data():
    gdf = gpd.read_file(INPUT_GEOJSON).to_crs(CRS_TARGET)

    # remove empty / null geometries
    gdf = gdf[gdf.geometry.notnull() & (~gdf.geometry.is_empty)]

    # fix invalid geometries
    gdf["geometry"] = gdf.geometry.buffer(0)

    # explode multilines
    gdf = gdf.explode(index_parts=False)

    # keep only lines
    gdf = gdf[gdf.geom_type.isin(["LineString"])].copy()

    return gdf


# -------------------------
# SAFE CLUSTERING (NO centroid crash)
# -------------------------
def cluster_roads(gdf, eps=3.0):
    # -------------------------
    # HARD SAFETY FILTER
    # -------------------------
    gdf = gdf[gdf.geometry.notnull() & (~gdf.geometry.is_empty)].copy()

    # keep only line geometries
    gdf = gdf[gdf.geom_type.isin(["LineString", "MultiLineString"])]

    if len(gdf) == 0:
        raise ValueError("No valid geometries left after cleaning. Check input data.")

    # -------------------------
    # SAFE FEATURE EXTRACTION
    # -------------------------
    coords = []

    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue

        # MultiLineString safety
        if geom.geom_type == "MultiLineString":
            geom = list(geom.geoms)[0]

        # use representative point (stable, always inside geometry)
        p = geom.representative_point()
        coords.append([p.x, p.y])

    coords = np.array(coords)

    # FINAL GUARD (THIS FIXES YOUR CRASH)
    if coords.size == 0:
        raise ValueError("DBSCAN input is empty. No valid coordinate samples found.")

    # -------------------------
    # CLUSTER
    # -------------------------
    from sklearn.cluster import DBSCAN

    labels = DBSCAN(eps=eps, min_samples=1).fit(coords).labels_

    # align safely
    gdf = gdf.iloc[:len(labels)].copy()
    gdf["cluster"] = labels

    return gdf


# -------------------------
# DISSOLVE CORRIDORS
# -------------------------
def dissolve_clusters(gdf):
    dissolved = gdf.dissolve(by="cluster")

    def clean_geom(geom):
        if geom is None or geom.is_empty:
            return None

        if geom.geom_type == "MultiLineString":
            geom = linemerge(geom)

        return geom

    dissolved["geometry"] = dissolved.geometry.apply(clean_geom)

    dissolved = dissolved[dissolved.geometry.notnull()]

    return dissolved.reset_index(drop=True)


# -------------------------
# REMOVE SMALL ARTIFACTS
# -------------------------
def filter_short(gdf, min_len=5.0):
    gdf = gdf.copy()

    gdf["length"] = gdf.geometry.length
    gdf = gdf[gdf["length"] >= min_len]

    return gdf.drop(columns=["length"])


# -------------------------
# FINAL MERGE CLEANUP
# -------------------------
def final_merge(gdf):
    merged = unary_union(gdf.geometry)
    merged = linemerge(merged)

    if merged.geom_type == "LineString":
        return gpd.GeoDataFrame(geometry=[merged], crs=CRS_TARGET)

    return gpd.GeoDataFrame(geometry=list(merged.geoms), crs=CRS_TARGET)


# -------------------------
# PIPELINE
# -------------------------
def clean_pipeline():
    print("Loading data...")
    gdf = load_data()

    print("Clustering road corridors...")
    gdf = cluster_roads(gdf, CLUSTER_EPS)

    print("Dissolving clusters...")
    gdf = dissolve_clusters(gdf)

    print("Filtering short artifacts...")
    gdf = filter_short(gdf, MIN_LENGTH)

    print("Final merge cleanup...")
    gdf = final_merge(gdf)

    print("Saving output...")
    gdf.to_file(OUTPUT_GEOJSON, driver="GeoJSON")

    print("Done ✔")


if __name__ == "__main__":
    clean_pipeline()