import re

with open('main.py', 'r') as f:
    content = f.read()

# Fix get_sentinel_metadata signature and return type
old_endpoint = """@app.get("/api/sentinel-metadata")
def get_sentinel_metadata(lat: float, lng: float, z: int):
    \"\"\"Returns a GeoJSON FeatureCollection of the cached STAC data.\"\"\"
    # We round the coordinates just like the tile endpoint to hit the same cache key
    center_lat = round(lat * 2) / 2
    center_lng = round(lng * 2) / 2

    features = get_stac_features(center_lat, center_lng, z)

    return Response(
        content={"type": "FeatureCollection", "features": features},
        media_type="application/json"
    )"""

new_endpoint = """@app.get("/api/sentinel-metadata")
def get_sentinel_metadata(lat: float, lng: float, z: float):
    \"\"\"Returns a GeoJSON FeatureCollection of the cached STAC data.\"\"\"
    # We round the coordinates just like the tile endpoint to hit the same cache key
    center_lat = round(lat * 2) / 2
    center_lng = round(lng * 2) / 2

    features = get_stac_features(center_lat, center_lng, z)

    return {"type": "FeatureCollection", "features": features}"""

content = content.replace(old_endpoint, new_endpoint)

# Fix get_stac_features signature
old_stac = """def get_stac_features(lat: float, lng: float, z: int):"""
new_stac = """def get_stac_features(lat: float, lng: float, z: float):"""
content = content.replace(old_stac, new_stac)

with open('main.py', 'w') as f:
    f.write(content)
