import re

# ==========================================
# TELEGRAM SCRAPER CONFIGURATION
# Add new channels and rules here! No JSON editing required.
# ==========================================

CHANNEL_CONFIGS = {
    "znua_live": {
        # Regex patterns to match.
        # Group 1 (in parentheses) MUST be the location string.
        # Group 2 (in parentheses) MUST be the rest of the text/description.
        "patterns": [
            re.compile(r"✅✅✅✅✅⚡️💥⚡️\s*([^—]+)—(.*)"),
            re.compile(r"✅✅✅✅✅💥💥💥\s*([^—]+)—(.*)"),
            re.compile(r"✅✅✅✅✅💥⚡️💥\s*([^—]+)—(.*)")
        ],
        "icon": "🔥",
        "country_restrict": "ru", # Tell Nominatim to only look in Russia for these
        "location_group": 1,
        "description_group": 2
    }
    # To add another channel later, just add another block here:
    # "another_channel": { ... }
}
