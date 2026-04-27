import os
import shutil
import zipfile
import json
import httpx
import urllib.request
import tempfile
import os
import secrets
import httpx
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Body, Form, HTTPException, Request, Response, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from geoprocessing import load_kml, save_kml, run_ap_model, run_sm_model, copy_kml_styles
from titiler.core.factory import TilerFactory
import math
import mercantile
from fastapi.responses import RedirectResponse
from rio_tiler.io import Reader
from rio_tiler.mosaic import mosaic_reader
from rio_tiler.errors import TileOutsideBounds
import requests
from cachetools import cached, TTLCache
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mymaps-automation')

stac_cache = TTLCache(maxsize=100, ttl=300)

app = FastAPI()

# Enable CORS just in case
app.add_middleware(
    CORSMiddleware,
    # Replace with your actual public domain
    allow_origins=["*"],
    #allow_origins=["https://map.atpgeo.com", "http://localhost:8000, "http://100.74.180.38:8069"], 
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"], 
    allow_headers=["*"],
)

# --- 1. ADD TITILER ROUTER ---
# This instantly gives your FastAPI app the ability to serve map tiles from COGs!
cog_tiler = TilerFactory()
app.include_router(
    cog_tiler.router,
    prefix="/cog",
    tags=["Cloud Optimized GeoTIFF"]
)


@cached(cache=stac_cache)
def get_stac_urls(lat: float, lng: float):
    """Fetches the 5 latest AWS COG URLs for a 50km area, cached for speed."""
    stac_url = "https://earth-search.aws.element84.com/v1/search"
    
    # Create a bounding box roughly 100km wide around the center
    bbox = [lng - 0.5, lat - 0.5, lng + 0.5, lat + 0.5]
    
    payload = {
        "bbox": bbox,
        "collections": ["sentinel-2-l2a"],
        "query": {"eo:cloud_cover": {"lt": 20}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        "limit": 5  # Grab enough MGRS squares to stitch together seamlessly
    }
    
    response = requests.post(stac_url, json=payload)
    if response.status_code != 200:
        return []
        
    urls = []
    for item in response.json().get("features", []):
        href = item["assets"].get("visual", {}).get("href")
        if href:
            urls.append(href)
    return urls

def read_single_tile(url: str, x: int, y: int, z: int):
    with Reader(url) as src:
        return src.tile(x, y, z, tilesize=512, resampling_method="bilinear" # or "cubic" for even softer blending)

@app.get("/api/sentinel-latest/{z}/{x}/{y}.png")
def get_latest_sentinel(z: int, x: int, y: int):
    bounds = mercantile.bounds(x, y, z)
    
    # 1. Round the map coordinates to the nearest 0.5 degrees
    # If Leaflet asks for 15 tiles on a screen, they will all round to the same number,
    # meaning we only do ONE external STAC search instead of 15!
    center_lat = round((bounds.north + bounds.south) / 2 * 2) / 2
    center_lng = round((bounds.east + bounds.west) / 2 * 2) / 2
    
    # 2. Get the URLs (Hits the lightning-fast memory cache 14 out of 15 times)
    urls = get_stac_urls(center_lat, center_lng)
    
    if not urls:
        return Response(status_code=404, content="No imagery found")

    # 3. Stitch the overlapping MGRS squares together on the fly
    try:
        img_data, _ = mosaic_reader(urls, read_single_tile, x, y, z)
        img_buffer = img_data.render(img_format="PNG")
        return Response(content=img_buffer, media_type="image/png")
    except TileOutsideBounds:
        # Expected behaviour if the user pans completely off the data grid
        return Response(status_code=404, content="Tile outside data bounds")
    except Exception as e:
        print(f"Mosaic error: {e}")
        return Response(status_code=500, content="Failed to render mosaic")



#@app.get("/api/dynamic-topo/{z}/{x}/{y}.png")
#async def get_dynamic_topo(z: int, x: int, y: int):
#    """
#    Intercepts Leaflet's XYZ tile request, calculates the geographic coordinates,
#    finds the correct Copernicus DEM S3 URL, and redirects to Titiler to render it.
#    """
#    # 1. Get the geographical center of the requested map tile
#    bounds = mercantile.bounds(x, y, z)
#    center_lat = (bounds.north + bounds.south) / 2
#    center_lng = (bounds.east + bounds.west) / 2

    # 2. Format the exact Copernicus S3 grid reference dynamically
#    lat_floor = math.floor(center_lat)
#    lng_floor = math.floor(center_lng)
#
#    lat_str = f"N{lat_floor:02d}" if lat_floor >= 0 else f"S{abs(lat_floor):02d}"
#    lng_str = f"E{lng_floor:03d}" if lng_floor >= 0 else f"W{abs(lng_floor):03d}"

#    folder = f"Copernicus_DSM_COG_10_{lat_str}_00_{lng_str}_00_DEM"
#    s3_url = f"s3://copernicus-dem-30m/{folder}/{folder}.tif"

#    # 3. Redirect internally to the Titiler endpoint to do the heavy lifting
#    titiler_url = f"/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url={s3_url}&colormap_name=cfastie&rescale=0,1500"
    
#    return RedirectResponse(url=titiler_url)


DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)


# Grab secrets from the environment injected by Docker
SENTINEL_INSTANCE_ID = os.getenv("SENTINEL_INSTANCE_ID")
FIRMS_API_KEY = os.getenv("FIRMS_API_KEY")

# Grab admin credentials with fallbacks just in case the .env is missing
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")

# --- SECURITY SETUP ---
security = HTTPBasic()

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Checks the provided username and password securely."""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
# ----------------------

@app.get("/api/layers")
async def get_layers():
    """Returns a list of all KML files in the data directory."""
    files = []
    for f in DATA_DIR.iterdir():
        if f.is_file() and f.suffix.lower() == '.kml' and not f.name.startswith('Ukraine-Regions'):
            files.append(f.name)
    return {"layers": sorted(files)}

@app.post("/api/upload", dependencies=[Depends(verify_admin)])
async def upload_file(files: List[UploadFile] = File(...)):
    """Handles multiple KML and KMZ uploads, automatically extracting KMZ to KML."""
    results = []
    for file in files:
        file_ext = file.filename.lower().split('.')[-1]
        safe_filename = file.filename.replace(" ", "_")
        target_path = DATA_DIR / safe_filename

        # Save the uploaded file temporarily
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if file_ext == 'kmz':
            try:
                # Extract KML from the KMZ archive
                with zipfile.ZipFile(target_path, 'r') as zip_ref:
                    kml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.kml')]
                    if kml_files:
                        extracted_path = zip_ref.extract(kml_files[0], path="/tmp")
                        kml_filename = safe_filename[:-4] + ".kml"
                        final_kml_path = DATA_DIR / kml_filename
                        shutil.move(extracted_path, final_kml_path)
                        results.append({"message": "KMZ extracted and saved successfully", "filename": kml_filename})
                    else:
                        target_path.unlink(missing_ok=True)
                        return JSONResponse(status_code=400, content={"message": f"No KML file found inside {file.filename}"})
                # Remove the original KMZ file
                target_path.unlink(missing_ok=True)
            except Exception as e:
                target_path.unlink(missing_ok=True)
                return JSONResponse(status_code=400, content={"message": f"Failed to extract {file.filename}: {str(e)}"})
        else:
            results.append({"message": "KML saved successfully", "filename": safe_filename})
            
    return {"results": results}


@app.get("/api/settings")
async def get_settings():
    """Returns application settings and styles from settings.json."""
    settings_path = DATA_DIR / "settings.json"
    if settings_path.exists() and settings_path.is_file():
        try:
            with open(settings_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

@app.post("/api/settings", dependencies=[Depends(verify_admin)])
async def save_settings(settings: Dict[str, Any] = Body(...)):
    """Saves application settings and styles to settings.json."""
    settings_path = DATA_DIR / "settings.json"
    with open(settings_path, "w") as f:
        json.dump(settings, f)
    return {"message": "Settings saved successfully"}



class ProcessUpdateRequest(BaseModel):
    new_ap_url: str = ""
    new_sm_url: str = ""
    old_ap_filename: str = ""
    old_sm_filename: str = ""

def get_latest_layer(prefix: str) -> Optional[Path]:
    layers = []
    for f in DATA_DIR.iterdir():
        # Case insensitive check if prefix is in the filename (e.g. "AP Map" in "ap map 20 03.kml" or "AP Map_whatever.kml")
        if f.is_file() and prefix.lower() in f.name.lower() and f.name.endswith('.kml'):
            layers.append(f)
    if not layers:
        return None
    # sort by name
    return sorted(layers)[-1]

def download_file(url: str, dest: Path) -> bool:
    if not url: return False
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)

        # If it's a KMZ, extract it to KML
        if url.lower().endswith('.kmz') or url.lower().endswith('forcekml=1'):
            try:
                with zipfile.ZipFile(dest, 'r') as zip_ref:
                    kml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.kml')]
                    if kml_files:
                        extracted_path = zip_ref.extract(kml_files[0], path="/tmp")
                        shutil.move(extracted_path, dest)
            except zipfile.BadZipFile:
                pass # Probably already KML or something else
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

@app.post("/api/process_updates", dependencies=[Depends(verify_admin)])
def process_updates(
    new_ap_url: str = Form(""),
    new_sm_url: str = Form(""),
    old_ap_filename: str = Form(""),
    old_sm_filename: str = Form(""),
    update_date: str = Form(""),
    new_ap_file: Optional[UploadFile] = File(None),
    new_sm_file: Optional[UploadFile] = File(None)
):
    if not new_ap_url and not new_sm_url and not new_ap_file and not new_sm_file:
        raise HTTPException(status_code=400, detail="Must provide at least one URL or file")

    date_str = update_date if update_date else datetime.now().strftime("%Y-%m-%d")
    results = []


    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Ensure ukraine_provinces exists
        prov_path = DATA_DIR / "Ukraine-Regions.kml"
        if not prov_path.exists():
            logger.info("Copying missing ukraine_provinces KML for geoprocessing boundaries...")
            shutil.copy("static/Ukraine-Regions.kml", prov_path)

        if prov_path.exists():
            ukr_prov_gdf = load_kml(prov_path)
        else:
            logger.warning("Could not load ukr_prov_gdf, processing will run without country boundary clips!")
            ukr_prov_gdf = None

        # Process AP Map
        if new_ap_url or (new_ap_file and new_ap_file.filename):
            logger.info("--- Processing AP Map ---")
            if not old_ap_filename:
                logger.error("No base AP Map filename provided.")
                results.append({"status": "error", "layer": "AP Map", "message": "No base AP Map selected in UI."})
            else:
                latest_old_ap = DATA_DIR / old_ap_filename
                if not latest_old_ap.exists():
                    logger.error(f"Base AP Map {latest_old_ap} does not exist on disk.")
                    results.append({"status": "error", "layer": "AP Map", "message": f"Selected base file {old_ap_filename} not found."})
                else:
                    new_ap_path = tmp_path / "new_ap.kml"
                    success = False

                    if new_ap_file and new_ap_file.filename:
                        # Save uploaded file
                        logger.info("Saving uploaded AP file...")
                        file_ext = new_ap_file.filename.lower().split('.')[-1]
                        dest_path = new_ap_path if file_ext == 'kml' else tmp_path / "new_ap.kmz"
                        with open(dest_path, "wb") as buffer:
                            shutil.copyfileobj(new_ap_file.file, buffer)

                        if file_ext == 'kmz':
                            try:
                                with zipfile.ZipFile(dest_path, 'r') as zip_ref:
                                    kml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.kml')]
                                    if kml_files:
                                        extracted_path = zip_ref.extract(kml_files[0], path=tmp_path)
                                        shutil.move(extracted_path, new_ap_path)
                                        success = True
                            except zipfile.BadZipFile:
                                logger.error("Invalid AP KMZ file uploaded")
                        else:
                            success = True
                    else:
                        success = download_file(new_ap_url, new_ap_path)

                    if success:
                        logger.info(f"Loading base AP Map: {latest_old_ap}")
                        old_ap_gdf = load_kml(latest_old_ap)
                        logger.info("Loading new AP Map")
                        new_ap_gdf = load_kml(new_ap_path)

                        if old_ap_gdf.empty or new_ap_gdf.empty:
                            logger.error("Failed to parse one or both AP KMLs (they might be empty or invalid).")
                            results.append({"status": "error", "layer": "AP Map", "message": "Failed to parse AP KMLs. Check if URL returned valid KML/KMZ."})
                        else:
                            logger.info(f"Geoprocessing AP Maps: Old ({len(old_ap_gdf)} features) vs New ({len(new_ap_gdf)} features)")
                            map_out, pins_out = run_ap_model(old_ap_gdf, new_ap_gdf, ukr_prov_gdf)

                            out_map_name = f"AP Map {date_str}.kml"
                            out_pins_name = f"AP Pins {date_str}.kml"

                            logger.info(f"Saving new AP Map to {out_map_name}")
                            save_kml(map_out, DATA_DIR / out_map_name)
                            logger.info(f"Saving new AP Pins to {out_pins_name}")
                            save_kml(pins_out, DATA_DIR / out_pins_name)

                            logger.info("Copying KML styles from base layer...")
                            copy_kml_styles(latest_old_ap, DATA_DIR / out_map_name)
                            old_ap_pins = DATA_DIR / old_ap_filename.replace("Map", "Pins")
                            if old_ap_pins.exists():
                                copy_kml_styles(old_ap_pins, DATA_DIR / out_pins_name)

                            logger.info("AP Map update successful!")
                            results.append({"status": "success", "layer": "AP Map", "new_files": [out_map_name, out_pins_name]})
                    else:
                        results.append({"status": "error", "layer": "AP Map", "message": "Failed to acquire new AP Map (URL download or file upload failed)."})

        # Process SM Map
        if new_sm_url or (new_sm_file and new_sm_file.filename):
            logger.info("--- Processing SM Map ---")
            if not old_sm_filename:
                logger.error("No base SM Map filename provided.")
                results.append({"status": "error", "layer": "SM Map", "message": "No base SM Map selected in UI."})
            else:
                latest_old_sm = DATA_DIR / old_sm_filename
                if not latest_old_sm.exists():
                    logger.error(f"Base SM Map {latest_old_sm} does not exist on disk.")
                    results.append({"status": "error", "layer": "SM Map", "message": f"Selected base file {old_sm_filename} not found."})
                else:
                    new_sm_path = tmp_path / "new_sm.kml"
                    success = False

                    if new_sm_file and new_sm_file.filename:
                        # Save uploaded file
                        logger.info("Saving uploaded SM file...")
                        file_ext = new_sm_file.filename.lower().split('.')[-1]
                        dest_path = new_sm_path if file_ext == 'kml' else tmp_path / "new_sm.kmz"
                        with open(dest_path, "wb") as buffer:
                            shutil.copyfileobj(new_sm_file.file, buffer)

                        if file_ext == 'kmz':
                            try:
                                with zipfile.ZipFile(dest_path, 'r') as zip_ref:
                                    kml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.kml')]
                                    if kml_files:
                                        extracted_path = zip_ref.extract(kml_files[0], path=tmp_path)
                                        shutil.move(extracted_path, new_sm_path)
                                        success = True
                            except zipfile.BadZipFile:
                                logger.error("Invalid SM KMZ file uploaded")
                        else:
                            success = True
                    else:
                        success = download_file(new_sm_url, new_sm_path)

                    if success:
                        logger.info(f"Loading base SM Map: {latest_old_sm}")
                        old_sm_gdf = load_kml(latest_old_sm)
                        logger.info("Loading new SM Map")
                        new_sm_gdf = load_kml(new_sm_path)

                        if old_sm_gdf.empty or new_sm_gdf.empty:
                            logger.error("Failed to parse one or both SM KMLs (they might be empty or invalid).")
                            results.append({"status": "error", "layer": "SM Map", "message": "Failed to parse SM KMLs. Check if URL returned valid KML/KMZ."})
                        else:
                            logger.info(f"Geoprocessing SM Maps: Old ({len(old_sm_gdf)} features) vs New ({len(new_sm_gdf)} features)")
                            map_out, pins_out = run_sm_model(old_sm_gdf, new_sm_gdf, ukr_prov_gdf)

                            out_map_name = f"SM Map {date_str}.kml"
                            out_pins_name = f"SM Pins {date_str}.kml"

                            logger.info(f"Saving new SM Map to {out_map_name}")
                            save_kml(map_out, DATA_DIR / out_map_name)
                            logger.info(f"Saving new SM Pins to {out_pins_name}")
                            save_kml(pins_out, DATA_DIR / out_pins_name)

                            logger.info("Copying KML styles from base layer...")
                            copy_kml_styles(latest_old_sm, DATA_DIR / out_map_name)
                            old_sm_pins = DATA_DIR / old_sm_filename.replace("Map", "Pins")
                            if old_sm_pins.exists():
                                copy_kml_styles(old_sm_pins, DATA_DIR / out_pins_name)

                            logger.info("SM Map update successful!")
                            results.append({"status": "success", "layer": "SM Map", "new_files": [out_map_name, out_pins_name]})
                    else:
                        results.append({"status": "error", "layer": "SM Map", "message": "Failed to acquire new SM Map (URL download or file upload failed)."})

    return {"results": results}


@app.delete("/api/layers/{filename}", dependencies=[Depends(verify_admin)])
async def delete_layer(filename: str):
    """Safeguards the file by renaming it with a .deleted extension."""
    file_path = DATA_DIR / filename
    if file_path.exists() and file_path.is_file():
        # Rename instead of permanent deletion
        file_path.rename(file_path.with_suffix('.kml.deleted'))
        return {"message": "Layer archived"}
    return {"error": "File not found"}

# Serve the data directory so the frontend can fetch the KML files
app.mount("/data", StaticFiles(directory="/app/data"), name="data")

# Serve the frontend HTML
@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

@app.get("/api/sentinel")
def proxy_sentinel(request: Request):
    """Proxies Sentinel Hub WMS requests to hide the Instance ID."""
    # Grab the exact parameters Leaflet sent (e.g. bbox, width, height)
    query_string = request.url.query
    url = f"https://sh.dataspace.copernicus.eu/ogc/wms/{SENTINEL_INSTANCE_ID}?{query_string}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = response.read()
            # WMS GetMap returns images (png/jpeg), GetFeatureInfo returns JSON
            content_type = response.headers.get('Content-Type', 'image/png')
            return Response(content=data, media_type=content_type)
    except Exception as e:
        logger.error(f"Sentinel Proxy Error: {e}")
        raise HTTPException(status_code=500, detail="Error fetching satellite data")

@app.get("/api/firms/{source}/{bbox}")
def proxy_firms(source: str, bbox: str):
    """Securely proxies NASA FIRMS requests so the API key never reaches the browser."""
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_API_KEY}/{source}/{bbox}/2"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            csv_data = response.read()
            return Response(content=csv_data, media_type="text/csv")
    except Exception as e:
        logger.error(f"NASA FIRMS Proxy Error: {e}")
        raise HTTPException(status_code=500, detail="Error fetching thermal data")

@app.get("/admin", dependencies=[Depends(verify_admin)])
async def serve_admin():
    return FileResponse("static/index.html")

# Serve the admin script ONLY to authenticated users
@app.get("/admin_assets/map-admin.js", dependencies=[Depends(verify_admin)])
async def serve_admin_js():
    return FileResponse("admin_assets/map-admin.js")

@app.get("/maplibre")
async def serve_maplibre():
    return FileResponse("static/maplibre.html")

@app.get("/cesium")
async def serve_cesium():
    return FileResponse("static/cesium.html")

# Serve any other static assets if needed
app.mount("/", StaticFiles(directory="static"), name="static")
