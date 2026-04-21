FROM python:3.12-slim

WORKDIR /app

# System GIS dependencies
RUN apt-get update && apt-get install -y \
    libexpat1 \
    gdal-bin \
    libgdal-dev \
    proj-bin \
    libproj-dev \
    libgeos-dev \
    libspatialindex-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Ensure GDAL env consistency (important for rasterio/fiona)
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x run.sh

CMD ["./run.sh"]