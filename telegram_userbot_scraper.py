import argparse
import asyncio
import json
import os
import sqlite3
import sys
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
from dotenv import load_dotenv
from telethon import TelegramClient, events

from telegram_config import (
    CHANNEL_CONFIGS,
    clean_incident_location,
    clean_incident_description,
)
from telegram_shared import (
    _safe_replace,
    resolve_data_dir,
    should_skip_radar_message,
    parse_telegram_message,
    init_radar_history_db,
    record_alert_to_history_db,
    record_incident_to_history_db,
    save_radar_alert_to_live_cache,
    save_incident_to_live_cache,
    fetch_channel_messages_http,
    download_embed_photos_http,
)

# Load environment variables
load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    out_enc = "ascii" if os.name == "nt" else "utf-8"
    sys.stdout.reconfigure(encoding=out_enc, errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    err_enc = "ascii" if os.name == "nt" else "utf-8"
    sys.stderr.reconfigure(encoding=err_enc, errors="backslashreplace")

API_ID_RAW = os.getenv("TELEGRAM_API_ID", "0").strip().strip('"').strip("'")
API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip().strip('"').strip("'")
API_ID = int(API_ID_RAW) if API_ID_RAW.isdigit() else 0

DATA_DIR = resolve_data_dir()
IMAGES_DIR = DATA_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def resolve_session_path() -> str:
    env_path = os.getenv("TELEGRAM_SESSION_PATH")
    if env_path:
        return env_path
    # Check current directory first, then telegramold/ fallback
    if os.path.exists("mapping_userbot.session"):
        return "mapping_userbot"
    if os.path.exists(os.path.join("telegramold", "mapping_userbot.session")):
        return os.path.join("telegramold", "mapping_userbot")
    return "mapping_userbot"


SESSION_PATH = resolve_session_path()

if not API_ID or not API_HASH:
    print("ERROR: TELEGRAM_API_ID or TELEGRAM_API_HASH is missing from environment.")
    sys.exit(1)

session_file_name = SESSION_PATH if SESSION_PATH.endswith(".session") else f"{SESSION_PATH}.session"
_session_arg = None if "--http-only" in sys.argv or "--login" in sys.argv else (SESSION_PATH[:-8] if SESSION_PATH.endswith(".session") else SESSION_PATH)

client = TelegramClient(_session_arg, API_ID, API_HASH)
http_client = httpx.AsyncClient(timeout=12.0)

target_channels: Dict[str, Dict[str, Any]] = {k.lower(): v for k, v in CHANNEL_CONFIGS.items()}

# Track grouped_id -> (channel_username, base_msg_id) so album photos attached to subsequent
# empty-caption messages in the same Telegram media group are appended to the strike incident.
album_group_map: Dict[int, Dict[str, Any]] = {}


_GEOCODE_CACHE_MEM: Dict[str, Any] = {}
_GEOCODE_CACHE_MTIME: float = 0.0


def load_geocode_cache(force_reload: bool = False) -> Dict[str, Any]:
    global _GEOCODE_CACHE_MEM, _GEOCODE_CACHE_MTIME
    cache_file = DATA_DIR / "geocode_cache.json"
    if cache_file.exists():
        try:
            mtime = cache_file.stat().st_mtime
            if force_reload or mtime != _GEOCODE_CACHE_MTIME or not _GEOCODE_CACHE_MEM:
                with open(cache_file, "r", encoding="utf-8") as f:
                    _GEOCODE_CACHE_MEM = json.load(f)
                _GEOCODE_CACHE_MTIME = mtime
        except Exception:
            pass
    return _GEOCODE_CACHE_MEM


async def resolve_geocode_background(location_name: str, restrict_country: str = "ru,ua") -> Optional[Dict[str, Any]]:
    """Resolves a location against Nominatim (if not already in geocode_cache.json) and updates the cache."""
    if not location_name:
        return None
    cache_file = DATA_DIR / "geocode_cache.json"
    cache = load_geocode_cache()
    if location_name in cache:
        res = cache[location_name]
        return res if "empty" not in res else None

    feature_type = ""
    lower_loc = location_name.lower()
    if "," not in lower_loc and any(x in lower_loc for x in ["область", "республика", "край", "округ"]):
        feature_type = "&featureType=state"

    url = (
        f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location_name)}"
        f"&format=json&polygon_geojson=1&limit=1&polygon_threshold=0.005"
        f"&countrycodes={restrict_country}&accept-language=en,ru{feature_type}"
    )
    headers = {"User-Agent": "ATPGeopolitics/1.0"}
    try:
        resp = await http_client.get(url, headers=headers)
        if resp.status_code == 429:
            await asyncio.sleep(5)
            resp = await http_client.get(url, headers=headers)
            if resp.status_code == 429:
                return None

        data = resp.json()
        if data:
            result = data[0]
        else:
            result = {"empty": True}
            try:
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                log_file = DATA_DIR / f"geocode_failures_{today_str}.txt"
                time_str = datetime.now(timezone.utc).isoformat()
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(f"[{time_str}] Failed to geocode: {location_name}\n")
            except Exception:
                pass

        fresh_cache = load_geocode_cache(force_reload=True)
        fresh_cache[location_name] = result
        temp_file = cache_file.with_suffix(f".tmp.{uuid.uuid4().hex}")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(fresh_cache, f, ensure_ascii=False, indent=2)
        _safe_replace(temp_file, cache_file)
        load_geocode_cache(force_reload=True)
        await asyncio.sleep(1.5)  # Respect Nominatim rate limit
        return result if "empty" not in result else None
    except Exception as e:
        print(f"Geocode error for {location_name}: {e}")
        return None


async def download_message_photo(message, channel_username: str) -> Optional[str]:
    """Downloads a photo from a Telegram message into data/images/ and returns the filename."""
    if not getattr(message, "photo", None):
        return None
    filename = f"tg_{channel_username}_{message.id}.jpg"
    dest_path = IMAGES_DIR / filename
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return filename
    try:
        await client.download_media(message.photo, file=str(dest_path))
        if dest_path.exists() and dest_path.stat().st_size > 0:
            return filename
    except Exception as e:
        print(f"Error downloading photo from {channel_username}/{message.id}: {e}")
    return None


async def collect_album_photos(message, channel_username: str) -> List[str]:
    """Downloads photos from the message and any sibling messages in the same media album."""
    photos: List[str] = []

    # First try public ?embed=1 media extraction (retrieves all album photos in a single HTTP request)
    embed_photos = await download_embed_photos_http(channel_username, message.id, IMAGES_DIR, http_client)
    for ep in embed_photos:
        if ep not in photos:
            photos.append(ep)

    if photos:
        return photos

    # Fallback to Telethon media download (for private channels or when embed has no photos)
    first_photo = await download_message_photo(message, channel_username)
    if first_photo:
        photos.append(first_photo)

    grouped_id = getattr(message, "grouped_id", None)
    if grouped_id and client.is_connected():
        album_group_map[grouped_id] = {
            "channel": channel_username,
            "msg_id": message.id,
            "record_id": f"{channel_username}_{message.id}",
        }
        try:
            chat = await message.get_chat()
            ids_to_check = list(range(message.id + 1, message.id + 8))
            siblings = await client.get_messages(chat, ids=ids_to_check)
            for sib in siblings:
                if sib and getattr(sib, "grouped_id", None) == grouped_id:
                    sib_photo = await download_message_photo(sib, channel_username)
                    if sib_photo and sib_photo not in photos:
                        photos.append(sib_photo)
        except Exception as e:
            print(f"Album sibling check error for {channel_username}/{message.id}: {e}")
    return photos


async def process_channel_message(
    message,
    channel_username: str,
    resolve_geocodes: bool = True,
    download_media: bool = True,
    db_conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """
    Processes a single Telethon Message from `channel_username`.
    Returns True if an alert or incident was extracted and recorded.
    """
    channel_username = channel_username.lower()
    if channel_username not in target_channels:
        return False

    config = target_channels[channel_username]
    channel_type = config.get("type", "radar_alert")
    text = (getattr(message, "message", None) or "").strip()
    grouped_id = getattr(message, "grouped_id", None)

    # Check if this is a captionless album sibling photo for a recently matched incident
    if not text and grouped_id and grouped_id in album_group_map and download_media:
        album_info = album_group_map[grouped_id]
        sib_photo = await download_message_photo(message, channel_username)
        if sib_photo:
            incidents_file = DATA_DIR / "telegram_incidents.json"
            if incidents_file.exists():
                try:
                    with open(incidents_file, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    rec_id = album_info["record_id"]
                    if rec_id in records:
                        imgs = records[rec_id].setdefault("images", [])
                        if sib_photo not in imgs:
                            imgs.append(sib_photo)
                            save_incident_to_live_cache(records[rec_id], DATA_DIR)
                            record_incident_to_history_db(records[rec_id], load_geocode_cache(), DATA_DIR, conn=db_conn)
                except Exception as e:
                    print(f"Error appending album photo: {e}")
        return False

    if not text:
        return False

    msg_time = message.date
    if msg_time.tzinfo is None:
        msg_time = msg_time.replace(tzinfo=timezone.utc)
    time_iso = msg_time.isoformat()

    # 1. Handle Radar Alert Channels
    if channel_type == "radar_alert":
        if should_skip_radar_message(text):
            return False

        composite_id = f"{channel_username}/{message.id}"
        parsed = parse_telegram_message(text, composite_id, time_iso, channel_username=channel_username)
        if not parsed.get("locations") or not parsed.get("threat"):
            return False

        # Save to 24h live cache (if recent)
        saved_live = save_radar_alert_to_live_cache(parsed, DATA_DIR)

        # Resolve geocodes if requested
        gc = load_geocode_cache()
        if resolve_geocodes:
            for loc_info in parsed["locations"]:
                if loc_info["name"] not in gc:
                    await resolve_geocode_background(loc_info["name"], restrict_country="ru,ua")
            gc = load_geocode_cache()

        # Always record to permanent history DB
        record_alert_to_history_db(parsed, geocode_cache=gc, data_dir=DATA_DIR, conn=db_conn)
        if saved_live:
            locs_str = ", ".join(l["name"] for l in parsed["locations"])
            print(f"[RADAR] {composite_id}: {locs_str} -> {parsed['threat']} ({parsed['status']})")
        return True

    # 2. Handle Regex Incident / Strike Channels (e.g. znua_live)
    elif channel_type == "regex_incident":
        for pattern in config.get("patterns", []):
            match = pattern.search(text)
            if match:
                raw_location_text = match.group(config.get("location_group", 1)).strip()
                location_text = clean_incident_location(raw_location_text)
                raw_desc = match.group(config.get("description_group", 2)).strip()
                description = clean_incident_description(raw_desc, config.get("strip_footers"))
                clean_full = clean_incident_description(text, config.get("strip_footers"))

                print(f"[INCIDENT MATCH] {channel_username}/{message.id}! Location: {location_text}")

                photos: List[str] = []
                if download_media:
                    photos = await collect_album_photos(message, channel_username)

                post_url = f"https://t.me/{channel_username}/{message.id}"
                embed_url = f"https://t.me/{channel_username}/{message.id}?embed=1"
                record_id = f"{channel_username}_{message.id}"

                incident_data = {
                    "id": record_id,
                    "channel": channel_username,
                    "msg_id": message.id,
                    "time": time_iso,
                    "location_text": location_text,
                    "raw_location_text": raw_location_text,
                    "description": description,
                    "full_text": clean_full,
                    "post_url": post_url,
                    "embed_url": embed_url,
                    "images": photos,
                    "icon": config.get("icon", "🔥"),
                    "markerType": config.get("marker_type", "emoji"),
                    "markerIcon": config.get("icon", "🔥"),
                    "markerColor": config.get("marker_color", "#f97316"),
                    "markerBorder": config.get("marker_border", "#ffffff"),
                    "category": config.get("category", "Strike / Hit"),
                    "country_restrict": config.get("country_restrict", "ru"),
                    "plot_type": config.get("plot_type", "marker"),
                    "embed_post": config.get("embed_post", False),
                    "status": "active",
                }

                save_incident_to_live_cache(incident_data, DATA_DIR)

                gc = load_geocode_cache()
                if resolve_geocodes and location_text not in gc:
                    await resolve_geocode_background(
                        location_text,
                        restrict_country=config.get("country_restrict", "ru"),
                    )
                    gc = load_geocode_cache()

                record_incident_to_history_db(incident_data, geocode_cache=gc, data_dir=DATA_DIR, conn=db_conn)
                return True

    return False


@client.on(events.NewMessage(incoming=True))
async def handle_new_message(event):
    """Triggers instantly when any subscribed channel posts a new message."""
    message = event.message
    if not message:
        return

    chat = await event.get_chat()
    if not chat:
        return

    channel_username = getattr(chat, "username", None)
    if not channel_username:
        return

    channel_username = channel_username.lower()
    if channel_username not in target_channels:
        return

    await process_channel_message(
        message,
        channel_username,
        resolve_geocodes=True,
        download_media=True,
    )


async def backfill_channel_history(
    limit_per_channel: int = 100,
    resolve_geocodes: bool = True,
    use_telethon: bool = True,
):
    """
    Fetches historical messages from all configured channels to populate:
    - `data/radar_history.db` (longitudinal SQLite database)
    - `data/radar_alerts.json` (any alerts from the last 24h)
    - `data/telegram_incidents.json` (regex-matched strike incidents + photos)
    """
    db_path = init_radar_history_db(DATA_DIR)

    # Seed history DB with any existing alerts already stored in data/radar_alerts.json
    existing_alerts_file = DATA_DIR / "radar_alerts.json"
    if existing_alerts_file.exists():
        try:
            gc = load_geocode_cache()
            with open(existing_alerts_file, "r", encoding="utf-8") as f:
                existing_alerts = json.load(f)
            conn = sqlite3.connect(db_path, timeout=30.0)
            try:
                for _, alert_rec in existing_alerts.items():
                    record_alert_to_history_db(alert_rec, geocode_cache=gc, data_dir=DATA_DIR, conn=conn)
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Warning: could not seed existing radar_alerts.json into history DB: {e}")

    dialog_by_username = {}
    if use_telethon and client.is_connected():
        try:
            dialogs = await client.get_dialogs()
            for d in dialogs:
                u = getattr(d.entity, "username", None)
                if u:
                    dialog_by_username[u.lower()] = d.entity
        except Exception as e:
            print(f"Warning: Telethon get_dialogs failed ({e}), falling back to HTTP t.me/s/ backfill.")
            use_telethon = False

    total_recorded = 0
    now = datetime.now(timezone.utc)

    # Process regex_incident channels (e.g. znua_live) first so strike markers and media are ready immediately
    ordered_channels = sorted(
        target_channels.items(),
        key=lambda kv: (0 if kv[1].get("type") == "regex_incident" else 1),
    )

    for ch_username, cfg in ordered_channels:
        is_incident_ch = cfg.get("type") == "regex_incident"
        ch_limit = max(limit_per_channel, 300) if is_incident_ch else limit_per_channel
        try:
            msgs = None
            if use_telethon and client.is_connected():
                entity = dialog_by_username.get(ch_username) or ch_username
                try:
                    msgs = await client.get_messages(entity, limit=ch_limit)
                except Exception as te:
                    print(f"Telethon get_messages failed for @{ch_username} ({te}); using HTTP fallback.")
            if msgs is None:
                msgs = await fetch_channel_messages_http(ch_username, ch_limit, http_client)

            ch_count = 0
            conn = sqlite3.connect(db_path, timeout=30.0)
            try:
                for m in reversed(msgs):
                    if not m:
                        continue
                    msg_time = m.date.replace(tzinfo=timezone.utc) if m.date.tzinfo is None else m.date
                    is_recent_24h = (now - msg_time).total_seconds() <= 24 * 3600
                    # Only hit Nominatim during backfill for 24h live alerts or strike incidents
                    # (or if already cached in geocode_cache.json)
                    should_geocode = resolve_geocodes and (is_recent_24h or is_incident_ch)
                    should_download_media = is_incident_ch
                    ok = await process_channel_message(
                        m,
                        ch_username,
                        resolve_geocodes=should_geocode,
                        download_media=should_download_media,
                        db_conn=conn,
                    )
                    if ok:
                        ch_count += 1
                        total_recorded += 1
                conn.commit()
            finally:
                conn.close()
            print(f"Backfilled {ch_count} alerts/incidents from @{ch_username} (scanned {len(msgs)} messages)")
        except Exception as e:
            print(f"Warning: Failed to backfill @{ch_username}: {e}")

    print(f"Backfill complete! Total alerts/incidents processed: {total_recorded}")


async def run_http_polling_loop(interval_seconds: int = 90):
    """
    Continuous async HTTP polling loop across all configured channels when Telethon session
    is unavailable or invalidated (e.g. AuthKeyDuplicatedError across environments).
    """
    print(f"Starting async HTTP multi-channel polling loop ({len(target_channels)} channels, interval={interval_seconds}s)...")
    seen_ids: Dict[str, int] = {}
    db_path = init_radar_history_db(DATA_DIR)

    while True:
        ordered_channels = sorted(
            target_channels.items(),
            key=lambda kv: (0 if kv[1].get("type") == "regex_incident" else 1),
        )
        for ch_username, cfg in ordered_channels:
            try:
                msgs = await fetch_channel_messages_http(ch_username, 20, http_client)
                last_seen = seen_ids.get(ch_username, 0)
                conn = sqlite3.connect(db_path, timeout=30.0)
                try:
                    for m in reversed(msgs):
                        if m.id <= last_seen:
                            continue
                        is_incident_ch = cfg.get("type") == "regex_incident"
                        await process_channel_message(
                            m,
                            ch_username,
                            resolve_geocodes=True,
                            download_media=is_incident_ch,
                            db_conn=conn,
                        )
                        if m.id > seen_ids.get(ch_username, 0):
                            seen_ids[ch_username] = m.id
                    conn.commit()
                finally:
                    conn.close()
            except Exception as e:
                print(f"HTTP poll error for @{ch_username}: {e}")
            await asyncio.sleep(1.5)
        await asyncio.sleep(interval_seconds)


async def main():
    parser = argparse.ArgumentParser(description="Telegram Multi-Channel Radar & Incident Userbot")
    parser.add_argument(
        "--backfill",
        type=int,
        default=int(os.getenv("TELEGRAM_STARTUP_BACKFILL", "50")),
        help="Number of recent messages per channel to backfill on startup (0 to skip)",
    )
    parser.add_argument(
        "--backfill-only",
        action="store_true",
        help="Run historical backfill and exit without starting the live listener",
    )
    parser.add_argument(
        "--no-geocode",
        action="store_true",
        help="Skip live Nominatim queries for uncached historical locations during backfill",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Interactively authenticate via QR code + 2FA and create/replace the Telethon .session file",
    )
    parser.add_argument(
        "--http-only",
        action="store_true",
        help="Use HTTP t.me/s/ scraping without touching the Telethon .session file",
    )
    args = parser.parse_args()

    print("Starting Telegram Radar & Incident Userbot...")
    init_radar_history_db(DATA_DIR)

    if args.login:
        from auth import main as auth_main
        await http_client.aclose()
        await auth_main()
        return

    telethon_ok = False
    if not args.http_only and os.path.exists(session_file_name):
        try:
            await client.connect()
            if await client.is_user_authorized():
                print("Successfully logged in as Userbot via Telethon!")
                print("Waking up channel subscriptions...")
                await client.get_dialogs()
                telethon_ok = True
            else:
                print(
                    f"WARNING: Session file '{session_file_name}' is not authorized. "
                    "Run `python telegram_userbot_scraper.py --login` to re-authenticate. "
                    "Using HTTP t.me/s/ fallback."
                )
        except Exception as e:
            try:
                await client.disconnect()
            except Exception:
                pass
            print(
                f"WARNING: Telethon session connection failed ({type(e).__name__}: {e}). "
                "Note: Using the same .session file simultaneously on two different IP addresses causes "
                "Telegram to invalidate the key (AuthKeyDuplicatedError). "
                "Run `python telegram_userbot_scraper.py --login` to create a fresh session. "
                "Continuing via HTTP t.me/s/ multi-channel fallback..."
            )
    else:
        print(
            f"WARNING: Session file not found at '{os.path.abspath(session_file_name)}'. "
            "Continuing via HTTP t.me/s/ multi-channel fallback..."
        )

    if args.backfill > 0:
        print(f"Running startup backfill ({args.backfill} messages per channel, telethon={telethon_ok})...")
        await backfill_channel_history(
            limit_per_channel=args.backfill,
            resolve_geocodes=not args.no_geocode,
            use_telethon=telethon_ok,
        )

    if args.backfill_only:
        await http_client.aclose()
        if client.is_connected():
            await client.disconnect()
        return

    if telethon_ok:
        print(f"Listening in real-time via Telethon to {len(target_channels)} channels: {', '.join(target_channels.keys())}")
        try:
            await client.run_until_disconnected()
        finally:
            await http_client.aclose()
    else:
        try:
            await run_http_polling_loop()
        finally:
            await http_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
