import asyncio
import base64
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Capture console messages
        page.on("console", lambda msg: print(f"Browser console: {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser error: {err}"))

        auth_header = base64.b64encode(b"admin:admin").decode('utf-8')
        await page.set_extra_http_headers({"Authorization": f"Basic {auth_header}"})

        await page.goto("http://localhost:8000/admin")

        await page.wait_for_timeout(2000)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
