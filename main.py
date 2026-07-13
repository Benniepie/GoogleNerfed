import os
import shutil
import zipfile
import json
import httpx
import urllib.request
import urllib.parse
import tempfile
import os
import secrets
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
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
import rasterio
import requests
import asyncio
from cachetools import cached, TTLCache
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mymaps-automation')

def secure_filename(filename: str) -> str:
    if not filename:
        return "unnamed"
    # Convert backslashes to forward slashes just in case
    normalized = filename.replace("\\", "/")
    basename = os.path.basename(normalized)
    if not basename or basename in {".", ".."}:
        return "unnamed"
    return basename.replace(" ", "_")

stac_cache = TTLCache(maxsize=100, ttl=300)

app = FastAPI()

# Create a global connection pool
_radar_polling_task = None
http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=50, max_connections=100),
    timeout=4.0
)
import anyio
import fcntl
import os

_radar_lock_file = None

@app.on_event("startup")
async def startup_event():
    global _radar_polling_task
    global _radar_lock_file

    lock_path = DATA_DIR / "radar_polling.lock"
    try:
        import fcntl
        _radar_lock_file = open(lock_path, "w")
        fcntl.flock(_radar_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info("Acquired radar polling lock. Starting background task.")
        _radar_polling_task = asyncio.create_task(poll_radar_russia_background())
    except (BlockingIOError, IOError, ModuleNotFoundError):
        logger.info("Another worker is already running the radar polling task (or fcntl unavailable).")
        if _radar_lock_file:
            _radar_lock_file.close()
        _radar_lock_file = None

    # 3 threads per worker * 4 workers = 12 total background threads max
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = 3
@app.on_event("shutdown")
async def shutdown_event():
    global _radar_polling_task
    global _radar_lock_file
    if _radar_polling_task:
        _radar_polling_task.cancel()
    if _radar_lock_file:
        import fcntl
        fcntl.flock(_radar_lock_file, fcntl.LOCK_UN)
        _radar_lock_file.close()
    await http_client.aclose()

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
def boxes_intersect(tile_bounds, item_bbox):
    """Checks if the Leaflet tile physically overlaps the STAC image footprint"""
    t_west, t_south, t_east, t_north = tile_bounds
    i_west, i_south, i_east, i_north = item_bbox
    return not (t_east < i_west or t_west > i_east or t_north < i_south or t_south > i_north)

@cached(cache=stac_cache)
def get_stac_features(lat: float, lng: float, z: float):
    """Fetches the 5 latest AWS COG URLs for a 50km area, cached for speed."""
    stac_url = "https://earth-search.aws.element84.com/v1/search"
    
    # Create a bounding box roughly 100km wide around the center
    bbox = [lng - 0.5, lat - 0.5, lng + 0.5, lat + 0.5]
    search_limit = 40 if z <= 12 else 20
    payload = {
        "bbox": bbox,
        "collections": ["sentinel-2-l2a"],
        "query": {"eo:cloud_cover": {"lt": 20}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        "limit": search_limit
    }
    
    response = requests.post(stac_url, json=payload)
    if response.status_code != 200:
        logger.error("STAC API failed to respond")
        return []
    return response.json().get("features", [])    
    
@app.get("/api/sentinel-metadata")
def get_sentinel_metadata(lat: float, lng: float, z: float):
    """Returns a GeoJSON FeatureCollection of the cached STAC data."""
    # We round the coordinates just like the tile endpoint to hit the same cache key
    center_lat = round(lat * 2) / 2
    center_lng = round(lng * 2) / 2
    
    features = get_stac_features(center_lat, center_lng, z)
    
    return {"type": "FeatureCollection", "features": features}




def read_single_tile(url: str, x: int, y: int, z: int):
    # These settings optimize GDAL for cloud storage
    env_kwargs = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "GDAL_HTTP_MAX_RETRY": 3,
        "GDAL_HTTP_RETRY_DELAY": 1,
        "VSI_CACHE": True,
        "GDAL_INGESTED_BYTES_AT_OPEN": 32768
    }
    
    # The Env block creates the connection pool for this specific thread
    with rasterio.Env(**env_kwargs):
        with Reader(url) as src:
            return src.tile(x, y, z, tilesize=512, resampling_method="bilinear")

@app.get("/api/sentinel-latest/{z}/{x}/{y}.webp")
def get_latest_sentinel(z: int, x: int, y: int):
    bounds = mercantile.bounds(x, y, z)
    
    # 1. Round the map coordinates to the nearest 0.5 degrees
    # If Leaflet asks for 15 tiles on a screen, they will all round to the same number,
    # meaning we only do ONE external STAC search instead of 15!
    center_lat = round((bounds.north + bounds.south) / 2 * 2) / 2
    center_lng = round((bounds.east + bounds.west) / 2 * 2) / 2
    
    # 2. Get the URLs (Hits the lightning-fast memory cache 14 out of 15 times)
    
    features = get_stac_features(center_lat, center_lng, z)
    
    urls = []
    for item in features:
        item_bbox = item.get("bbox")
        # ONLY add the URL if the image physically touches this specific map tile
        if item_bbox and boxes_intersect((bounds.west, bounds.south, bounds.east, bounds.north), item_bbox):
            href = item["assets"].get("visual", {}).get("href")
            if href:
                urls.append(href)

    logger.info(f"--- STAC SEARCH FOR ZOOM {z} ---")
    logger.info(f"Found {len(urls)} scenes.")
    for u in urls:
        logger.info(f"COG: {u}")
        
    if not urls:
        return Response(status_code=404, content="No imagery found")

    # 3. Stitch the overlapping MGRS squares together on the fly
    try:
        img_data, _ = mosaic_reader(urls, read_single_tile, x, y, z)
        if img_data.mask.max() == 0:
             return Response(status_code=404, content="Tile has no valid data pixels")
        
        img_buffer = img_data.render(img_format="WEBP", **{"quality": 80})
        return Response(content=img_buffer, media_type="image/webp")
        
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
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    ADMIN_PASSWORD = secrets.token_urlsafe(32)
    logger.warning(f"No ADMIN_PASSWORD set in environment. Generated temporary password: {ADMIN_PASSWORD}")

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

# --- TELEGRAM SCRAPER LOGIC ---
def get_radar_icon(location_str, threat_str):
    combined = (location_str + " " + threat_str).lower()
    if any(kw in combined for kw in ["аэропорт", "аэродром", "airport", "авиабаза", "air base"]): return "✈️"
    if any(kw in combined for kw in ["нпз", "нефте", "oil", "naval base", "порт", "терминал", "refinery"]): return "⚓"
    if any(kw in combined for kw in ["море", "залив", "sea", "вода", "океан", "акватория"]): return "🌊"
    if any(kw in combined for kw in ["база", "base", "вч", "войсковая часть", "military"]): return "🪖"
    return ""

def parse_telegram_message(text: str, msg_id: str, time_str: str) -> dict:
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line: continue
        # Filter out boilerplate
        if any(kw in line for kw in ["❗️", "Обход белых списков", "@radarrussiia", "Радар по всей России", "Internet_Boost_bot", "🌐", "Ускоритель Интернета", "Остались какие-то вопросы"]):
            continue
        cleaned_lines.append(line)

    threat_keywords = ["опасность", "фиксация", "отбой", "работа", "пво", "ракет", "бпла", "приготовиться", "тревога", "меры", "сбит", "угроза", "внимание"]

    locations = []
    threats = []

    for line in cleaned_lines:
        parts = line.split(' - ')
        for part in parts:
            part = part.strip()
            is_threat = any(kw in part.lower() for kw in threat_keywords)
            if is_threat or len(part) > 60:
                threats.append(part)
            else:
                for loc in part.split(','):
                    loc_clean = loc.strip()
                    loc_clean = re.sub(r'(?i)и близлежащие', '', loc_clean).strip()
                    if loc_clean:
                        locations.append(loc_clean)

    status_val = "active"
    if any("отбой" in t.lower() for t in threats):
        status_val = "over"

    # Determine the most specific locations (filter out broad contexts if a town is mentioned)
    context_keywords = ["область", "край", "республика", "окг", "округ", "крым", "район"]
    context = ""
    for loc in reversed(locations):
        if any(x in loc.lower() for x in context_keywords):
            context = loc
            break

    final_locs = []
    combined_threat = " | ".join(threats)

    # Translation dictionary for locations
    location_translations = {
        "мордовия": "Mordovia",
        "республика": "Republic",
        "область": "Oblast",
        "край": "Krai",
        "район": "District"
    }

    # Simple manual translation dictionary for common radar terms
    threat_translations = {
        "опасность по бпла": "UAV Danger",
        "ракетная опасность": "Missile Danger",
        "отбой опасности по бпла": "UAV Danger Over",
        "отбой ракетной опасности": "Missile Danger Over",
        "фиксация бпла": "UAV Detected",
        "работа пво": "Air Defense Active",
        "тревога": "Alarm",
        "сбиты": "Shot Down",
        "сбит": "Shot Down",
        "внимание": "Attention",
        "угроза": "Threat",
        "отбой": "All Clear / Over",
        "реактивным": "Jet",
        "волна": "Wave",
        "приготовиться к волне бпла": "Prepare for UAV wave",
        "в вашем направлении": "in your direction",
        "со стороны": "from the direction of",
        "крылатые ракеты большой дальности": "long-range cruise missiles",
        "возможно от": "possibly from"
    }

    english_threat = combined_threat
    for ru, en in threat_translations.items():
        english_threat = re.sub(re.escape(ru), en, english_threat, flags=re.IGNORECASE)

    # If there are multiple locations, don't just use context
    if len(locations) > 1:
        # Filter out locations that are just broad contexts if there are more specific ones
        specific_locs = [loc for loc in locations if not any(x in loc.lower() for x in context_keywords)]
        if not specific_locs:
            specific_locs = locations # Use all if all are broad

        # We'll use the specific locations and optionally append context
        for loc in specific_locs:
            translated_loc = loc
            for ru, en in location_translations.items():
                translated_loc = re.sub(re.escape(ru), en, translated_loc, flags=re.IGNORECASE)

            full_name = loc
            if context and loc != context:
                full_name = f"{loc}, {context}"

            translated_full = full_name
            for ru, en in location_translations.items():
                translated_full = re.sub(re.escape(ru), en, translated_full, flags=re.IGNORECASE)

            final_locs.append({"name": translated_full, "icon": get_radar_icon(loc, combined_threat)})
    else:
        for loc in locations:
            translated_loc = loc
            for ru, en in location_translations.items():
                translated_loc = re.sub(re.escape(ru), en, translated_loc, flags=re.IGNORECASE)

            final_locs.append({"name": translated_loc, "icon": get_radar_icon(loc, combined_threat)})

    return {
        "id": msg_id,
        "time": time_str,
        "locations": final_locs,
        "threat": english_threat if english_threat else combined_threat,
        "status": status_val
    }
async def poll_radar_russia_background():
    """Background task to poll radar alerts every 60 seconds."""
    while True:
        try:
            await fetch_and_cache_radar_russia()
        except Exception as e:
            logger.error(f"Background radar polling error: {e}")
        await asyncio.sleep(60)

async def fetch_and_cache_radar_russia():
    url = "https://t.me/s/radarrussiia"
    try:
        response = await http_client.get(url, timeout=10.0)
        html = response.text
    except Exception as e:
        logger.error(f"Failed to fetch Telegram channel: {e}")
        return

    soup = BeautifulSoup(html, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_wrap')

    cache_file = DATA_DIR / "radar_alerts.json"
    cached_alerts = {}
    if cache_file.exists():
        try:
            import json
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_alerts = json.load(f)
        except Exception:
            pass

    now = datetime.now(timezone.utc)

    # Prune old alerts (> 24 hours)
    for msg_id in list(cached_alerts.keys()):
        try:
            alert_time = datetime.fromisoformat(cached_alerts[msg_id]['time'].replace('Z', '+00:00'))
            if (now - alert_time).total_seconds() > 24 * 3600:
                del cached_alerts[msg_id]
        except Exception:
            del cached_alerts[msg_id]

    # Process new alerts
    for msg in messages:
        msg_el = msg.find('div', class_='tgme_widget_message')
        if not msg_el: continue
        msg_id = msg_el.get('data-post', '')

        text_div = msg.find('div', class_='tgme_widget_message_text')
        if not text_div: continue
        text = text_div.get_text(separator='\n').strip()


        time_tag = msg.find('time')
        time_str = time_tag.get('datetime', '') if time_tag else ''

        if not time_str:
            continue

        parsed = parse_telegram_message(text, msg_id, time_str)
        cached_alerts[msg_id] = parsed

    # Fully resolve missing geocodes in the background
    geocode_cache = {}
    gc_file = DATA_DIR / "geocode_cache.json"
    if gc_file.exists():
        try:
            with open(gc_file, "r", encoding="utf-8") as f:
                import json
                geocode_cache = json.load(f)
        except:
            pass

    for msg_id, parsed in cached_alerts.items():
        for loc_info in parsed["locations"]:
            await get_cached_geocode(loc_info["name"], cache_dict=geocode_cache)

    temp_file = cache_file.with_suffix('.tmp')
    with open(temp_file, "w", encoding="utf-8") as f:
        import json
        json.dump(cached_alerts, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, cache_file)


async def get_cached_geocode(location_name: str, cache_dict: Optional[dict] = None) -> Optional[dict]:
    cache_file = DATA_DIR / "geocode_cache.json"
    cache = cache_dict if cache_dict is not None else {}
    if cache_dict is None and cache_file.exists():
        try:
            import json
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass

    if location_name in cache:
        res = cache[location_name]
        return res if "empty" not in res else None

    # Use extremely aggressive simplification (0.05) to reduce polygon size
    # and restrict responses to Russia and Ukraine only (countrycodes=ru,ua) to prevent huge global multi-polygons
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location_name)}&format=json&polygon_geojson=1&limit=1&polygon_threshold=0.005&countrycodes=ru,ua&accept-language=en"
    headers = {'User-Agent': 'ATPGeopolitics/1.0'}
    try:
        resp = await http_client.get(url, headers=headers, timeout=10.0)
        data = resp.json()
        await asyncio.sleep(1.5)

        if data:
            result = data[0]
        else:
            result = {"empty": True} # Negative cache

        cache[location_name] = result
        # Atomic write to prevent JSONDecodeError from race conditions
        temp_file = cache_file.with_suffix('.tmp')
        with open(temp_file, "w", encoding="utf-8") as f:
            import json
            json.dump(cache, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, cache_file)

        return result if "empty" not in result else None
    except Exception as e:
        logger.error(f"Geocode error for {location_name}: {e}")

    return None

@app.get("/api/radar-russia")
async def get_radar_russia_alerts(since: Optional[str] = None):
    cache_file = DATA_DIR / "radar_alerts.json"
    cached_alerts = {}
    if cache_file.exists():
        try:
            import json
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_alerts = json.load(f)
        except Exception as e:
            logger.error(f"Error reading radar alerts cache: {e}")
            raise HTTPException(status_code=500, detail="Error reading radar data cache")

    features = []

    # Load cache once per API request
    geocode_cache = {}
    gc_file = DATA_DIR / "geocode_cache.json"
    if gc_file.exists():
        try:
            with open(gc_file, "r", encoding="utf-8") as f:
                import json
                geocode_cache = json.load(f)
        except:
            pass

    for msg_id, parsed in cached_alerts.items():
        # Delta filtering: If `since` is provided, skip older records
        if since:
            try:
                # Use strptime to be safe if fromisoformat fails on timezone
                alert_time = datetime.fromisoformat(parsed["time"].replace('Z', '+00:00'))
                # Replace ' ' with '+' in case urllib.parse unquoted the '+' to a space
                since_time_str = since.replace(' ', '+').replace('Z', '+00:00')
                since_time = datetime.fromisoformat(since_time_str)

                # Make timezone naive if one is naive and other is aware, or just use timestamp
                if alert_time.timestamp() <= since_time.timestamp():
                    continue
            except Exception as e:
                # Print exception here for safety
                print(f"Date parse error in since parameter: {e}")
                pass # Parse error, include it anyway

        for loc_info in parsed["locations"]:
            geo_data = await get_cached_geocode(loc_info["name"], cache_dict=geocode_cache)
            if geo_data and "geojson" in geo_data:
                feature = {
                    "type": "Feature",
                    "properties": {
                        "id": parsed["id"],
                        "time": parsed["time"],
                        "name": geo_data.get("name", loc_info["name"]),
                        "threat": parsed["threat"],
                        "status": parsed["status"],
                        "icon": loc_info["icon"]
                    },
                    "geometry": geo_data["geojson"]
                }
                features.append(feature)

    return {"type": "FeatureCollection", "features": features}

# ------------------------------

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
        if not file.filename:
            continue
        safe_filename = secure_filename(file.filename)
        file_ext = safe_filename.lower().split('.')[-1]
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



@app.get("/api/firms/combined/{bbox}")
async def proxy_firms_combined(bbox: str):
    """Fetches all 3 VIIRS satellites concurrently and returns one stitched CSV."""
    sources = ["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "VIIRS_SNPP_NRT"]
    
    # 1. Create the 3 NASA URLs
    urls = [
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_API_KEY}/{source}/{bbox}/2"
        for source in sources
    ]
    
    # 2. Fire all 3 requests to NASA at the exact same time
    try:
        responses = await asyncio.gather(
            *[http_client.get(url) for url in urls],
            return_exceptions=True # Don't crash if one satellite fails
        )
    except Exception as e:
        logger.error(f"Failed to fetch from NASA: {e}")
        raise HTTPException(status_code=500, detail="Error fetching thermal data")

    combined_csv_lines = []
    header_added = False

    # 3. Stitch the CSVs together
    for response in responses:
        if isinstance(response, Exception):
            logger.warning(f"A NASA request failed: {response}")
            continue
            
        if response.status_code == 429:
            logger.warning("NASA FIRMS Rate Limit Hit")
            continue
            
        if response.status_code == 200 and response.text.strip():
            lines = response.text.strip().split('\n')
            if not lines:
                continue
                
            # Only add the CSV header row once
            if not header_added:
                combined_csv_lines.append(lines[0])
                header_added = True
                
            # Add the actual data rows (skipping the header)
            combined_csv_lines.extend(lines[1:])

    # If all 3 failed or returned empty, return 204 No Content
    if not header_added or len(combined_csv_lines) == 1:
        return Response(status_code=204, content="")

    final_csv = '\n'.join(combined_csv_lines)
    return Response(content=final_csv, media_type="text/csv")




@app.get("/api/firms/{source}/{bbox}")
async def proxy_firms(source: str, bbox: str):
    """Securely proxies NASA FIRMS requests so the API key never reaches the browser."""
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_API_KEY}/{source}/{bbox}/2"
    try:
        response = await http_client.get(url)
        if response.status_code == 429:
            logger.warning("NASA FIRMS Rate Limit Hit")
            return Response(status_code=429, content="")
        return Response(content=response.text, media_type="text/csv")
    except httpx.TimeoutException:
        # If NASA tarpits us, drop it immediately and return an empty CSV
        logger.warning(f"NASA FIRMS timeout for {bbox}")
        return Response(status_code=204, content="") # 204 No Content
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
