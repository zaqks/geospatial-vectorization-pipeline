import geopandas as gpd
from shapely.geometry import LineString, Polygon, MultiLineString, MultiPolygon
import sys


# ─────────────────────────────────────────────
# CONFIG (tune these)
# ─────────────────────────────────────────────
MIN_LINE_LENGTH = 25     # map units (increase if still noisy)
MIN_POLY_AREA   = 40     # for accidental polygons
DROP_POINTS     = True   # remove Point geometries


# ─────────────────────────────────────────────
# CLEAN FUNCTION
# ─────────────────────────────────────────────
def clean_geometries(gdf):

    print("Initial features:", len(gdf))

    cleaned = []

    for geom in gdf.geometry:

        if geom is None or geom.is_empty:
            continue

        gtype = geom.geom_type

        # ─────────────────────────────
        # REMOVE POINTS
        # ─────────────────────────────
        if DROP_POINTS and gtype == "Point":
            continue

        # ─────────────────────────────
        # LINE FILTERING
        # ─────────────────────────────
        if gtype in ["LineString"]:

            if geom.length >= MIN_LINE_LENGTH:
                cleaned.append(geom)

        elif gtype == "MultiLineString":

            parts = [l for l in geom.geoms if l.length >= MIN_LINE_LENGTH]

            if parts:
                cleaned.append(LineString([pt for line in parts for pt in line.coords]))

        # ─────────────────────────────
        # POLYGON FILTERING (if exists)
        # ─────────────────────────────
        elif gtype == "Polygon":

            if geom.area >= MIN_POLY_AREA:
                cleaned.append(geom)

        elif gtype == "MultiPolygon":

            parts = [p for p in geom.geoms if p.area >= MIN_POLY_AREA]

            if parts:
                cleaned.append(MultiPolygon(parts))

        # ─────────────────────────────
        # fallback (ignore geometry collections noise)
        # ─────────────────────────────
        else:
            continue

    gdf_clean = gpd.GeoDataFrame(geometry=cleaned, crs=gdf.crs)

    print("After cleaning:", len(gdf_clean))

    return gdf_clean


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":

    input_file =  "output/vect/poly/output/vect/line/street_clean2.geojson"
    output_file =  "/output/vect/poly/output/vect/line/street_final_clean.geojson"

    gdf = gpd.read_file(input_file)

    gdf = clean_geometries(gdf)

    gdf.to_file(output_file, driver="GeoJSON")

    print("Saved →", output_file)