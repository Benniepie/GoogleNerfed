import json

def get_icon(locations, threat):
    # Determine the icon to use based on keywords in location and threat
    is_plane = any(kw in (", ".join(locations) + " " + threat).lower() for kw in ["аэропорт", "аэродром", "airport"])
    is_oil = any(kw in (", ".join(locations) + " " + threat).lower() for kw in ["нпз", "нефте", "oil", "naval base", "порт"])
    is_water = any(kw in (", ".join(locations) + " " + threat).lower() for kw in ["море", "залив", "sea", "вода"])

    if is_plane: return "✈️"
    if is_oil: return "🛢️"
    if is_water: return "🌊"
    return "alert"

print(get_icon(["Азовское море"], ""))
print(get_icon(["Аэродром Энгельс"], ""))
print(get_icon(["Туапсе, НПЗ"], ""))
print(get_icon(["Таганрог"], ""))
