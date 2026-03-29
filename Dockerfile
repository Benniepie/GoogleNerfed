FROM python:3.11-slim

WORKDIR /app

# Install dependencies

RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    python3-dev \
    libsuitesparse-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

RUN export CPLUS_INCLUDE_PATH=/usr/include/gdal
RUN export C_INCLUDE_PATH=/usr/include/gdal

RUN pip install git+https://github.com/drufat/triangle.git
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend and frontend files
COPY main.py .
COPY geoprocessing.py .
COPY debug_pipeline.py .
COPY debug_config.json .
COPY test_identical.py .
COPY static/ ./static/

# Ensure the data directory exists
RUN mkdir -p /app/data

# Run the FastAPI server using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8069"]
