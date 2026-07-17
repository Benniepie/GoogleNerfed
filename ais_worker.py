import asyncio
import websockets
import json
import sqlite3
import os
import time
import math
from datetime import datetime, timezone

DB_PATH = "/app/data/vessels.db"
# You'll need to set your API key in the environment
API_KEY = os.getenv("AIS_API_KEY", "YOUR_API_KEY")

# Combine all bounding boxes into a single list of lists
# [ [min_lat, min_lon], [max_lat, max_lon] ]
BOUNDING_BOXES = [
    [[-90.0, -180.0], [90.0, 180.0]] # Global, as per requested logic
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    return conn

def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance in kilometers between two points on the earth."""
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371 # Radius of earth in kilometers
    return c * r

async def connect_ais():
    print("Connecting to AISStream...")
    conn = init_db()

    # Optional filtering to reduce load
    subscription = {
        "APIKey": API_KEY,
        "BoundingBoxes": BOUNDING_BOXES,
        "FilterMessageTypes": ["PositionReport", "StandardClassBPositionReport", "ShipStaticData"]
    }

    # Local cache to prevent querying SQLite for every single websocket message
    target_mmsis = set()
    last_cache_update = 0
    CACHE_TTL = 60 # Refresh target list every 60 seconds

    msg_count = 0
    target_hits = 0
    last_log_time = time.time()

    # Stateful cache for last known positions to prevent spoofing jumps
    last_positions = {}

    try:
        async with websockets.connect("wss://stream.aisstream.io/v0/stream") as ws:
            await ws.send(json.dumps(subscription))
            print("Connected and subscribed! Waiting for data...")

            while True:
                message = await ws.recv()
                data = json.loads(message)

                msg_count += 1
                current_time = time.time()

                # Refresh target cache if expired
                if current_time - last_cache_update > CACHE_TTL:
                    cursor = conn.cursor()
                    cursor.execute("SELECT mmsi FROM shadow_fleet_targets")
                    target_mmsis = {row[0] for row in cursor.fetchall()}
                    last_cache_update = current_time
                    print(f"Refreshed target cache. Monitoring {len(target_mmsis)} target vessels.")

                # Log metrics every 10 seconds
                if current_time - last_log_time > 10:
                    print(f"Processed {msg_count} raw messages in the last 10s. Target vessel pings recorded: {target_hits}")
                    msg_count = 0
                    target_hits = 0
                    last_log_time = current_time

                cursor = conn.cursor()
                now = datetime.now(timezone.utc).isoformat()

                mmsi = str(data.get("MetaData", {}).get("MMSI", ""))
                if not mmsi or mmsi not in target_mmsis:
                    continue

                target_hits += 1

                if data["MessageType"] in ["PositionReport", "StandardClassBPositionReport"]:
                    msg = data["Message"].get("PositionReport") or data["Message"].get("StandardClassBPositionReport")
                    if not msg:
                        continue
                    lat = msg["Latitude"]
                    lon = msg["Longitude"]
                    heading = msg["TrueHeading"]

                    if lat is not None and lon is not None and lat <= 90.0 and lon <= 180.0:

                        is_valid = True
                        if mmsi in last_positions:
                            last_pos = last_positions[mmsi]
                            dist_km = haversine_distance(last_pos['lon'], last_pos['lat'], lon, lat)
                            time_diff_hours = (current_time - last_pos['time']) / 3600.0

                            if time_diff_hours > 0:
                                speed_kmh = dist_km / time_diff_hours
                                if speed_kmh > 80 and dist_km > 20:
                                    is_valid = False
                            elif dist_km > 5:
                                is_valid = False

                            if not is_valid:
                                last_pos['reject_count'] = last_pos.get('reject_count', 0) + 1
                                if last_pos['reject_count'] > 3:
                                    # Too many rejects, assume we were stuck on a spoofed point and recover
                                    is_valid = True

                        if is_valid:
                            last_positions[mmsi] = {'lon': lon, 'lat': lat, 'time': current_time, 'reject_count': 0}

                            # Insert/update basic position
                            cursor.execute('''
                            INSERT INTO vessels (mmsi, last_seen, last_lon, last_lat, heading)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(mmsi) DO UPDATE SET
                                last_seen=excluded.last_seen,
                                last_lon=excluded.last_lon,
                                last_lat=excluded.last_lat,
                                heading=excluded.heading
                            ''', (mmsi, now, lon, lat, heading))

                            # Save track
                            cursor.execute('''
                            INSERT INTO tracks (mmsi, lon, lat, timestamp)
                            VALUES (?, ?, ?, ?)
                            ''', (mmsi, lon, lat, now))

                            conn.commit()

                elif data["MessageType"] == "ShipStaticData":
                    msg = data["Message"]["ShipStaticData"]
                    name = msg.get("Name", "").strip()
                    ship_type = "Unknown"
                    # Simple ship type mapping from AIS type code (mocking mapping here)
                    if 70 <= msg.get("Type", 0) <= 79:
                        ship_type = "Cargo"
                    elif 80 <= msg.get("Type", 0) <= 89:
                        ship_type = "Tanker"

                    cursor.execute('''
                    INSERT INTO vessels (mmsi, name, ship_type, last_seen)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(mmsi) DO UPDATE SET
                        name=excluded.name,
                        ship_type=excluded.ship_type
                    ''', (mmsi, name, ship_type, now))

                    conn.commit()

    except Exception as e:
        print(f"Error in AIS stream: {e}")
        time.sleep(5)
        # Restart logic can be handled by Docker restart policy or adding a loop here

if __name__ == "__main__":
    # Ensure dir exists before starting db
    while not os.path.exists("/app/data"):
        print("Waiting for data directory...")
        time.sleep(2)
    asyncio.run(connect_ais())
