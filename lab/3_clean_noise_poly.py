import os
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from PIL import Image
from tqdm import tqdm
from shapely.validation import make_valid

# -------------------------
# CONFIG
# -------------------------
# SIMPLIFY_TOL = 0.1  # adjust if needed


def clean_geometry(gdf, min_area_m2):
    """Full geometry cleaning pipeline"""

    # 1. Remove null / empty
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]

    # 2. Fix invalid geometries
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: make_valid(g) if not g.is_valid else g
    )

    # 3. Explode multipolygons
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)

    # 4. Remove non-polygon geometries (safety)
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]

    # 5. Project to metric CRS for area filtering
    original_crs = gdf.crs
    gdf_metric = gdf.to_crs(epsg=3857)

    # 6. Remove tiny polygons
    gdf_metric["area"] = gdf_metric.geometry.area
    gdf_metric = gdf_metric[gdf_metric["area"] >= min_area_m2]
    gdf_metric = gdf_metric.drop(columns=["area"])

    # 7. Back to original CRS
    gdf = gdf_metric.to_crs(original_crs)

    # 8. Simplify geometry
    # gdf["geometry"] = gdf.geometry.simplify(
    #     SIMPLIFY_TOL,
    #     preserve_topology=True
    # )

    # 9. Final cleanup after simplify
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]

    return gdf


def clean_and_debug_vector(geojson_path, output_dir, min_area_m2, reference_raster_path):
    """
    Filters and cleans polygons from a GeoJSON and exports cleaned version + debug PNG.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(geojson_path))[0]

    # 1. Load
    gdf = gpd.read_file(geojson_path)
    if gdf.empty:
        print(f"No data found in {geojson_path}")
        return

    initial_count = len(gdf)

    # 2. Clean geometry
    gdf_cleaned = clean_geometry(gdf, min_area_m2)

    final_count = len(gdf_cleaned)
    print(f"[{base_name}] {initial_count} → {final_count} features after cleaning.")

    # 3. Export cleaned GeoJSON
    clean_geojson_path = os.path.join(output_dir, f"{base_name}_cleaned.geojson")
    gdf_cleaned.to_file(clean_geojson_path, driver="GeoJSON")

    # 4. Generate Debug PNG
    with rasterio.open(reference_raster_path) as src:
        h, w = src.height, src.width
        transform = src.transform
        raster_crs = src.crs

    gdf_for_raster = gdf_cleaned.to_crs(raster_crs)

    if not gdf_for_raster.empty:
        mask = rasterize(
            [(geom, 1) for geom in gdf_for_raster.geometry],
            out_shape=(h, w),
            transform=transform,
            fill=0,
            dtype=np.uint8
        )

        out_img = np.zeros((h, w, 3), dtype=np.uint8)
        out_img[mask == 1] = [255, 0, 0]

        Image.fromarray(out_img).save(
            os.path.join(output_dir, f"{base_name}.png")
        )

    print(f"Finished: {clean_geojson_path}")


# -------------------------
# EXECUTION
# -------------------------
from pathlib import Path

if __name__ == "__main__":
    input_folder = Path("output/vect/poly")
    output_folder = Path("output/clean/poly")
    ref_raster = "data/el_harrach_georef.tif"

    output_folder.mkdir(parents=True, exist_ok=True)

    geojson_files = list(input_folder.glob("*.geojson"))

    if not geojson_files:
        print("No GeoJSON files found.")

    for geojson_path in tqdm(geojson_files, desc="Processing GeoJSON files"):
        try:
            clean_and_debug_vector(
                geojson_path=str(geojson_path),
                output_dir=str(output_folder),
                min_area_m2=1,
                reference_raster_path=ref_raster
            )
        except Exception as e:
            print(f"Failed on {geojson_path.name}: {e}")