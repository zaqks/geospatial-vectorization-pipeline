# This image comes with Python 3.12, GDAL, GEOS, and X11 libs pre-baked
FROM pangeo/pangeo-notebook:6f9fda2

USER root
WORKDIR /app

# Copy your requirements and code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x run.sh

CMD ["./run.sh"]
