import re
import bs4

def get_icon(location_str, threat_str):
    combined = (location_str + " " + threat_str).lower()
    if any(kw in combined for kw in ["аэропорт", "аэродром", "airport", "авиабаза"]): return "✈️"
    if any(kw in combined for kw in ["нпз", "нефте", "oil", "naval base", "порт", "терминал"]): return "🛢️"
    if any(kw in combined for kw in ["море", "залив", "sea", "вода", "океан", "акватория"]): return "🌊"
    return ""

def parse_message(text, msg_id, time_str):
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if "❗️" in line or "Обход белых списков" in line or "@radarrussiia" in line or "Радар по всей России" in line or "Internet_Boost_bot" in line or "🌐" in line or "Ускоритель Интернета" in line or "Остались какие-то вопросы" in line:
            continue
        if line:
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

    status = "active"
    if any("отбой" in t.lower() for t in threats):
        status = "over"

    context = ""
    for loc in reversed(locations):
        if any(x in loc.lower() for x in ["область", "край", "республика", "окг", "округ", "крым"]):
            context = loc
            break

    final_locs = []
    for loc in locations:
        if loc == context:
            final_locs.append({"name": loc, "icon": get_icon(loc, " | ".join(threats))})
        elif context:
            final_locs.append({"name": f"{loc}, {context}", "icon": get_icon(f"{loc}, {context}", " | ".join(threats))})
        else:
            final_locs.append({"name": loc, "icon": get_icon(loc, " | ".join(threats))})

    return {
        "id": msg_id,
        "time": time_str,
        "locations": final_locs,
        "threat": " | ".join(threats),
        "status": status
    }
