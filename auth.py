import asyncio
import getpass
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PasswordHashInvalidError
import qrcode

load_dotenv()
API_ID_RAW = os.getenv("TELEGRAM_API_ID", "0").strip().strip('"').strip("'")
API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip().strip('"').strip("'")
API_ID = int(API_ID_RAW) if API_ID_RAW.isdigit() else 0

SESSION_NAME = os.getenv("TELEGRAM_SESSION_PATH", "mapping_userbot")
if SESSION_NAME.endswith(".session"):
    SESSION_NAME = SESSION_NAME[:-8]


def print_qr(url: str):
    print("\nScan this QR code in Telegram:")
    print("Telegram -> Settings -> Devices -> Link Desktop Device\n")
    qr_img = qrcode.QRCode(border=1)
    qr_img.add_data(url)
    qr_img.make(fit=True)
    for row in qr_img.get_matrix():
        print("".join("██" if cell else "  " for cell in row))


async def prompt_2fa(client: TelegramClient):
    while True:
        try:
            pw = os.getenv("TELEGRAM_2FA_PASSWORD")
            if not pw:
                try:
                    pw = getpass.getpass("\nEnter your Telegram 2FA Cloud Password (input hidden): ")
                except Exception:
                    pw = ""
                if not pw:
                    pw = input("\nEnter your Telegram 2FA Cloud Password: ").strip()
            await client.sign_in(password=pw)
            return
        except PasswordHashInvalidError:
            print("Invalid 2FA password, please try again.")
            os.environ.pop("TELEGRAM_2FA_PASSWORD", None)


async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        qr = await client.qr_login()
        while True:
            print_qr(qr.url)
            try:
                await qr.wait(timeout=30)
                break
            except SessionPasswordNeededError:
                print("\nQR code scanned! Two-Step Verification (2FA) password is required.")
                await prompt_2fa(client)
                break
            except asyncio.TimeoutError:
                print("\nQR code expired, refreshing QR code...")
                await qr.recreate()

    me = await client.get_me()
    print(f"\nLogged in successfully as {me.first_name} (@{getattr(me, 'username', '')}, ID: {me.id})")
    print(f"Session saved to: {os.path.abspath(SESSION_NAME + '.session')}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
