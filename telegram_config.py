import re
from typing import Dict, Any, List, Optional

# ==========================================
# TELEGRAM SCRAPER & CHANNEL CONFIGURATION
# ==========================================
# Types of channels:
# 1. "radar_alert": Russian air alert / drone detection / air defence channels.
#    Messages are parsed through the radar alert parser (with location extraction,
#    default regional context fallback, threat translation, and geocode overrides),
#    and stored both in the 24h live cache (`radar_alerts.json`) and in the
#    permanent SQLite history database (`radar_history.db`).
# 2. "regex_incident": Regex-matched incident/strike channels (e.g., znua_live).
#    Messages matching any configured regex pattern have their location, text,
#    link, and photos extracted, saved to `telegram_incidents.json` and
#    `radar_history.db`, and plotted as customizable markers on the Radar Russia layer.

RADAR_CHANNELS: Dict[str, Dict[str, Any]] = {
    "radarrussiia": {
        "type": "radar_alert",
        "label": "Радар по всей России",
        "default_context": "",
    },
    "radar_lipetskk": {
        "type": "radar_alert",
        "label": "Липецк и область",
        "default_context": "Липецкая область",
    },
    "radar_orei": {
        "type": "radar_alert",
        "label": "Орел и область",
        "default_context": "Орловская область",
    },
    "radar_voronezh": {
        "type": "radar_alert",
        "label": "Воронеж и область",
        "default_context": "Воронежская область",
    },
    "radar_smolensk": {
        "type": "radar_alert",
        "label": "Смоленск и область",
        "default_context": "Смоленская область",
    },
    "radar_moscoww": {
        "type": "radar_alert",
        "label": "Москва и область",
        "default_context": "Московская область",
    },
    "radar_tver": {
        "type": "radar_alert",
        "label": "Тверь и область",
        "default_context": "Тверская область",
    },
    "radar_tuia": {
        "type": "radar_alert",
        "label": "Тула и область",
        "default_context": "Тульская область",
    },
    "radar_volgograd": {
        "type": "radar_alert",
        "label": "Волгоград и область",
        "default_context": "Волгоградская область",
    },
    "radar_tambov": {
        "type": "radar_alert",
        "label": "Тамбов и область",
        "default_context": "Тамбовская область",
    },
    "radar_rostovv": {
        "type": "radar_alert",
        "label": "Ростов (Таганрог / Морозовск)",
        "default_context": "Ростовская область",
    },
    "radar_kras": {
        "type": "radar_alert",
        "label": "Краснодарский край (Ейск / Новороссийск)",
        "default_context": "Краснодарский край",
    },
    "radar_crimeaa": {
        "type": "radar_alert",
        "label": "Крым",
        "default_context": "Республика Крым",
    },
    "radar_bryanskk": {
        "type": "radar_alert",
        "label": "Брянск",
        "default_context": "Брянская область",
    },
    "radar_beigorod": {
        "type": "radar_alert",
        "label": "Белгород",
        "default_context": "Белгородская область",
    },
    "radar_kurskk": {
        "type": "radar_alert",
        "label": "Курск",
        "default_context": "Курская область",
    },
    "rada_saratov": {
        "type": "radar_alert",
        "label": "Саратов и область",
        "default_context": "Саратовская область",
    },
    "radar_engels": {
        "type": "radar_alert",
        "label": "Энгельс и область",
        "default_context": "Саратовская область",
    },
    "radar_elets": {
        "type": "radar_alert",
        "label": "Елец",
        "default_context": "Липецкая область",
    },
    "radar_ryazan": {
        "type": "radar_alert",
        "label": "Рязань и область",
        "default_context": "Рязанская область",
    },
    "radar_kaluga": {
        "type": "radar_alert",
        "label": "Калуга и область",
        "default_context": "Калужская область",
    },
    "radar_vladimir": {
        "type": "radar_alert",
        "label": "Владимир",
        "default_context": "Владимирская область",
    },
    "radar_livni": {
        "type": "radar_alert",
        "label": "Ливны",
        "default_context": "Орловская область",
    },
    "radar_tatarstann": {
        "type": "radar_alert",
        "label": "Республика Татарстан (Казань)",
        "default_context": "Республика Татарстан",
    },
    "kubanoperativ": {
        "type": "radar_alert",
        "label": "Кубань",
        "default_context": "Краснодарский край",
    },
    "radar_ahtari": {
        "type": "radar_alert",
        "label": "Приморско-Ахтарск",
        "default_context": "Краснодарский край",
    },
    "radar_samaraa": {
        "type": "radar_alert",
        "label": "Самара и область",
        "default_context": "Самарская область",
    },
    "radar_bashkortostan": {
        "type": "radar_alert",
        "label": "Республика Башкортостан",
        "default_context": "Республика Башкортостан",
    },
    "radar_nizhniinovgorod": {
        "type": "radar_alert",
        "label": "Нижегородская область",
        "default_context": "Нижегородская область",
    },
    "radar_vologda": {
        "type": "radar_alert",
        "label": "Вологда и область",
        "default_context": "Вологодская область",
    },
    "radar_udmurtiya": {
        "type": "radar_alert",
        "label": "Республика Удмуртия (Ижевск)",
        "default_context": "Удмуртская Республика",
    },
    "radar_peterburg": {
        "type": "radar_alert",
        "label": "Питер и область",
        "default_context": "Ленинградская область",
    },
    "radar_astrakhann": {
        "type": "radar_alert",
        "label": "Астрахань и область",
        "default_context": "Астраханская область",
    },
    "radar_ulyanovsk": {
        "type": "radar_alert",
        "label": "Ульяновск и область",
        "default_context": "Ульяновская область",
    },
    "radar_mordoviya": {
        "type": "radar_alert",
        "label": "Республика Мордовия",
        "default_context": "Республика Мордовия",
    },
    "radar_chuvashiya": {
        "type": "radar_alert",
        "label": "Республика Чувашия",
        "default_context": "Чувашская Республика",
    },
    "stavropol_radar": {
        "type": "radar_alert",
        "label": "Ставропольский край",
        "default_context": "Ставропольский край",
    },
    "radar_adygeya": {
        "type": "radar_alert",
        "label": "Республика Адыгея",
        "default_context": "Республика Адыгея",
    },
    "radar_penzaa": {
        "type": "radar_alert",
        "label": "Пензенская область",
        "default_context": "Пензенская область",
    },
    "radar_sochiii": {
        "type": "radar_alert",
        "label": "Сочи (Адлер, Лазаревское, Сириус)",
        "default_context": "Краснодарский край",
    },
    "radar_pskovv": {
        "type": "radar_alert",
        "label": "Псковская область",
        "default_context": "Псковская область",
    },
}

INCIDENT_CHANNELS: Dict[str, Dict[str, Any]] = {
    "znua_live": {
        "type": "regex_incident",
        "label": "ZN.UA Strikes",
        # Group 1 (in parentheses) MUST be the location string.
        # Group 2 (in parentheses) MUST be the rest of the text/description.
        "patterns": [
            re.compile(r"✅✅✅✅✅⚡️💥⚡️\s*([^—\n]+)—\s*(.*)", re.DOTALL),
            re.compile(r"✅✅✅✅✅💥💥💥\s*([^—\n]+)—\s*(.*)", re.DOTALL),
            re.compile(r"✅✅✅✅✅💥⚡️💥\s*([^—\n]+)—\s*(.*)", re.DOTALL),
            re.compile(r"✅{3,}[⚡️💥🔥]+\s*([^—\n]+)—\s*(.*)", re.DOTALL),
        ],
        "icon": "🔥",
        "marker_type": "emoji",
        "marker_color": "#f97316",
        "marker_border": "#ffffff",
        "category": "Strike / Hit",
        "country_restrict": "ru",  # Tell Nominatim to only look in Russia for these
        "location_group": 1,
        "description_group": 2,
        "plot_type": "marker",
        "embed_post": False,
        "strip_footers": [
            r"🚀\s*Підтримати.*",
            r"🚀\s*Приєднатися до ZN\.UA.*",
            r"Підтримати ZN\.UA.*",
            r"Приєднатися до ZN\.UA.*",
        ],
    }
}

CHANNEL_CONFIGS: Dict[str, Dict[str, Any]] = {
    **RADAR_CHANNELS,
    **INCIDENT_CHANNELS,
}


def get_channel_default_context(channel_username: Optional[str]) -> str:
    if not channel_username:
        return ""
    ch = CHANNEL_CONFIGS.get(channel_username.lower(), {})
    return ch.get("default_context", "")


def clean_incident_location(raw_location: str) -> str:
    """Cleans location strings extracted from strike posts (e.g. 'УФА, Башкортостан, рф' -> 'Уфа, Башкортостан')."""
    loc = raw_location.strip()
    # Remove trailing 'рф' / 'РФ' / 'россия' tokens so Nominatim geocodes cleanly
    loc = re.sub(r"[,\s]+\b(?:рф|россия|росія)\b\.?$", "", loc, flags=re.IGNORECASE).strip()
    loc = loc.strip(" ,—-")
    return loc


def clean_incident_description(raw_text: str, strip_footers: Optional[List[str]] = None) -> str:
    text = raw_text.strip()
    if strip_footers:
        for pat in strip_footers:
            text = re.sub(pat, "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    return text
