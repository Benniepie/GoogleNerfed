import asyncio
import websockets
import json
import sqlite3
import os
import time
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
    conn.commit()
    return conn

async def connect_ais():
    print("Connecting to AISStream...")
    conn = init_db()

    # Optional filtering to reduce load
    subscription = {
        "APIKey": API_KEY,
        "BoundingBoxes": BOUNDING_BOXES,
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
    }

    try:
        async with websockets.connect("wss://stream.aisstream.io/v0/stream") as ws:
            await ws.send(json.dumps(subscription))
            print("Connected and subscribed!")

            while True:
                message = await ws.recv()
                data = json.loads(message)

                cursor = conn.cursor()
                now = datetime.now(timezone.utc).isoformat()

                if data["MessageType"] == "PositionReport":
                    msg = data["Message"]["PositionReport"]
                    mmsi = str(data["MetaData"]["MMSI"])
                    lat = msg["Latitude"]
                    lon = msg["Longitude"]
                    heading = msg["TrueHeading"]

                    if lat is not None and lon is not None and lat <= 90.0 and lon <= 180.0:
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
                    mmsi = str(data["MetaData"]["MMSI"])
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
