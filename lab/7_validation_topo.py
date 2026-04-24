# %%
# ─────────────────────────────
    


import geopandas as gpd
from shapely.validation import make_valid
from shapely.ops import unary_union
import numpy as np


# ─────────────────────────────────────────────
# LOAD SAFE
# ─────────────────────────────────────────────
def load(path):
    gdf = gpd.read_file(path)
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]
    gdf["geometry"] = gdf.geometry.apply(make_valid)
    return gdf


# ─────────────────────────────────────────────
# INTERSECTION CHECK (SAFE, SPATIAL INDEX)
# ─────────────────────────────────────────────
def find_intersections(a, b):

    idx = b.sindex
    issues = []

    for i, geom in enumerate(a.geometry):

        if geom is None:
            continue

        possible = list(b.iloc[list(idx.intersection(geom.bounds))].geometry)

        for g2 in possible:
            if geom.intersects(g2):
                inter = geom.intersection(g2)

                if not inter.is_empty:
                    issues.append(inter)

    return issues


# ─────────────────────────────────────────────
# VALIDATION RULES
# ─────────────────────────────────────────────
def validate():

    print("Loading layers...")

    roads_auto = load_clean("output/vect/line2/route_final_clean2.geojson")
    roads_nat  = load_clean("output/vect/line2/autoroute_final_clean.geojson")
    roads_st   = load_clean("output/vect/line2/street_final_clean.geojson")

    
    buildings  = load_clean("output/vect/poly/buildings_clean2.geojson")
    water      = load_clean("output/vect/poly/water_clean.geojson")
    res        = load_clean("output/vect/poly/residential_clean.geojson")
    area       = load_clean("output/vect/poly/area_clean.geojson")
    grass      = load("output/vect/poly/grass_clean.geojson")
    metro      = load("output/vect/poly/surrounding metro.geojson")

    print("Running validations...\n")

    # ─────────────────────────────
    # 1. BUILDINGS vs WATER
    # ─────────────────────────────
    bw = find_intersections(buildings, water)
    print("Buildings ∩ Water:", len(bw))

    # ─────────────────────────────
    # 2. BUILDINGS vs ROADS
    # ─────────────────────────────
    all_roads = gpd.GeoSeries(
        list(roads_auto.geometry) +
        list(roads_nat.geometry) +
        list(roads_st.geometry)
    )

    br = find_intersections(buildings, gpd.GeoDataFrame(geometry=all_roads))
    print("Buildings ∩ Roads:", len(br))

    # ─────────────────────────────
    # 3. ROAD HIERARCHY VIOLATIONS
    # ─────────────────────────────
    na = find_intersections(roads_nat, roads_auto)
    st = find_intersections(roads_st, roads_nat)

    print("National ↔ Autoroute:", len(na))
    print("Street ↔ National:", len(st))

    # ─────────────────────────────
    # 4. RESIDENTIAL vs WATER
    # ─────────────────────────────
    rw = find_intersections(res, water)
    print("Residential ∩ Water:", len(rw))

    # ─────────────────────────────
    # 5. GRASS vs WATER (expected partial overlap)
    # ─────────────────────────────
    gw = find_intersections(grass, water)
    print("Grass ∩ Water:", len(gw))

    # ─────────────────────────────
    # 6. METRO CONFLICTS
    # ─────────────────────────────
    mb = find_intersections(metro, buildings)
    mw = find_intersections(metro, water)

    print("Metro ∩ Buildings:", len(mb))
    print("Metro ∩ Water:", len(mw))

    # ─────────────────────────────
    # EXPORT ERROR LAYERS
    # ─────────────────────────────
    def export(name, geom_list):
        if len(geom_list) == 0:
            return
        gpd.GeoDataFrame(geometry=geom_list, crs=roads_auto.crs)\
            .to_file(f"errors_{name}.geojson", driver="GeoJSON")

    export("buildings_water", bw)
    export("buildings_roads", br)
    export("road_nat_auto", na)
    export("road_st_nat", st)
    export("res_water", rw)
    export("metro_buildings", mb)
    export("metro_water", mw)

    print("\n✅ Validation complete — error layers exported.")


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    validate()  