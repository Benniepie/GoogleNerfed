## **Oi! Map It!**

Google Earth's view of Google MyMaps was totally broken and every single map marker had a label that wouldn't go away. With Google MyMaps KML styles being ignored by Google Earth when viewing a MyMap and no sign of it ever being fixed by Google, it was time to jump ship and ditch the cloud.

This is a lightweight, open-source, and fully self-hosted map app. This project allows you to easily view, upload, manage, and style your KML and KMZ mapping data over beautiful vector and satellite base maps. And a few other bits and pieces. 

Written by Bennie, map expertise by JR for JP @ ATP Geopolitics: https://map.atpgeo.com
Track updates to the map on Youtube: https://youtube.com/@atpgeo


## **✨ Features**

* **KML & KMZ Support**: Upload your exported Google Maps data directly through the UI. KMZ archives are automatically unpacked into KML on the backend.  
* **Layer Management**: Toggle multiple data layers on and off seamlessly.  
* **Custom Styling**: Change the colour of polygons, lines, and markers for each layer. Style choices are saved in your browser's local storage so they persist across reloads.  
* **Base Map Switching**: Easily toggle between a sleek Dark Vector Map (via OpenFreeMap) and High-Resolution Satellite Imagery (via Esri).  
* **Soft Deletion**: Delete layers from the UI with peace of mind. The backend safeguards your data by renaming deleted files with a .deleted extension rather than permanently erasing them.  
* **Modern UI**: A responsive, dark-mode 'glassmorphism' control panel that floats over your maps.  
* **Single-Container Deployment**: The entire application (FastAPI backend and static frontend) runs in a single, lightweight Docker container.

## **🛠 Tech Stack**

### **Frontend**

* **Leaflet (1.9.4)**: The core mapping library handling the UI, popups, and GeoJSON rendering.  
* **MapLibre GL JS**: Used alongside a Leaflet binding (@maplibre/maplibre-gl-leaflet) to render modern, crisp Vector Tiles inside the Leaflet environment.  
* **toGeoJSON**: A robust JavaScript library to parse XML/KML files into GeoJSON on the fly.  
* **Vanilla HTML/CSS/JS**: No heavy frontend frameworks required. Uses CSS variables for a clean dark mode theme.
* **Custom Timeline Scrubber** to Browse changes to the map through time
* **Experimental 3D front-ends using CesiumJS and Maplibre-GL**
* **Scale, Mini-map, Intuitive measurement tools and other bits and pieces**
* **Secure Admin functionality** behind Basic Auth and read only frontend
* **Persistent Styles**

### **Backend**

* **Python 3.11**  
* **FastAPI**: A lightning-fast, production-grade web framework that serves both the API endpoints and the static frontend files.  
* **Uvicorn**: ASGI web server implementation for Python.  
* **Python-Multipart**: For handling raw file uploads.
* **Rio-Tiler / GDAL / Cloud Optimised GeoTiff Mosaic Implementation** for Map Tiling / API and Sentinel-2 Imagery with caching
* **Doris is in there somewhere**


### **Mapping Providers**

* **OpenFreeMap**: Providing the 'Dark' and 'Light' vector tiles.
* **OpenTopoMap**: Topographic  tiles.
* **HOT**: Humanitarian Open Street Map tiles
* **Esri World Imagery**: Providing the high-resolution satellite raster tiles.
* **Esri Firefly**: Lower Saturation satellite tiles
* **Sentinel 2 Cloudless Imagery**: Mosaic of Sentinel 2 satellite imagery
* **Sentinel 2 L2A TRUE COLOUR / NATURAL COLOUR**: Latest Sentinel 2 satellite imagery mosaic tiles created on the fly from Sentinel 2 L2A 10m COGs on AWS. 
* **Custom hybrid layer:** Using OpenFreeMap vector tiles overlaid for each of the 5 satellite imagery providers

  
### **Data Providers**
* **Ukraine War FrontLines:** Functionality to load Ukraine war front line data from two mappers, calculate the differences between the two, draw the changes on that map using map markers with the historical data easily browsable using a timeline slider. Credit to JR for the original QGIS logic
* **NASA FIRMS:** Last 48 hours VIIRS satellite data (as raster tiles at lower zoom levels & CSV data plotted on the map and higher zoom levels
* **Sentinel 2 metadata:** To determine the created date of the Sentinel 2 imagery
* **OpenStreetMap polygon data** from Overpass Turbo API

## **🚀 Getting Started**

### **Prerequisites**

* Docker  
* Docker Compose

### **Installation**

1. Create a directory for the project and ensure your files are structured as follows:  
   mymaps/  
   ├── docker-compose.yml  
   ├── Dockerfile  
   ├── requirements.txt  
   ├── main.py  
   └── static/  
       └── index.html

2. Create a data directory in the root of your project:  
   mkdir data

   *(Optional)* You can drop any initial .kml or .kmz files into this folder before starting up.  
3. Build and run the Docker container:  
   docker-compose up \-d \--build

4. Access the application:  
   Open your web browser and navigate to http://localhost:8080 (or the respective port/IP if you are using Tailscale/host networking).

## **🗄 API Endpoints**

* GET /api/layers: Returns a JSON array of all active .kml files in the data directory.  
* POST /api/upload: Accepts multipart/form-data. Saves .kml files directly or extracts .kml from uploaded .kmz archives.  
* DELETE /api/layers/{filename}: Soft-deletes a specified layer by renaming it to {filename}.deleted.  
* GET /data/{filename}: Serves the raw KML file to the frontend.

## **🔮 Future Enhancements (Roadmap)**

* Full migration to MapLibre GL / Cesium JS for 3D terrain and 3D building support.  
* Some crazy 4D Gaussian Splatting to bring 4D Immersive models & walkable worlds to ATP audience
