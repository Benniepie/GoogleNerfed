import json
import os
import re
import sqlite3
import time
import uuid
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import httpx

from telegram_config import (
    CHANNEL_CONFIGS,
    get_channel_default_context,
    clean_incident_location,
    clean_incident_description,
)

_INITIALIZED_DBS: Set[str] = set()


def _safe_replace(temp_file: Path, target_file: Path):
    """Replaces target_file with temp_file, retrying briefly on Windows PermissionError."""
    for attempt in range(5):
        try:
            os.replace(temp_file, target_file)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05)


def resolve_data_dir() -> Path:
    env_dir = os.getenv("MAP_DATA_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    local_data = Path("data")
    if os.name == "nt" or local_data.exists() or not Path("/app").exists():
        local_data.mkdir(parents=True, exist_ok=True)
        return local_data
    app_data = Path("/app/data")
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data


SUMMARY_SKIP_PHRASES = [
    "За прошедшую ночь",
    "За ночь средствами ПВО",
    "Дежурными средствами ПВО перехвачено и уничтожено",
    "силами противовоздушной обороны было уничтожено",
    "средствами ПВО было уничтожено",
    "Ожидаем ближе к ночи",
    "Фиксаций над нашим воздушным пространством не наблюдаем",
    "Пока по обстановке тихо",
    "На данный момент по обстановке тихо",
    "При возникновении непосредственной угрозы",
    "Берегите себя и своих близких",
    "В связи с возможной ночной угрозой оружием",
    "В связи массовыми угрозами нанесения ударов",
    "Убедительная просьба,найти свой город",
    "КАНАЛЫ БУДУТ РАБОТАТЬ ДАЖЕ БЕЗ МОБИЛЬНОЙ СВЯЗИ",
    "РСЧС (МЧС России) был взломан",
    "Не поддавайтесь панике",
    "Сидела в кафе",
    "ПЕРВЫЙ ПАРФЮМЕРНЫЙ",
    "PARFUM GALLERY",
    "Золотого Яблока",
    "РИВ ГОШ",
    "это не реклама, поэтому просьба не игнорировать",
    "t.me/+",
    "Реклама",
    "Учения",
    "ВСУ сбросили",
]

LINE_BOILERPLATE_KEYWORDS = [
    "❗️",
    "‼️",
    "Обход белых списков",
    "@radarrussiia",
    "📲",
    "https://max.ru/join/radarrussiia",
    "https://max.ru/tyrbazaa",
    "https://max.ru",
    "http://",
    "https://",
    "Наш канал в МАХ",
    "Радар по всей России",
    "Internet_Boost_bot",
    "🌐",
    "Ускоритель Интернета",
    "Остались какие-то вопросы",
    "Подписаться на Радар",
    "Подписаться на канал",
    "Радар ",
    "@radar_",
    "@rada_",
    "@Kubanoperativ",
    "@stavropol_radar",
]

NON_LOCATION_PHRASES = {
    "север",
    "юг",
    "запад",
    "восток",
    "северо-запад",
    "северо-восток",
    "юго-запад",
    "юго-восток",
    "центр",
    "сохраняется",
    "уйти от окон",
    "укрытие",
    "в укрытие",
}


def should_skip_radar_message(text: str) -> bool:
    if not text or not text.strip():
        return True
    lower_text = text.lower()
    return any(phrase.lower() in lower_text for phrase in SUMMARY_SKIP_PHRASES)


def get_radar_icon(location_str: str, threat_str: str) -> str:
    combined = (location_str + " " + threat_str).lower()
    if any(kw in combined for kw in ["аэропорт", "аэродром", "airport", "авиабаза", "air base"]):
        return "✈️"
    if any(kw in combined for kw in ["нпз", "нефте", "oil", "naval base", "порт", "терминал", "refinery"]):
        return "⚓"
    if any(kw in combined for kw in ["море", "залив", "sea", "вода", "океан", "акватория"]):
        return "🌊"
    if any(kw in combined for kw in ["база", "base", "вч", "войсковая часть", "military"]):
        return "🪖"
    return ""


def parse_telegram_message(
    text: str,
    msg_id: str,
    time_str: str,
    channel_username: Optional[str] = None,
) -> dict:
    """
    Parses a Russian radar alert message into locations, threat translation, and status.
    Preserves the original radar Russia parsing rules while supporting per-channel
    regional context fallbacks when individual oblast/city channels omit the oblast name.
    """
    if not channel_username and "/" in str(msg_id):
        channel_username = str(msg_id).split("/")[0]

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        lower_line = line.lower()
        # Filter out boilerplate, channel footers, and referral links
        if any(kw.lower() in lower_line for kw in LINE_BOILERPLATE_KEYWORDS):
            continue
        if re.search(r"@\w+", line):
            continue
        cleaned_lines.append(line)

    threat_keywords = [
        "опасность",
        "фиксаци",
        "отбой",
        "работа",
        "пво",
        "ракет",
        "бпла",
        "приготовиться",
        "тревога",
        "меры",
        "сбит",
        "угроза",
        "внимание",
        "уничтожен",
        "отражен",
        "атак",
        "беспилотник",
    ]

    locations = []
    threats = []

    for line in cleaned_lines:
        parts = line.split(" - ")
        for part in parts:
            part = part.strip().rstrip(".")
            if not part:
                continue
            is_threat = any(kw in part.lower() for kw in threat_keywords)
            if is_threat:
                threats.append(part)
            else:
                for loc in part.split(","):
                    loc_clean = loc.strip()
                    if not loc_clean:
                        continue
                    if loc_clean.lower() in NON_LOCATION_PHRASES:
                        continue
                    # Strip leading cardinal direction prefixes e.g. "Север Республика Крым"
                    loc_clean = re.sub(
                        r"^(?:северо-запад|северо-восток|юго-запад|юго-восток|север|юг|запад|восток)\s+",
                        "",
                        loc_clean,
                        flags=re.IGNORECASE,
                    ).strip()
                    if not loc_clean or loc_clean.lower() in NON_LOCATION_PHRASES:
                        continue
                    # Ignore trajectory descriptions like "От Ельня до Дугино" or "далее Бежецк-Кашин"
                    if re.match(r"^(?:от\s+\S+\s+до\s+|далее\s+|граница\s+)", loc_clean, flags=re.IGNORECASE):
                        continue

                    loc_clean = re.sub(r"(?i)и близлежащие", "округ", loc_clean).strip()
                    loc_clean = re.sub(r"(?i)\bблизлежащие\b", "округ", loc_clean).strip()
                    loc_clean = re.sub(r"^г\.\s*", "", loc_clean, flags=re.IGNORECASE).strip()

                    admin_expansions = {
                        "мо ": "муниципальный округ ",
                        "го ": "городской округ ",
                        "мр ": "муниципальный район ",
                        "ао ": "административный округ ",
                        "зато ": "закрытое административно-территориальное образование ",
                    }

                    lower_loc = loc_clean.lower()
                    for prefix, expansion in admin_expansions.items():
                        if lower_loc.startswith(prefix):
                            loc_clean = expansion + loc_clean[len(prefix):].strip()
                            break

                    # Split compound "Саратов/Энгельс" into two locations
                    if "/" in loc_clean and not loc_clean.startswith("http"):
                        for sub_loc in loc_clean.split("/"):
                            sub_clean = sub_loc.strip()
                            if sub_clean and sub_clean.lower() not in NON_LOCATION_PHRASES:
                                locations.append(sub_clean)
                    elif loc_clean:
                        locations.append(loc_clean)

    # Extract directional targets if threats mention "на Москву" / "в направлении Твери" and locations is empty
    if not locations and threats:
        combined_t = " ".join(threats)
        if re.search(r"на\s+Москву", combined_t, re.IGNORECASE):
            locations.append("Москва")

    status_val = "active"
    if any("отбой" in t.lower() for t in threats):
        status_val = "over"

    combined_threat = " | ".join(threats)

    threat_translations = {
        "опасность по бпла": "UAV Danger",
        "ракетная опасность": "Missile Danger",
        "отбой опасности по бпла": "UAV Danger Over",
        "отбой ракетной опасности": "Missile Danger Over",
        "фиксации группы бпла": "UAV Group Detected",
        "фиксация группы бпла": "UAV Group Detected",
        "фиксации бпла": "UAV Detected",
        "фиксация бпла": "UAV Detected",
        "продолжается работа пво по бпла": "Air Defense Active (UAV)",
        "продолжается работа пво": "Air Defense Active",
        "работа пво по бпла": "Air Defense Active (UAV)",
        "работа пво": "Air Defense Active",
        "тревога по бпла": "UAV Alarm",
        "внимание по бпла": "UAV Attention",
        "меры безопасности": "Security Measures",
        "сбитие бпла": "UAV Shot Down",
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
        "в вашу сторону": "in your direction",
        "со стороны": "from the direction of",
        "крылатые ракеты большой дальности": "long-range cruise missiles",
        "возможно от": "possibly from",
    }

    english_threat = combined_threat
    # Sort keys by length descending so longer phrases match before shorter substrings
    for ru in sorted(threat_translations.keys(), key=len, reverse=True):
        en = threat_translations[ru]
        english_threat = re.sub(re.escape(ru), en, english_threat, flags=re.IGNORECASE)

    # --- MASTER CONTEXT LOGIC ---
    top_level_keywords = [
        "область",
        "край",
        "республика",
        "окг",
        "автономный округ",
        "oblast",
        "krai",
        "republic",
        "okrug",
    ]

    contexts = []
    for loc in locations:
        lower_loc = loc.lower()
        is_region = any(kw in lower_loc for kw in top_level_keywords)
        if is_region or lower_loc in ["крым", "республика крым", "crimea", "москва", "санкт-петербург"]:
            contexts.append(loc)

    if len(contexts) == 1:
        master_context = contexts[0]
    elif len(contexts) == 0 and channel_username:
        master_context = get_channel_default_context(channel_username)
    else:
        master_context = ""

    final_locs = []
    seen_full_names = set()

    for loc in locations:
        lower_loc = loc.lower()
        is_top_level = (
            any(kw in lower_loc for kw in top_level_keywords)
            or lower_loc in ["крым", "республика крым", "crimea", "москва", "санкт-петербург"]
        )

        if is_top_level:
            full_name = loc
        else:
            if master_context and master_context.lower() not in lower_loc:
                full_name = f"{loc}, {master_context}"
            else:
                full_name = loc

        if full_name not in seen_full_names:
            seen_full_names.add(full_name)
            final_locs.append(
                {
                    "name": full_name,
                    "icon": get_radar_icon(loc, combined_threat),
                    "raw_name": full_name,
                }
            )

    return {
        "id": msg_id,
        "channel": channel_username or (str(msg_id).split("/")[0] if "/" in str(msg_id) else "radarrussiia"),
        "time": time_str,
        "locations": final_locs,
        "threat": english_threat if english_threat else combined_threat,
        "raw_threat": combined_threat,
        "raw_text": text,
        "status": status_val,
    }


def init_radar_history_db(data_dir: Optional[Path] = None) -> Path:
    """Initializes the longitudinal SQLite database for all radar alerts and strike incidents."""
    d = data_dir or resolve_data_dir()
    db_path = d / "radar_history.db"
    db_key = str(db_path.resolve())
    if db_key in _INITIALIZED_DBS and db_path.exists():
        return db_path

    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS radar_alerts_history (
            record_key TEXT PRIMARY KEY,
            msg_id TEXT,
            channel TEXT,
            timestamp TEXT,
            raw_location TEXT,
            nominatim_query TEXT,
            resolved_name TEXT,
            osm_id TEXT,
            osm_type TEXT,
            lat REAL,
            lon REAL,
            threat TEXT,
            raw_threat TEXT,
            status TEXT,
            icon TEXT,
            source_type TEXT,
            post_url TEXT,
            media_json TEXT,
            raw_text TEXT,
            created_at TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_radar_hist_time ON radar_alerts_history(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_radar_hist_channel ON radar_alerts_history(channel)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_radar_hist_query ON radar_alerts_history(nominatim_query)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_radar_hist_type ON radar_alerts_history(source_type)")
    conn.commit()
    conn.close()
    _INITIALIZED_DBS.add(db_key)
    return db_path


def record_alert_to_history_db(
    parsed_alert: Dict[str, Any],
    geocode_cache: Optional[Dict[str, Any]] = None,
    data_dir: Optional[Path] = None,
    conn: Optional[sqlite3.Connection] = None,
):
    """Records a parsed radar alert (with each of its resolved locations) into radar_history.db."""
    if not parsed_alert.get("locations") or not parsed_alert.get("threat"):
        return

    d = data_dir or resolve_data_dir()
    db_path = init_radar_history_db(d)
    gc = geocode_cache or {}

    msg_id = str(parsed_alert.get("id", ""))
    channel = parsed_alert.get("channel") or (msg_id.split("/")[0] if "/" in msg_id else "radarrussiia")
    post_num = msg_id.split("/")[-1] if "/" in msg_id else msg_id
    post_url = f"https://t.me/{channel}/{post_num}" if channel and post_num else ""
    now_iso = datetime.now(timezone.utc).isoformat()

    owns_conn = conn is None
    active_conn = conn or sqlite3.connect(db_path, timeout=30.0)
    cursor = active_conn.cursor()
    try:
        for loc_info in parsed_alert.get("locations", []):
            query = loc_info.get("name", "")
            raw_loc = loc_info.get("raw_name", query)
            record_key = f"{msg_id}_{query}"

            geo = gc.get(query) if gc else None
            resolved_name = ""
            osm_id = ""
            osm_type = ""
            lat = None
            lon = None
            if geo and isinstance(geo, dict) and "empty" not in geo:
                display_name = geo.get("display_name", "")
                resolved_name = geo.get("name", "")
                if display_name and "," in display_name:
                    resolved_name = display_name.split(",")[0].strip()
                elif not resolved_name:
                    resolved_name = query
                osm_id = str(geo.get("osm_id", "")) if geo.get("osm_id") else ""
                osm_type = str(geo.get("osm_type", "")) if geo.get("osm_type") else ""
                try:
                    lat = float(geo["lat"]) if "lat" in geo else None
                    lon = float(geo["lon"]) if "lon" in geo else None
                except (ValueError, TypeError):
                    pass

            cursor.execute(
                """
                INSERT INTO radar_alerts_history (
                    record_key, msg_id, channel, timestamp, raw_location,
                    nominatim_query, resolved_name, osm_id, osm_type, lat, lon,
                    threat, raw_threat, status, icon, source_type, post_url,
                    media_json, raw_text, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_key) DO UPDATE SET
                    resolved_name = COALESCE(NULLIF(excluded.resolved_name, ''), radar_alerts_history.resolved_name),
                    osm_id = COALESCE(NULLIF(excluded.osm_id, ''), radar_alerts_history.osm_id),
                    osm_type = COALESCE(NULLIF(excluded.osm_type, ''), radar_alerts_history.osm_type),
                    lat = COALESCE(excluded.lat, radar_alerts_history.lat),
                    lon = COALESCE(excluded.lon, radar_alerts_history.lon),
                    threat = excluded.threat,
                    status = excluded.status
                """,
                (
                    record_key,
                    msg_id,
                    channel,
                    parsed_alert.get("time", ""),
                    raw_loc,
                    query,
                    resolved_name,
                    osm_id,
                    osm_type,
                    lat,
                    lon,
                    parsed_alert.get("threat", ""),
                    parsed_alert.get("raw_threat", ""),
                    parsed_alert.get("status", "active"),
                    loc_info.get("icon", ""),
                    "radar_alert",
                    post_url,
                    "[]",
                    parsed_alert.get("raw_text", ""),
                    now_iso,
                ),
            )
        if owns_conn:
            active_conn.commit()
    finally:
        if owns_conn:
            active_conn.close()


def record_incident_to_history_db(
    incident: Dict[str, Any],
    geocode_cache: Optional[Dict[str, Any]] = None,
    data_dir: Optional[Path] = None,
    conn: Optional[sqlite3.Connection] = None,
):
    """Records a regex-matched strike/incident post (e.g. znua_live) into radar_history.db."""
    d = data_dir or resolve_data_dir()
    db_path = init_radar_history_db(d)
    gc = geocode_cache or {}

    channel = incident.get("channel", "znua_live")
    msg_id = str(incident.get("msg_id", ""))
    record_key = incident.get("id") or f"{channel}_{msg_id}"
    query = incident.get("location_text", "")
    post_url = incident.get("post_url") or f"https://t.me/{channel}/{msg_id}"
    now_iso = datetime.now(timezone.utc).isoformat()

    geo = gc.get(query) if gc else None
    resolved_name = incident.get("name", "")
    osm_id = ""
    osm_type = ""
    lat = incident.get("lat")
    lon = incident.get("lng")

    if geo and isinstance(geo, dict) and "empty" not in geo:
        if not resolved_name:
            display_name = geo.get("display_name", "")
            resolved_name = geo.get("name", "")
            if display_name and "," in display_name:
                resolved_name = display_name.split(",")[0].strip()
            elif not resolved_name:
                resolved_name = query
        osm_id = str(geo.get("osm_id", "")) if geo.get("osm_id") else ""
        osm_type = str(geo.get("osm_type", "")) if geo.get("osm_type") else ""
        if lat is None or lon is None:
            try:
                lat = float(geo["lat"]) if "lat" in geo else None
                lon = float(geo["lon"]) if "lon" in geo else None
            except (ValueError, TypeError):
                pass

    media_list = incident.get("images", [])
    owns_conn = conn is None
    active_conn = conn or sqlite3.connect(db_path, timeout=30.0)
    cursor = active_conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO radar_alerts_history (
                record_key, msg_id, channel, timestamp, raw_location,
                nominatim_query, resolved_name, osm_id, osm_type, lat, lon,
                threat, raw_threat, status, icon, source_type, post_url,
                media_json, raw_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_key) DO UPDATE SET
                nominatim_query = excluded.nominatim_query,
                resolved_name = COALESCE(NULLIF(excluded.resolved_name, ''), radar_alerts_history.resolved_name),
                osm_id = COALESCE(NULLIF(excluded.osm_id, ''), radar_alerts_history.osm_id),
                osm_type = COALESCE(NULLIF(excluded.osm_type, ''), radar_alerts_history.osm_type),
                lat = COALESCE(excluded.lat, radar_alerts_history.lat),
                lon = COALESCE(excluded.lon, radar_alerts_history.lon),
                threat = excluded.threat,
                icon = excluded.icon,
                media_json = excluded.media_json
            """,
            (
                record_key,
                f"{channel}/{msg_id}",
                channel,
                incident.get("time", ""),
                incident.get("raw_location_text", query),
                query,
                resolved_name,
                osm_id,
                osm_type,
                lat,
                lon,
                incident.get("description", ""),
                incident.get("description", ""),
                incident.get("status", "active"),
                incident.get("icon", "🔥"),
                "telegram_incident",
                post_url,
                json.dumps(media_list, ensure_ascii=False),
                incident.get("full_text", incident.get("description", "")),
                now_iso,
            ),
        )
        if owns_conn:
            active_conn.commit()
    finally:
        if owns_conn:
            active_conn.close()


def save_radar_alert_to_live_cache(parsed_alert: Dict[str, Any], data_dir: Optional[Path] = None) -> bool:
    """Atomically saves a parsed radar alert into data/radar_alerts.json (if within 24h and valid)."""
    if not parsed_alert.get("locations") or not parsed_alert.get("threat"):
        return False

    d = data_dir or resolve_data_dir()
    cache_file = d / "radar_alerts.json"

    try:
        alert_time = datetime.fromisoformat(parsed_alert["time"].replace("Z", "+00:00"))
        if alert_time.tzinfo is None:
            alert_time = alert_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if (now - alert_time).total_seconds() > 24 * 3600:
            return False
    except Exception:
        pass

    cached_alerts = {}
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_alerts = json.load(f)
        except Exception:
            cached_alerts = {}

    now = datetime.now(timezone.utc)
    for k in list(cached_alerts.keys()):
        try:
            t = datetime.fromisoformat(cached_alerts[k]["time"].replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if (now - t).total_seconds() > 24 * 3600:
                del cached_alerts[k]
        except Exception:
            del cached_alerts[k]

    cached_alerts[parsed_alert["id"]] = parsed_alert

    temp_file = cache_file.with_suffix(f".tmp.{uuid.uuid4().hex}")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(cached_alerts, f, ensure_ascii=False, indent=2)
    _safe_replace(temp_file, cache_file)
    return True


def save_incident_to_live_cache(incident_data: Dict[str, Any], data_dir: Optional[Path] = None) -> str:
    """Atomically saves or updates an incident in data/telegram_incidents.json."""
    d = data_dir or resolve_data_dir()
    incidents_file = d / "telegram_incidents.json"

    records = {}
    if incidents_file.exists():
        try:
            with open(incidents_file, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = {}

    record_id = incident_data.get("id") or f"{incident_data['channel']}_{incident_data['msg_id']}"
    incident_data["id"] = record_id

    # Preserve manual admin edits if re-scraping an existing incident
    if record_id in records and records[record_id].get("admin_modified"):
        existing = records[record_id]
        for img in incident_data.get("images", []):
            if img not in existing.get("images", []):
                existing.setdefault("images", []).append(img)
        records[record_id] = existing
    else:
        records[record_id] = incident_data

    temp_file = incidents_file.with_suffix(f".tmp.{uuid.uuid4().hex}")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    _safe_replace(temp_file, incidents_file)
    return record_id


class SimpleHTTPMessage:
    """Lightweight message object compatible with Telethon Message interface for HTTP fallback."""

    def __init__(self, msg_id: int, message_text: str, msg_date: datetime, photo_urls: Optional[List[str]] = None):
        self.id = msg_id
        self.message = message_text
        self.date = msg_date
        self.photo_urls = photo_urls or []
        self.photo = bool(self.photo_urls)
        self.grouped_id = None


def parse_tme_s_html(raw_html: str) -> List[SimpleHTTPMessage]:
    """Parses public Telegram web preview HTML (https://t.me/s/<channel>) using stdlib."""
    import html as html_mod

    results: List[SimpleHTTPMessage] = []
    blocks = re.split(r'(?=<div class="tgme_widget_message\b)', raw_html)
    for block in blocks:
        post_m = re.search(r'data-post="([^"/]+)/(\d+)"', block)
        if not post_m:
            continue
        msg_id = int(post_m.group(2))

        time_m = re.search(r'<time[^>]+datetime="([^"]+)"', block)
        time_str = time_m.group(1) if time_m else ""
        try:
            msg_date = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            if msg_date.tzinfo is None:
                msg_date = msg_date.replace(tzinfo=timezone.utc)
        except Exception:
            msg_date = datetime.now(timezone.utc)

        text_m = re.search(
            r'<div class="tgme_widget_message_text js-message_text"[^>]*>(.*?)</div>\s*(?:<div|<a|<time|<span)',
            block,
            re.DOTALL,
        )
        if not text_m:
            text_m = re.search(
                r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
                block,
                re.DOTALL,
            )
        text_html = text_m.group(1) if text_m else ""
        text_clean = re.sub(r"<br\s*/?>", "\n", text_html, flags=re.IGNORECASE)
        text_clean = re.sub(r"<[^>]+>", "", text_clean)
        text_clean = html_mod.unescape(text_clean).strip()

        photo_urls = re.findall(
            r"tgme_widget_message_photo_wrap[^>]+background-image:url\('([^']+)'\)",
            block,
        )
        results.append(SimpleHTTPMessage(msg_id, text_clean, msg_date, photo_urls))
    return results


async def fetch_channel_messages_http(
    channel_username: str,
    limit: int,
    http_client: httpx.AsyncClient,
) -> List[SimpleHTTPMessage]:
    """Fetches up to `limit` historical messages from https://t.me/s/<channel> using ?before= pagination."""
    collected: Dict[int, SimpleHTTPMessage] = {}
    before_id: Optional[int] = None
    max_pages = max(1, (limit + 19) // 20)

    for _ in range(max_pages):
        url = f"https://t.me/s/{channel_username}"
        if before_id is not None:
            url += f"?before={before_id}"
        try:
            resp = await http_client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                follow_redirects=True,
            )
            if resp.status_code != 200:
                break
            batch = parse_tme_s_html(resp.text)
            if not batch:
                break
            new_ids = []
            for m in batch:
                if m.id not in collected:
                    collected[m.id] = m
                    new_ids.append(m.id)
            if not new_ids or len(collected) >= limit:
                break
            before_id = min(new_ids)
        except Exception:
            break

    # Return newest-first (matching Telethon client.get_messages order) up to limit
    sorted_msgs = sorted(collected.values(), key=lambda x: x.id, reverse=True)
    return sorted_msgs[:limit]


async def download_embed_photos_http(
    channel_username: str,
    msg_id: int,
    images_dir: Path,
    http_client: httpx.AsyncClient,
) -> List[str]:
    """Downloads all photos (including media album photos) for a public Telegram post via ?embed=1."""
    images_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://t.me/{channel_username}/{msg_id}?embed=1"
    saved_files: List[str] = []
    try:
        resp = await http_client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return saved_files
        photo_urls = re.findall(r"background-image:url\('(https://[^']+)'\)", resp.text)
        seen_urls = []
        for u in photo_urls:
            if u not in seen_urls:
                seen_urls.append(u)

        for idx, photo_url in enumerate(seen_urls):
            suffix = "" if idx == 0 else f"_{idx + 1}"
            filename = f"tg_{channel_username}_{msg_id}{suffix}.jpg"
            dest = images_dir / filename
            if dest.exists() and dest.stat().st_size > 0:
                saved_files.append(filename)
                continue
            img_resp = await http_client.get(photo_url, follow_redirects=True)
            if img_resp.status_code == 200 and img_resp.content:
                dest.write_bytes(img_resp.content)
                saved_files.append(filename)
    except Exception as e:
        print(f"HTTP photo download error for {channel_username}/{msg_id}: {e}")
    return saved_files
