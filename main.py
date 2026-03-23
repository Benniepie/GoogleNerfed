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



app = FastAPI()

# Enable CORS just in case
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/api/layers")
async def get_layers():
    """Returns a list of all KML files in the data directory."""
    files = []
    for f in DATA_DIR.iterdir():
        if f.is_file() and f.suffix.lower() == '.kml':
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




import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mymaps-automation")

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
    logger.info(f"Starting download from: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)

        logger.info(f"Successfully downloaded file to {dest}. Size: {dest.stat().st_size} bytes")

        # Check if it's a KMZ by trying to open it as a zip
        try:
            with zipfile.ZipFile(dest, 'r') as zip_ref:
                logger.info("File identified as ZIP/KMZ archive. Extracting...")
                kml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.kml')]
                if kml_files:
                    logger.info(f"Found KML inside archive: {kml_files[0]}")
                    extracted_path = zip_ref.extract(kml_files[0], path="/tmp")
                    shutil.move(extracted_path, dest)
                    logger.info("Extracted KML successfully.")
                else:
                    logger.warning("No KML files found inside the KMZ archive.")
        except zipfile.BadZipFile:
            logger.info("File is not a valid zip archive, assuming it's raw KML.")

        return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return False

@app.post("/api/process_updates")
def process_updates(req: ProcessUpdateRequest):
    if not req.new_ap_url and not req.new_sm_url:
        raise HTTPException(status_code=400, detail="Must provide at least one URL")

    date_str = datetime.now().strftime("%Y-%m-%d")
    results = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Process AP Map
        if req.new_ap_url:
            logger.info("--- Processing AP Map ---")
            if not req.old_ap_filename:
                logger.error("No base AP Map filename provided.")
                results.append({"status": "error", "layer": "AP Map", "message": "No base AP Map selected in UI."})
            else:
                latest_old_ap = DATA_DIR / req.old_ap_filename
                if not latest_old_ap.exists():
                    logger.error(f"Base AP Map {latest_old_ap} does not exist on disk.")
                    results.append({"status": "error", "layer": "AP Map", "message": f"Selected base file {req.old_ap_filename} not found."})
                else:
                    new_ap_path = tmp_path / "new_ap.kml"
                    if download_file(req.new_ap_url, new_ap_path):
                        logger.info(f"Loading base AP Map: {latest_old_ap}")
                        old_ap_gdf = load_kml(latest_old_ap)
                        logger.info("Loading downloaded new AP Map")
                        new_ap_gdf = load_kml(new_ap_path)

                        if old_ap_gdf.empty or new_ap_gdf.empty:
                            logger.error("Failed to parse one or both AP KMLs (they might be empty or invalid).")
                            results.append({"status": "error", "layer": "AP Map", "message": "Failed to parse AP KMLs. Check if URL returned valid KML/KMZ."})
                        else:
                            logger.info(f"Geoprocessing AP Maps: Old ({len(old_ap_gdf)} features) vs New ({len(new_ap_gdf)} features)")
                            map_out, pins_out = run_ap_model(old_ap_gdf, new_ap_gdf)

                            out_map_name = f"AP Map {date_str}.kml"
                            out_pins_name = f"AP Pins {date_str}.kml"

                            logger.info(f"Saving new AP Map to {out_map_name}")
                            save_kml(map_out, DATA_DIR / out_map_name)
                            logger.info(f"Saving new AP Pins to {out_pins_name}")
                            save_kml(pins_out, DATA_DIR / out_pins_name)

                            logger.info("Copying KML styles from base layer...")
                            copy_kml_styles(latest_old_ap, DATA_DIR / out_map_name)
                            copy_kml_styles(latest_old_ap, DATA_DIR / out_pins_name)

                            logger.info("AP Map update successful!")
                            results.append({"status": "success", "layer": "AP Map", "new_files": [out_map_name, out_pins_name]})
                    else:
                        results.append({"status": "error", "layer": "AP Map", "message": "Failed to download AP Map from URL."})

        # Process SM Map
        if req.new_sm_url:
            logger.info("--- Processing SM Map ---")
            if not req.old_sm_filename:
                logger.error("No base SM Map filename provided.")
                results.append({"status": "error", "layer": "SM Map", "message": "No base SM Map selected in UI."})
            else:
                latest_old_sm = DATA_DIR / req.old_sm_filename
                if not latest_old_sm.exists():
                    logger.error(f"Base SM Map {latest_old_sm} does not exist on disk.")
                    results.append({"status": "error", "layer": "SM Map", "message": f"Selected base file {req.old_sm_filename} not found."})
                else:
                    new_sm_path = tmp_path / "new_sm.kml"
                    if download_file(req.new_sm_url, new_sm_path):
                        logger.info(f"Loading base SM Map: {latest_old_sm}")
                        old_sm_gdf = load_kml(latest_old_sm)
                        logger.info("Loading downloaded new SM Map")
                        new_sm_gdf = load_kml(new_sm_path)

                        if old_sm_gdf.empty or new_sm_gdf.empty:
                            logger.error("Failed to parse one or both SM KMLs (they might be empty or invalid).")
                            results.append({"status": "error", "layer": "SM Map", "message": "Failed to parse SM KMLs. Check if URL returned valid KML/KMZ."})
                        else:
                            logger.info(f"Geoprocessing SM Maps: Old ({len(old_sm_gdf)} features) vs New ({len(new_sm_gdf)} features)")
                            map_out, pins_out = run_sm_model(old_sm_gdf, new_sm_gdf)

                            out_map_name = f"SM Map {date_str}.kml"
                            out_pins_name = f"SM Pins {date_str}.kml"

                            logger.info(f"Saving new SM Map to {out_map_name}")
                            save_kml(map_out, DATA_DIR / out_map_name)
                            logger.info(f"Saving new SM Pins to {out_pins_name}")
                            save_kml(pins_out, DATA_DIR / out_pins_name)

                            logger.info("Copying KML styles from base layer...")
                            copy_kml_styles(latest_old_sm, DATA_DIR / out_map_name)
                            copy_kml_styles(latest_old_sm, DATA_DIR / out_pins_name)

                            logger.info("SM Map update successful!")
                            results.append({"status": "success", "layer": "SM Map", "new_files": [out_map_name, out_pins_name]})
                    else:
                        results.append({"status": "error", "layer": "SM Map", "message": "Failed to download SM Map from URL."})

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
