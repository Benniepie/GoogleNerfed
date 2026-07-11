import sys
sys.path.append('.')
import urllib.parse
import urllib.request
import json
from pathlib import Path
DATA_DIR = Path('/app/data')
DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_cached_geocode(location_name: str):
    cache_file = DATA_DIR / "geocode_cache.json"
    cache = {}
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass

    if location_name in cache:
        return cache[location_name]

    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location_name)}&format=json&polygon_geojson=1&limit=1&accept-language=ru,en"
    req = urllib.request.Request(url, headers={'User-Agent': 'ATPGeopolitics/1.0'})
    try:
        resp = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
        data = json.loads(resp)
        if data:
            result = data[0]
            cache[location_name] = result
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            return result
    except Exception as e:
        print(f"Geocode error for {location_name}: {e}")

    return None

res = get_cached_geocode("Славянский район, Краснодарский край")
print("Found cache file?", (DATA_DIR / "geocode_cache.json").exists())
print("Result type:", res.get('type') if res else None)
