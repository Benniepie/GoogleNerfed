import asyncio
import json
import os
import sys
from datetime import datetime
from telethon import TelegramClient, events
from telegram_config import CHANNEL_CONFIGS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Make sure API_ID and API_HASH are in your .env file
API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
OUTPUT_JSON = 'data/telegram_incidents.json'

# ALLOW EXPLICIT PATH: Defaults to 'mapping_userbot' in current directory
SESSION_PATH = os.getenv("TELEGRAM_SESSION_PATH", "mapping_userbot")

if not API_ID or not API_HASH:
    print("❌ ERROR: TELEGRAM_API_ID or TELEGRAM_API_HASH is missing from environment.")
    exit(1)

# PREVENT EOF ERROR LOOP: Check if the session file actually exists before starting
session_file_name = f"{SESSION_PATH}.session"
if not os.path.exists(session_file_name):
    print(f"❌ CRITICAL ERROR: Session file not found at '{os.path.abspath(session_file_name)}'")
    print("In a Docker environment, you must provide a valid .session file to prevent interactive login prompts.")
    sys.exit(1)

# The session file stores the login state. Keep this out of GitHub!
client = TelegramClient(SESSION_PATH, API_ID, API_HASH)

def save_incident_to_json(data):
    """Safely append the extracted incident to our JSON file."""
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    records = {}
    if os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except json.JSONDecodeError:
            pass

    # Use a combined key of channel + msg_id to ensure uniqueness
    record_id = f"{data['channel']}_{data['msg_id']}"
    records[record_id] = data

    # Atomic write to prevent corruption
    temp_file = f"{OUTPUT_JSON}.tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, OUTPUT_JSON)

    print(f"✅ Saved incident {record_id} to JSON.")

# Listen to all channels defined in our config
#target_channels = list(CHANNEL_CONFIGS.keys())
target_channels = {k.lower(): v for k, v in CHANNEL_CONFIGS.items()}

@client.on(events.NewMessage(incoming=True))
async def handle_new_message(event):
    """Triggers instantly when any channel posts."""
    message = event.message
    text = message.message or ""

    # Get the channel name safely
    chat = await event.get_chat()
    if not chat:
        return

    channel_username = getattr(chat, 'username', None)
    if not channel_username:
        return

    channel_username = channel_username.lower()

    # Drop messages from channels we don't care about
    if channel_username not in target_channels:
        return

    # --- RAW DEBUG DUMP ---
    # This writes the EXACT raw string to a text file so you can see hidden characters
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open('data/telegram_debug.txt', 'a', encoding='utf-8') as f:
        f.write(f"--- MSG FROM {channel_username} (ID: {message.id}) ---\n")
        f.write(repr(text)) # repr() reveals \n, \r, and hidden unicode characters
        f.write("\n\n")

    safe_text = text[:80].replace('\n', ' ')
    print(f"👀 MSG RECEIVED in {channel_username}: {safe_text}...")

    config = target_channels[channel_username]

    for pattern in config["patterns"]:
        match = pattern.search(text)
        if match:
            location_text = match.group(config["location_group"]).strip()
            description = match.group(config["description_group"]).strip()

            print(f"🔥 MATCH in {channel_username}! Location: {location_text}")

            # Construct the iframe embed URL for the Leaflet popup
            embed_url = f"https://t.me/{channel_username}/{message.id}?embed=1"

            incident_data = {
                "channel": channel_username,
                "msg_id": message.id,
                "time": message.date.isoformat(),
                "location_text": location_text,
                "description": description,
                "embed_url": embed_url,
                "icon": config.get("icon", "📍"),
                "country_restrict": config.get("country_restrict", "ru,ua"),
                "plot_type": config.get("plot_type", "polygon"),
                "embed_post": config.get("embed_post", False)
            }

            save_incident_to_json(incident_data)
            break # Stop checking patterns if we found a match

async def main():
    print("Starting Telegram Incident Userbot...")

    # Connect to Telegram headless (does not prompt for input)
    await client.connect()

    # Explicitly check if the session is authorized
    if not await client.is_user_authorized():
        print(f"❌ CRITICAL ERROR: Session file '{SESSION_PATH}.session' was found, but it is NOT authorized.")
        print("This usually happens for three reasons:")
        print("  1. You clicked 'Terminate all other sessions' in your Telegram app.")
        print("  2. The local script was still running when you copied the file (SQLite WAL file was missed).")
        print("  3. The API_ID/API_HASH don't match the ones used to create the session.")
        print("Please generate a new session file locally and replace it.")
        sys.exit(1)

    print(f"✅ Successfully logged in as Userbot!")
    print("Waking up channel subscriptions...")
    # CRITICAL FIX: Fetching dialogs wakes up Telegram's update socket for this session
    # and populates Telethon's internal entity cache so it knows channel IDs.
    await client.get_dialogs()
    print(f"📡 Listening to: {', '.join(target_channels)}")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
