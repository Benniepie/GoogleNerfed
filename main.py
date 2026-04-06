import os
import shutil
import zipfile
import json
import urllib.request
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Body, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from geoprocessing import load_kml, save_kml, run_ap_model, run_sm_model, copy_kml_styles
from titiler.core.factory import TilerFactory
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mymaps-automation')



app = FastAPI()

# Enable CORS just in case
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ADD TITILER ROUTER HERE ---
# This instantly gives your FastAPI app the ability to serve map tiles from COGs!
cog_tiler = TilerFactory()
app.include_router(
    cog_tiler.router,
    prefix="/cog",
    tags=["Cloud Optimized GeoTIFF"]
)
# -------------------------------

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/api/layers")
async def get_layers():
    """Returns a list of all KML files in the data directory."""
    files = []
    for f in DATA_DIR.iterdir():
        if f.is_file() and f.suffix.lower() == '.kml' and not f.name.startswith('Ukraine-Regions'):
            files.append(f.name)
    return {"layers": sorted(files)}

@app.post("/api/upload")
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
                # Remove the original KMZ file
                target_path.unlink(missing_ok=True)
                results.append({"message": "KMZ extracted and saved successfully", "filename": kml_filename})
            except zipfile.BadZipFile:
                target_path.unlink(missing_ok=True)
                results.append({"error": f"Invalid KMZ file: {file.filename}"})
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

@app.post("/api/settings")
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

@app.post("/api/process_updates")
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


@app.delete("/api/layers/{filename}")
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

@app.get("/maplibre")
async def serve_maplibre():
    return FileResponse("static/maplibre.html")

@app.get("/cesium")
async def serve_cesium():
    return FileResponse("static/cesium.html")

# Serve any other static assets if needed
app.mount("/", StaticFiles(directory="static"), name="static")
