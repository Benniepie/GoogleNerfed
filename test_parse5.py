import urllib.request
import urllib.parse
import json

def geocode_location(location_str):
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location_str)}&format=json&polygon_geojson=1&limit=1&accept-language=ru,en"
    req = urllib.request.Request(url, headers={'User-Agent': 'MyMaps/1.0'})
    try:
        resp = urllib.request.urlopen(req).read().decode('utf-8')
        data = json.loads(resp)
        if data:
            return data[0]
    except Exception as e:
        print(f"Geocode error for {location_str}:", e)
    return None

loc = geocode_location("Краснодарский край, Республика Адыгея")
print(loc)
loc2 = geocode_location("Республика Адыгея")
print(loc2 is not None)
