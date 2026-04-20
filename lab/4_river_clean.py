import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid
import sys


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
MIN_AREA = 30       # remove tiny noise polygons
SIMPLIFY_TOL = 2.0    # higher = smoother but less detailed


# ─────────────────────────────────────────────
# CLEAN GEOMETRY FUNCTION
# ─────────────────────────────────────────────
def clean_geometry(gdf):

    print("Removing invalid geometries...")
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]

    # fix invalid shapes
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: make_valid(g) if not g.is_valid else g
    )

    print("Exploding multipolygons...")
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)

    print("Removing tiny polygons...")
    gdf["area"] = gdf.geometry.area
    gdf = gdf[gdf["area"] >= MIN_AREA]
    gdf = gdf.drop(columns=["area"])

    print("Simplifying geometry (smoothing edges)...")
    gdf["geometry"] = gdf.geometry.simplify(
        SIMPLIFY_TOL,
        preserve_topology=True
    )

    # remove anything broken after simplify
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]

    return gdf


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def clean_geojson(input_file, output_file):

    print(f"\nLoading {input_file}")
    gdf = gpd.read_file(input_file)

    print(f"Initial features: {len(gdf)}")

    cleaned = clean_geometry(gdf)

    print(f"Cleaned features: {len(cleaned)}")

    cleaned.to_file(output_file, driver="GeoJSON")

    print(f"\n✅ Saved clean GeoJSON → {output_file}")


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":

    input_geojson = sys.argv[1] if len(sys.argv) > 1 else "water.geojson"
    output_geojson = sys.argv[2] if len(sys.argv) > 2 else "water_clean.geojson"

    clean_geojson(input_geojson, output_geojson)