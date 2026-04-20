import os
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from PIL import Image
from tqdm import tqdm

def clean_and_debug_vector(geojson_path, output_dir, min_area_m2, reference_raster_path):
    """
    Filters small polygons from a GeoJSON and exports a cleaned version + a debug PNG.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(geojson_path))[0]
    
    # 1. Load the data
    gdf = gpd.read_file(geojson_path)
    if gdf.empty:
        print(f"No data found in {geojson_path}")
        return

    # 2. Calculate Area and Filter
    original_crs = gdf.crs
    gdf_metric = gdf.to_crs(epsg=3857) 
    
    initial_count = len(gdf_metric)
    gdf_cleaned_metric = gdf_metric[gdf_metric.geometry.area >= min_area_m2]
    final_count = len(gdf_cleaned_metric)
    
    print(f"[{base_name}] Dropped {initial_count - final_count} polygons smaller than {min_area_m2}m².")

    # Convert back to original CRS
    gdf_cleaned = gdf_cleaned_metric.to_crs(original_crs)

    # 3. Export Cleaned GeoJSON
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