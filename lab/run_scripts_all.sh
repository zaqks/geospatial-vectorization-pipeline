#!/bin/bash

#!/bin/bash
set -e  # stop on error

echo "Starting pipeline..."

# echo "Running 0_data.py..."
# python 0_data.py

# echo "Running 0_legend_extract.py..."
# python 0_legend_extract.py

echo "Running 0_legend_overlay_line.py..."
python 0_legend_overlay_line.py

echo "Running 0_legend_overlay_poly.py..."
python 0_legend_overlay_poly.py

echo "Running 1_georef.py..."
python 1_georef.py

echo "Running 2_vectorization_line.py..."
python 2_vectorization_line.py

echo "Running 2_vectorization_poly.py..."
python 2_vectorization_poly.py

echo "Running 2_vectorization_dotted.py..."
python 2_vectorization_dotted.py

echo "Running 3_clean_noise_poly.py..."
python 3_clean_noise_poly.py

echo "Running 3_clean_gapfill.py..."
python 3_clean_gapfill.py

# echo "Running 6_viz_line.py..."
# python 6_viz_line.py

# echo "Running 6_viz_poly.py..."
# python 6_viz_poly.py

# echo "Running 7_validation_topo.py..."
# python 7_validation_topo.py

echo "All scripts completed successfully!"
