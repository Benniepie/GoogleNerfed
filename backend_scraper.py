import asyncio
import httpx
import json
from bs4 import BeautifulSoup
import re

def parse_message(text, msg_id, time_str):
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if "❗️" in line or "Обход белых списков" in line or "@radarrussiia" in line or "Радар по всей России" in line or "Internet_Boost_bot" in line or "🌐" in line:
            continue
        if line:
            cleaned_lines.append(line)

    threat_keywords = ["опасность", "фиксация", "отбой", "работа", "пво", "ракет", "бпла", "приготовиться", "тревога", "меры", "сбит", "угроза"]

    locations = []
    threats = []

    for line in cleaned_lines:
        parts = line.split(' - ')
        for part in parts:
            part = part.strip()
            is_threat = any(kw in part.lower() for kw in threat_keywords)
            if is_threat or len(part) > 50:
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
        if any(x in loc.lower() for x in ["область", "край", "республика", "окг", "округ"]):
            context = loc
            break

    final_locs = []
    for loc in locations:
        if loc == context:
            final_locs.append(loc)
        elif context:
            final_locs.append(f"{loc}, {context}")
        else:
            final_locs.append(loc)

    return {
        "id": msg_id,
        "time": time_str,
        "locations": final_locs,
        "threat": " | ".join(threats),
        "status": status
    }

async def fetch_telegram_data():
    url = "https://t.me/s/radarrussiia"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        html = resp.text

    soup = BeautifulSoup(html, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_wrap')

    parsed = []
    for msg in messages:
        msg_el = msg.find('div', class_='tgme_widget_message')
        if not msg_el: continue
        msg_id = msg_el.get('data-post', '')

        text_div = msg.find('div', class_='tgme_widget_message_text')
        if not text_div: continue
        text = text_div.get_text(separator='\n').strip()

        time_tag = msg.find('time')
        time_str = time_tag['datetime'] if time_tag else ''

        parsed.append(parse_message(text, msg_id, time_str))

    print(json.dumps(parsed[-2:], indent=2, ensure_ascii=False))

asyncio.run(fetch_telegram_data())
