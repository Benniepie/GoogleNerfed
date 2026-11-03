import os
import sys
import uuid
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
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from fastapi import FastAPI, APIRouter, UploadFile, File, Body, Form, HTTPException, Request, Response, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from geoprocessing import load_kml, save_kml, run_ap_model, run_sm_model, copy_kml_styles
from telegram_config import CHANNEL_CONFIGS
from telegram_shared import (
    resolve_data_dir,
    should_skip_radar_message,
    get_radar_icon,
    parse_telegram_message,
    init_radar_history_db,
    record_alert_to_history_db,
    record_incident_to_history_db,
    save_incident_to_live_cache,
)
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
import os

_radar_lock_file = None

@app.on_event("startup")
async def startup_event():
    global _radar_polling_task
    global _radar_lock_file

    def init_vessels_db():
        conn = sqlite3.connect(DATA_DIR / "vessels.db")
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vessels (
            mmsi TEXT PRIMARY KEY,
            name TEXT,
            ship_type TEXT,
            heading REAL,
            last_seen TEXT,
            last_lon REAL,
            last_lat REAL
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracks (
            mmsi TEXT,
            lon REAL,
            lat REAL,
            timestamp TEXT
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shadow_fleet_targets (
            mmsi TEXT PRIMARY KEY,
            imo TEXT,
            name TEXT,
            flag TEXT
        )
        ''')
        conn.commit()
        conn.close()

    init_vessels_db()
    init_radar_history_db(DATA_DIR)

    lock_path = DATA_DIR / "radar_polling.lock"
    try:
        import fcntl
        _radar_lock_file = open(lock_path, "w")
        fcntl.flock(_radar_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info("Acquired radar polling lock. Starting background task.")
        _radar_polling_task = asyncio.create_task(poll_radar_russia_background())
    except ModuleNotFoundError:
        logger.info("fcntl unavailable (Windows); starting radar polling task directly.")
        _radar_polling_task = asyncio.create_task(poll_radar_russia_background())
    except (BlockingIOError, IOError):
        logger.info("Another worker is already running the radar polling task.")
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
        try:
            import fcntl
            fcntl.flock(_radar_lock_file, fcntl.LOCK_UN)
        except Exception:
            pass
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


DATA_DIR = resolve_data_dir()


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
# `get_radar_icon` and `parse_telegram_message` are imported from `telegram_shared.py`
# so both the HTTP fallback scraper and the Telethon multi-channel worker share the exact
# same parsing, context-fallback, and geolocation rules.

async def poll_radar_russia_background():
    """Background task to poll radar alerts every 60 seconds."""
    while True:
        try:
            await fetch_and_cache_radar_russia()
        except Exception as e:
            logger.error(f"Background radar polling error: {e}")
        await asyncio.sleep(60)

async def fetch_and_cache_radar_russia():
    url = "https://telegram.me/s/radarrussiia"
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
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_alerts = json.load(f)
        except Exception:
            pass

    now = datetime.now(timezone.utc)

    # Prune old alerts (> 24 hours)
    for msg_id in list(cached_alerts.keys()):
        try:
            alert_time = datetime.fromisoformat(cached_alerts[msg_id]['time'].replace('Z', '+00:00'))
            if alert_time.tzinfo is None:
                alert_time = alert_time.replace(tzinfo=timezone.utc)
            if (now - alert_time).total_seconds() > 24 * 3600:
                del cached_alerts[msg_id]
        except Exception:
            del cached_alerts[msg_id]

    newly_parsed = []

    # Process new alerts
    for msg in messages:
        msg_el = msg.find('div', class_='tgme_widget_message')
        if not msg_el: continue
        msg_id = msg_el.get('data-post', '')

        text_div = msg.find('div', class_='tgme_widget_message_text')
        if not text_div: continue
        text = text_div.get_text(separator='\n').strip()

        if should_skip_radar_message(text):
            continue

        time_tag = msg.find('time')
        time_str = time_tag.get('datetime', '') if time_tag else ''

        if not time_str:
            continue

        parsed = parse_telegram_message(text, msg_id, time_str, channel_username="radarrussiia")
        if not parsed.get("locations") or not parsed.get("threat"):
            continue

        try:
            alert_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            if alert_time.tzinfo is None:
                alert_time = alert_time.replace(tzinfo=timezone.utc)
            if (now - alert_time).total_seconds() <= 24 * 3600:
                cached_alerts[msg_id] = parsed
        except Exception:
            cached_alerts[msg_id] = parsed

        newly_parsed.append(parsed)

    # Fully resolve missing geocodes in the background
    geocode_cache = {}
    gc_file = DATA_DIR / "geocode_cache.json"
    if gc_file.exists():
        try:
            with open(gc_file, "r", encoding="utf-8") as f:
                geocode_cache = json.load(f)
        except Exception:
            pass

    for msg_id, parsed in cached_alerts.items():
        for loc_info in parsed["locations"]:
            if loc_info["name"] not in geocode_cache:
                await get_cached_geocode(loc_info["name"], cache_dict=geocode_cache)
                await asyncio.sleep(1.5) # Prevent Nominatim 429 Too Many Requests

    # Re-read cache_file before writing so we never clobber concurrent writes from the Telethon worker
    fresh_alerts = {}
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                fresh_alerts = json.load(f)
        except Exception:
            pass
    for k in list(fresh_alerts.keys()):
        try:
            t = datetime.fromisoformat(fresh_alerts[k]['time'].replace('Z', '+00:00'))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if (now - t).total_seconds() > 24 * 3600:
                del fresh_alerts[k]
        except Exception:
            del fresh_alerts[k]
    fresh_alerts.update(cached_alerts)

    temp_file = cache_file.with_suffix(f'.tmp.{uuid.uuid4().hex}')
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(fresh_alerts, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, cache_file)

    # Record into longitudinal SQLite history DB
    for parsed in newly_parsed:
        try:
            record_alert_to_history_db(parsed, geocode_cache=geocode_cache, data_dir=DATA_DIR)
        except Exception as db_e:
            logger.error(f"Error recording alert to history DB: {db_e}")


async def get_cached_geocode(location_name: str, cache_dict: Optional[dict] = None, restrict_country: str = "ru,ua") -> Optional[dict]:
    cache_file = DATA_DIR / "geocode_cache.json"
    cache = cache_dict if cache_dict is not None else {}
    if cache_dict is None and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass

    if location_name in cache:
        res = cache[location_name]
        return res if "empty" not in res else None

    # Use extremely aggressive simplification (0.05) to reduce polygon size
    # and restrict responses to Russia and Ukraine only (countrycodes={restrict_country}) to prevent huge global multi-polygons

    # We pass accept-language=en,ru so that Nominatim tries to return the English name but understands the raw Russian query

    # If it's a known region/oblast AND not a city context (no comma), append &featureType=state to force Nominatim to return the regional boundary
    # instead of a tiny local courthouse/town with the same name.
    feature_type = ""
    lower_loc = location_name.lower()
    if "," not in lower_loc and any(x in lower_loc for x in ["область", "республика", "край", "округ"]):
        feature_type = "&featureType=state"

    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location_name)}&format=json&polygon_geojson=1&limit=1&polygon_threshold=0.005&countrycodes={restrict_country}&accept-language=en,ru{feature_type}"
    headers = {'User-Agent': 'ATPGeopolitics/1.0'}
    try:
        resp = await http_client.get(url, headers=headers, timeout=10.0)
        if resp.status_code == 429:
            logger.warning("Nominatim 429 Too Many Requests, pausing for 5 seconds...")
            await asyncio.sleep(5)
            # Retry once
            resp = await http_client.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 429:
                logger.error(f"Geocode retry failed for {location_name} (429)")
                return None

        data = resp.json()

        if data:
            result = data[0]
        else:
            result = {"empty": True} # Negative cache

            # Log the geocode failure
            try:
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                log_file = DATA_DIR / f"geocode_failures_{today_str}.txt"
                time_str = datetime.now(timezone.utc).isoformat()
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(f"[{time_str}] Failed to geocode: {location_name}\n")
            except Exception as log_e:
                logger.error(f"Error writing to geocode failures log: {log_e}")

        # Re-read the cache right before writing to avoid clobbering concurrent manual overrides
        fresh_cache = {}
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    fresh_cache = json.load(f)
            except Exception:
                pass

        fresh_cache[location_name] = result

        # Also update the provided in-memory dict directly to avoid breaking memory caching
        if cache_dict is not None:
            cache_dict[location_name] = result

        # Atomic write to prevent JSONDecodeError from race conditions
        temp_file = cache_file.with_suffix(f'.tmp.{uuid.uuid4().hex}')
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(fresh_cache, f, ensure_ascii=False, indent=2)
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
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_alerts = json.load(f)
        except Exception as e:
            logger.error(f"Error reading radar alerts cache: {e}")
            raise HTTPException(status_code=500, detail="Error reading radar data cache")

    incidents_file = DATA_DIR / "telegram_incidents.json"
    incidents = {}
    if incidents_file.exists():
        try:
            with open(incidents_file, "r", encoding="utf-8") as f:
                incidents = json.load(f)
        except Exception as e:
            logger.error(f"Error reading telegram incidents cache: {e}")

    features = []

    # Load geocode cache once per API request
    geocode_cache = {}
    gc_file = DATA_DIR / "geocode_cache.json"
    if gc_file.exists():
        try:
            with open(gc_file, "r", encoding="utf-8") as f:
                geocode_cache = json.load(f)
        except Exception:
            pass

    # 1. Process Radar Russia Air Alerts (from all radar channels)
    for msg_id, parsed in cached_alerts.items():
        if since:
            try:
                alert_time = datetime.fromisoformat(parsed["time"].replace('Z', '+00:00'))
                since_time_str = since.replace(' ', '+').replace('Z', '+00:00')
                since_time = datetime.fromisoformat(since_time_str)
                if alert_time.timestamp() <= since_time.timestamp():
                    continue
            except Exception as e:
                print(f"Date parse error in since parameter: {e}")
                pass

        channel_name = parsed.get("channel") or (str(msg_id).split("/")[0] if "/" in str(msg_id) else "radarrussiia")
        post_num = str(msg_id).split("/")[-1] if "/" in str(msg_id) else str(msg_id)
        post_url = f"https://t.me/{channel_name}/{post_num}" if channel_name and post_num else ""

        for loc_info in parsed.get("locations", []):
            geo_data = await get_cached_geocode(loc_info["name"], cache_dict=geocode_cache)
            if geo_data and "geojson" in geo_data:
                display_name = geo_data.get("display_name", "")
                english_name = geo_data.get("name", "")

                if display_name and "," in display_name:
                    english_name = display_name.split(",")[0].strip()
                elif not english_name:
                    english_name = loc_info["name"]

                feature = {
                    "type": "Feature",
                    "properties": {
                        "id": f"{parsed['id']}_{loc_info['name']}",
                        "time": parsed["time"],
                        "name": english_name,
                        "raw_name": loc_info.get("raw_name", loc_info["name"]),
                        "threat": parsed["threat"],
                        "status": parsed["status"],
                        "icon": loc_info.get("icon", ""),
                        "channel": channel_name,
                        "post_url": post_url,
                    },
                    "geometry": geo_data["geojson"]
                }
                features.append(feature)

    # 2. Process Regex-Matched Telegram Strike/Hit Incidents (e.g. znua_live)
    for record_id, data in incidents.items():
        if data.get("suppressed"):
            continue

        if since:
            try:
                inc_time = datetime.fromisoformat(data["time"].replace('Z', '+00:00'))
                since_time_str = since.replace(' ', '+').replace('Z', '+00:00')
                since_time = datetime.fromisoformat(since_time_str)
                if inc_time.timestamp() <= since_time.timestamp() and not data.get("admin_modified"):
                    continue
            except Exception:
                pass

        location_query = data.get("location_text", "")
        manual_lat = data.get("lat")
        manual_lng = data.get("lng")

        geometry = None
        english_name = data.get("name", "")

        if manual_lat is not None and manual_lng is not None:
            try:
                geometry = {
                    "type": "Point",
                    "coordinates": [float(manual_lng), float(manual_lat)],
                }
                if not english_name:
                    english_name = location_query or "Strike Incident"
            except (ValueError, TypeError):
                geometry = None

        if geometry is None and location_query:
            geo_data = await get_cached_geocode(
                location_query,
                cache_dict=geocode_cache,
                restrict_country=data.get("country_restrict", "ru"),
            )
            if geo_data:
                if not english_name:
                    display_name = geo_data.get("display_name", "")
                    english_name = geo_data.get("name", "")
                    if display_name and "," in display_name:
                        english_name = display_name.split(",")[0].strip()
                    elif not english_name:
                        english_name = location_query

                # Plot hits as Point markers when plot_type == "marker" and lat/lon exist
                if data.get("plot_type", "marker") == "marker" and "lat" in geo_data and "lon" in geo_data:
                    try:
                        geometry = {
                            "type": "Point",
                            "coordinates": [float(geo_data["lon"]), float(geo_data["lat"])],
                        }
                    except (ValueError, TypeError):
                        geometry = geo_data.get("geojson")
                else:
                    geometry = geo_data.get("geojson")

        if not geometry:
            continue

        channel_name = data.get("channel", "znua_live")
        msg_num = data.get("msg_id", "")
        post_url = data.get("post_url") or (f"https://t.me/{channel_name}/{msg_num}" if channel_name and msg_num else "")

        props = {
            "id": record_id,
            "time": data.get("time", ""),
            "name": english_name or location_query,
            "raw_name": location_query,
            "threat": data.get("description", ""),
            "description": data.get("description", ""),
            "full_text": data.get("full_text", data.get("description", "")),
            "status": data.get("status", "active"),
            "icon": data.get("markerIcon") or data.get("icon", "🔥"),
            "markerType": data.get("markerType", "emoji"),
            "markerIcon": data.get("markerIcon") or data.get("icon", "🔥"),
            "markerColor": data.get("markerColor", "#f97316"),
            "markerBorder": data.get("markerBorder", "#ffffff"),
            "category": data.get("category", "Strike / Hit"),
            "post_url": post_url,
            "embed_url": data.get("embed_url", ""),
            "images": data.get("images", []),
            "custom_fields": data.get("custom_fields", {}),
            "source": "telegram",
            "channel": channel_name,
            "plot_type": data.get("plot_type", "marker"),
            "embed_post": data.get("embed_post", False),
        }
        # Also expose custom_fields at top level of properties so grouped styling and popups work seamlessly
        if isinstance(data.get("custom_fields"), dict):
            for cf_k, cf_v in data["custom_fields"].items():
                if cf_k not in props:
                    props[cf_k] = cf_v

        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": geometry,
        })

    return {"type": "FeatureCollection", "features": features}

@app.post("/api/radar-russia/export-video")
async def export_radar_video(basemap: str = "dark"):
    """Triggers the video generation script and returns the result."""
    try:
        video_filename = f"radar_replay_{datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
        process = await asyncio.create_subprocess_exec(
            "python", "-u", "generate_radar_video.py", "--output", video_filename, "--basemap", basemap,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"Video generation failed: {stderr.decode()}")
            raise HTTPException(status_code=500, detail="Video generation failed")

        video_path = DATA_DIR / video_filename
        if video_path.exists():
            return FileResponse(path=video_path, filename=video_filename, media_type="video/webm")
        else:
            raise HTTPException(status_code=500, detail="Video file not found after generation")
    except Exception as e:
        logger.error(f"Export video error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------

@app.get("/api/layers")
async def get_layers():
    """Returns a list of all KML files in the data directory."""
    files = []
    for f in DATA_DIR.iterdir():
        if f.is_file() and f.suffix.lower() == '.kml' and not f.name.startswith('Ukraine-Regions'):
            files.append(f.name)
    return {"layers": sorted(files)}

@app.post("/api/upload_image", dependencies=[Depends(verify_admin)])
async def upload_image(file: UploadFile = File(...)):
    """Handles uploading custom marker images to the data/images folder."""
    if not file.filename:
        return {"status": "error", "message": "No filename provided."}

    safe_filename = secure_filename(file.filename)
    images_dir = DATA_DIR / "images"
    images_dir.mkdir(exist_ok=True)
    target_path = images_dir / safe_filename

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"status": "success", "filename": safe_filename}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": repr(e)})


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
    safe_filename = secure_filename(filename)
    file_path = DATA_DIR / safe_filename
    if file_path.exists() and file_path.is_file():
        # Rename instead of permanent deletion
        file_path.rename(file_path.with_suffix('.kml.deleted'))
        return {"message": "Layer archived"}
    return {"error": "File not found"}

# Serve the data directory so the frontend can fetch the KML files
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

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


from pydantic import BaseModel
from pydantic import BaseModel
from pydantic import BaseModel
class GeocodeOverride(BaseModel):
    location_name: str
    osm_id: str
    english_name: str = ""
    suppress: bool = False

@app.post("/api/admin/upload_shadow_fleet", dependencies=[Depends(verify_admin)])
async def admin_upload_shadow_fleet(file: UploadFile = File(...)):
    import json
    try:
        content = await file.read()
        data = json.loads(content)

        conn = sqlite3.connect(DATA_DIR / "vessels.db")
        cursor = conn.cursor()

        # We assume the user's data is a dict like {"1": {"mmsi": "...", "imo": "...", "name": "...", "flag": "..."}, ...}
        for key, vessel_info in data.items():
            mmsi = vessel_info.get("mmsi")
            if mmsi:
                cursor.execute('''
                    INSERT INTO shadow_fleet_targets (mmsi, imo, name, flag)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(mmsi) DO UPDATE SET
                        imo=excluded.imo,
                        name=excluded.name,
                        flag=excluded.flag
                ''', (str(mmsi), vessel_info.get("imo", ""), vessel_info.get("name", ""), vessel_info.get("flag", "")))

        conn.commit()
        conn.close()

        return {"status": "success", "message": "Shadow fleet targets updated"}
    except Exception as e:
        logger.error(f"Error processing shadow fleet targets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/geocode_override", dependencies=[Depends(verify_admin)])
async def admin_geocode_override(override: GeocodeOverride):
    cache_file = DATA_DIR / "geocode_cache.json"
    cache = {}
    if cache_file.exists():
        try:
            import json
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass

    # Clean the input name
    target_name = override.location_name.strip()

    # Try to find a case-insensitive match in the cache if the exact case doesn't exist
    actual_key = target_name
    for k in cache.keys():
        if k.lower() == target_name.lower():
            actual_key = k
            break

    if override.osm_id and not override.suppress:
        # Fetch the exact polygon using osm_type and osm_id
        osm_type = 'R'
        osm_id_num = override.osm_id.strip()
        if osm_id_num[0].isalpha():
            osm_type = osm_id_num[0].upper()
            osm_id_num = osm_id_num[1:]

        url = f"https://nominatim.openstreetmap.org/lookup?osm_ids={osm_type}{osm_id_num}&format=json&polygon_geojson=1&accept-language=en,ru"
        headers = {'User-Agent': 'ATPGeopolitics/1.0'}
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                import json
                data = json.loads(response.read().decode('utf-8'))
                if data:
                    pending_override_res = data[0]
                    if override.english_name:
                        pending_override_res["name"] = override.english_name.strip()
                        pending_override_res["display_name"] = override.english_name.strip()
                else:
                    return {"status": "error", "message": "OSM ID not found in Nominatim"}
        except Exception as e:
            logger.error(f"Failed to fetch OSM override: {e}")
            return {"status": "error", "message": str(e)}

    fresh_cache = {}
    if cache_file.exists():
        try:
            import json
            with open(cache_file, "r", encoding="utf-8") as f:
                fresh_cache = json.load(f)
        except Exception:
            pass

    if override.suppress:
        fresh_cache[actual_key] = {"empty": True}
        if 'geocode_cache' in globals():
            geocode_cache[actual_key] = {"empty": True}
    elif not override.osm_id and not override.english_name:
        if actual_key in fresh_cache:
            del fresh_cache[actual_key]
        if 'geocode_cache' in globals() and actual_key in geocode_cache:
            del geocode_cache[actual_key]
    elif override.osm_id and 'pending_override_res' in locals():
        fresh_cache[actual_key] = pending_override_res
        if 'geocode_cache' in globals():
            geocode_cache[actual_key] = pending_override_res
    elif override.english_name and actual_key in fresh_cache:
        # Just override the translation of existing geometry
        fresh_cache[actual_key]["name"] = override.english_name.strip()
        fresh_cache[actual_key]["display_name"] = override.english_name.strip()
        if 'geocode_cache' in globals() and actual_key in geocode_cache:
            geocode_cache[actual_key]["name"] = override.english_name.strip()
            geocode_cache[actual_key]["display_name"] = override.english_name.strip()

    # Atomic write
    temp_file = cache_file.with_suffix(f'.tmp.{uuid.uuid4().hex}')
    with open(temp_file, "w", encoding="utf-8") as f:
        import json
        json.dump(fresh_cache, f, ensure_ascii=False, indent=2)
    import os
    os.replace(temp_file, cache_file)

    return {"status": "success"}


class TelegramIncidentEdit(BaseModel):
    id: str = ""
    name: str = ""
    location_text: str = ""
    description: str = ""
    full_text: str = ""
    post_url: str = ""
    time: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    markerType: str = "emoji"
    markerIcon: str = "🔥"
    markerColor: str = "#f97316"
    markerBorder: str = "#ffffff"
    category: str = "Strike / Hit"
    plot_type: str = "marker"
    images: List[str] = []
    custom_fields: Dict[str, Any] = {}
    suppressed: bool = False


@app.get("/api/admin/telegram_incidents", dependencies=[Depends(verify_admin)])
async def admin_list_telegram_incidents():
    incidents_file = DATA_DIR / "telegram_incidents.json"
    if incidents_file.exists():
        try:
            with open(incidents_file, "r", encoding="utf-8") as f:
                return {"status": "success", "incidents": json.load(f)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"status": "success", "incidents": {}}


@app.post("/api/admin/telegram_incidents", dependencies=[Depends(verify_admin)])
async def admin_save_telegram_incident(item: TelegramIncidentEdit):
    incidents_file = DATA_DIR / "telegram_incidents.json"
    records = {}
    if incidents_file.exists():
        try:
            with open(incidents_file, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = {}

    record_id = item.id.strip() if item.id else f"manual_{uuid.uuid4().hex[:8]}"
    existing = records.get(record_id, {})

    updated = {
        **existing,
        "id": record_id,
        "channel": existing.get("channel", "znua_live"),
        "msg_id": existing.get("msg_id", record_id),
        "time": item.time or existing.get("time") or datetime.now(timezone.utc).isoformat(),
        "name": item.name.strip(),
        "location_text": item.location_text.strip() or existing.get("location_text", ""),
        "description": item.description.strip(),
        "full_text": item.full_text.strip() or item.description.strip(),
        "post_url": item.post_url.strip() or existing.get("post_url", ""),
        "lat": item.lat,
        "lng": item.lng,
        "icon": item.markerIcon or "🔥",
        "markerType": item.markerType or "emoji",
        "markerIcon": item.markerIcon or "🔥",
        "markerColor": item.markerColor or "#f97316",
        "markerBorder": item.markerBorder or "#ffffff",
        "category": item.category or "Strike / Hit",
        "plot_type": item.plot_type or "marker",
        "images": item.images if item.images is not None else existing.get("images", []),
        "custom_fields": item.custom_fields or {},
        "suppressed": item.suppressed,
        "country_restrict": existing.get("country_restrict", "ru"),
        "admin_modified": True,
    }

    records[record_id] = updated
    temp_file = incidents_file.with_suffix(f".tmp.{uuid.uuid4().hex}")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, incidents_file)

    try:
        record_incident_to_history_db(updated, data_dir=DATA_DIR)
    except Exception as e:
        logger.warning(f"Failed to update incident in history DB: {e}")

    return {"status": "success", "id": record_id, "incident": updated}


@app.delete("/api/admin/telegram_incidents/{record_id}", dependencies=[Depends(verify_admin)])
async def admin_delete_telegram_incident(record_id: str):
    incidents_file = DATA_DIR / "telegram_incidents.json"
    if not incidents_file.exists():
        return {"status": "success"}
    try:
        with open(incidents_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        if record_id in records:
            del records[record_id]
            temp_file = incidents_file.with_suffix(f".tmp.{uuid.uuid4().hex}")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, incidents_file)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/radar-russia/history")
async def get_radar_russia_history(
    limit: int = 200,
    offset: int = 0,
    channel: Optional[str] = None,
    source_type: Optional[str] = None,
    query: Optional[str] = None,
):
    """Returns longitudinal historical air alerts and strike incidents from radar_history.db."""
    db_path = init_radar_history_db(DATA_DIR)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    clauses = []
    params: List[Any] = []
    if channel:
        clauses.append("channel = ?")
        params.append(channel.lower())
    if source_type:
        clauses.append("source_type = ?")
        params.append(source_type)
    if query:
        clauses.append("(nominatim_query LIKE ? OR resolved_name LIKE ? OR threat LIKE ?)")
        q_like = f"%{query}%"
        params.extend([q_like, q_like, q_like])

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    cursor.execute(f"SELECT COUNT(*) FROM radar_alerts_history{where_sql}", params)
    total = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT * FROM radar_alerts_history{where_sql} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        [*params, min(limit, 2000), offset],
    )
    rows = [dict(r) for r in cursor.fetchall()]

    cursor.execute(
        "SELECT channel, source_type, COUNT(*) as count FROM radar_alerts_history GROUP BY channel, source_type ORDER BY count DESC"
    )
    by_channel = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "by_channel": by_channel,
        "records": rows,
    }


@app.post("/api/admin/telegram_backfill", dependencies=[Depends(verify_admin)])
async def admin_trigger_telegram_backfill(limit: int = 100):
    """Triggers telegram_userbot_scraper.py --backfill-only to populate longitudinal history from Telegram."""
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable if "sys" in globals() else "python",
            "-u",
            "telegram_userbot_scraper.py",
            "--backfill",
            str(max(1, min(limit, 1000))),
            "--backfill-only",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
            return {"status": "error", "message": err_msg[-1000:]}
        return {
            "status": "success",
            "output": stdout.decode("utf-8", errors="replace")[-2000:],
        }
    except Exception as e:
        logger.error(f"Backfill trigger error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

# Shadow Fleet endpoints
shadow_fleet_router = APIRouter(prefix="/api/shadow-fleet", tags=["Shadow Fleet"])

@shadow_fleet_router.get("/vessels")
def get_vessels():
    """Returns all tracked vessels as a GeoJSON FeatureCollection."""
    conn = sqlite3.connect(DATA_DIR / "vessels.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT v.*, t.name as target_name
        FROM vessels v
        LEFT JOIN shadow_fleet_targets t ON v.mmsi = t.mmsi
    """)
    rows = cursor.fetchall()

    features = []
    now = datetime.now(timezone.utc)

    for row in rows:
        # Check if vessel has gone dark (no signal for 3 hours)
        last_seen = datetime.fromisoformat(row['last_seen']).replace(tzinfo=timezone.utc)
        is_live = (now - last_seen) < timedelta(hours=3)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row['last_lon'], row['last_lat']]
            },
            "properties": {
                "mmsi": row['mmsi'],
                "name": row['target_name'] or row['name'] or "Unknown",
                "type": row['ship_type'] or "Unknown",
                "heading": row['heading'],
                "last_seen": row['last_seen'],
                "is_live": is_live
            }
        }
        features.append(feature)

    conn.close()
    return {"type": "FeatureCollection", "features": features}

def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance in kilometers between two points on the earth."""
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
    return c * r

SPOOFING_ZONES = [
    {"lat": 54.0956, "lon": 38.2321},
    {"lat": 54.1749, "lon": 33.2728}
]

def is_in_spoofing_zone(lon, lat):
    for zone in SPOOFING_ZONES:
        if haversine_distance(zone["lon"], zone["lat"], lon, lat) <= 10.0:
            return True
    return False


def calculate_intermediate_point(lon1, lat1, lon2, lat2, fraction):
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    if c == 0:
        return math.degrees(lon1), math.degrees(lat1)
    A = math.sin((1 - fraction) * c) / math.sin(c)
    B = math.sin(fraction * c) / math.sin(c)
    x = A * math.cos(lat1) * math.cos(lon1) + B * math.cos(lat2) * math.cos(lon2)
    y = A * math.cos(lat1) * math.sin(lon1) + B * math.cos(lat2) * math.sin(lon2)
    z = A * math.sin(lat1) + B * math.sin(lat2)
    lat_inter = math.atan2(z, math.sqrt(x**2 + y**2))
    lon_inter = math.atan2(y, x)
    return round(math.degrees(lon_inter), 6), round(math.degrees(lat_inter), 6)
































def check_is_outage(cursor, start_time, end_time):
    # check if there are any points across all vessels between start_time + 30 mins and end_time - 30 mins
    import datetime

    st = start_time + datetime.timedelta(minutes=30)
    et = end_time - datetime.timedelta(minutes=30)

    if st >= et:
        return False

    cursor.execute("SELECT 1 FROM tracks WHERE timestamp > ? AND timestamp < ? LIMIT 1", (st.isoformat(), et.isoformat()))
    return cursor.fetchone() is None

def generate_track_features(cursor, mmsi, points):
    features = []
    current_segment = []
    last_lon, last_lat, last_time = None, None, None
    reject_count = 0

    for pt in points:
        try:
            lon, lat, timestamp = pt["lon"], pt["lat"], pt["timestamp"]
            if is_in_spoofing_zone(lon, lat):
                continue
            current_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)

            is_gap = False
            gap_type = None

            if last_lon is not None and last_lat is not None and last_time is not None:
                dist_km = haversine_distance(last_lon, last_lat, lon, lat)
                time_diff_hours = (current_time - last_time).total_seconds() / 3600.0

                if time_diff_hours >= 3:
                    is_gap = True
                    if check_is_outage(cursor, last_time, current_time):
                        gap_type = "outage"
                    else:
                        gap_type = "dark"

                is_valid = True
                if not is_gap:
                    if time_diff_hours > 0:
                        speed_kmh = dist_km / time_diff_hours
                        if speed_kmh > 80 and dist_km > 20:
                            is_valid = False
                    elif dist_km > 5:
                        is_valid = False

                if not is_valid:
                    reject_count += 1
                    if reject_count > 3:
                        reject_count = 0
                    else:
                        continue

                if is_gap:
                    if current_segment and current_segment[-1] != [last_lon, last_lat]:
                        current_segment.append([last_lon, last_lat])
                    elif not current_segment:
                        current_segment.append([last_lon, last_lat])

                    if len(current_segment) > 1:
                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": current_segment},
                            "properties": {"mmsi": mmsi}
                        })

                    if dist_km > 300:
                        fraction = 25.0 / dist_km
                        inter1 = calculate_intermediate_point(last_lon, last_lat, lon, lat, fraction)
                        inter2 = calculate_intermediate_point(last_lon, last_lat, lon, lat, 1.0 - fraction)

                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [[last_lon, last_lat], list(inter1)]},
                            "properties": {"mmsi": mmsi, "is_dark": gap_type == "dark", "is_outage": gap_type == "outage"}
                        })
                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [list(inter2), [lon, lat]]},
                            "properties": {"mmsi": mmsi, "is_dark": gap_type == "dark", "is_outage": gap_type == "outage"}
                        })
                    else:
                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [[last_lon, last_lat], [lon, lat]]},
                            "properties": {"mmsi": mmsi, "is_dark": gap_type == "dark", "is_outage": gap_type == "outage"}
                        })

                    current_segment = []
                else:
                    if not current_segment:
                        current_segment.append([last_lon, last_lat])
                    current_segment.append([lon, lat])

            else:
                if not current_segment:
                    current_segment.append([lon, lat])
                else:
                    current_segment.append([lon, lat])

            last_lon, last_lat, last_time = lon, lat, current_time
            reject_count = 0

        except Exception as e:
            logger.error(f"Error parsing track point: {e}")
            if not current_segment:
                if last_lon is not None:
                    current_segment.append([last_lon, last_lat])
            current_segment.append([pt["lon"], pt["lat"]])
            last_lon, last_lat = pt["lon"], pt["lat"]

    if last_lon is not None and (not current_segment or current_segment[-1] != [last_lon, last_lat]):
        current_segment.append([last_lon, last_lat])

    if len(current_segment) > 1:
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": current_segment},
            "properties": {"mmsi": mmsi}
        })

    return features



@shadow_fleet_router.get("/tracks/{mmsi}")
def get_vessel_track(mmsi: str):
    """Returns the historical track of a specific vessel as a GeoJSON FeatureCollection."""
    conn = sqlite3.connect(DATA_DIR / "vessels.db")
    cursor = conn.cursor()

    # Get last 7 days of points, limit 500
    cursor.execute("SELECT lon, lat, timestamp FROM tracks WHERE mmsi = ? AND timestamp >= datetime('now', '-7 days') ORDER BY timestamp DESC LIMIT 500", (mmsi,))
    rows = cursor.fetchall()

    if not rows:
        conn.close()
        return {"error": "No tracks found"}

    rows = list(reversed(rows))
    points = [{"lon": r[0], "lat": r[1], "timestamp": r[2]} for r in rows]

    features = generate_track_features(cursor, mmsi, points)

    conn.close()
    return {
        "type": "FeatureCollection",
        "features": features
    }


@shadow_fleet_router.get("/tracks")
def get_all_vessel_tracks():
    """Returns the historical tracks of all vessels as a GeoJSON FeatureCollection."""
    conn = sqlite3.connect(DATA_DIR / "vessels.db")
    cursor = conn.cursor()

    cursor.execute('''
        WITH RankedTracks AS (
            SELECT mmsi, lon, lat, timestamp,
                   ROW_NUMBER() OVER (PARTITION BY mmsi ORDER BY timestamp DESC) as rn
            FROM tracks
            WHERE timestamp >= datetime('now', '-7 days')
        )
        SELECT mmsi, lon, lat, timestamp FROM RankedTracks WHERE rn <= 100 ORDER BY mmsi, timestamp ASC
    ''')
    rows = cursor.fetchall()

    tracks_by_mmsi = {}
    for row in rows:
        mmsi = row[0]
        coord_data = {"lon": row[1], "lat": row[2], "timestamp": row[3]}
        if mmsi not in tracks_by_mmsi:
            tracks_by_mmsi[mmsi] = []
        tracks_by_mmsi[mmsi].append(coord_data)

    features = []
    for mmsi, points in tracks_by_mmsi.items():
        features.extend(generate_track_features(cursor, mmsi, points))

    conn.close()

    return {"type": "FeatureCollection", "features": features}



app.include_router(shadow_fleet_router)

# Serve any other static assets if needed
app.mount("/", StaticFiles(directory="static"), name="static")

async def daily_video_scheduler():
    """Generates the radar video automatically at 10 AM UTC every day."""
    while True:
        now = datetime.now(timezone.utc)
        # Calculate next 10 AM
        target = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)

        sleep_seconds = (target - now).total_seconds()
        logger.info(f"Next daily video scheduled in {sleep_seconds} seconds (at {target})")
        await asyncio.sleep(sleep_seconds)

        try:
            logger.info("Running scheduled daily radar video generation...")
            video_filename = f"radar_replay_daily_{target.strftime('%Y%m%d')}.webm"
            process = await asyncio.create_subprocess_exec("python", "-u", "generate_radar_video.py", "--output", video_filename)
            await process.communicate()
        except Exception as e:
            logger.error(f"Scheduled video generation failed: {e}")

@app.on_event("startup")
async def start_scheduler():
    asyncio.create_task(daily_video_scheduler())
