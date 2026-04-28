import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to your app
        await page.goto('http://localhost:3000')

        # Wait for control panel or a recognizable element
        await page.wait_for_selector('.hamburger-btn', state='visible')

        # Open control panel
        await page.click('.hamburger-btn')

        # Wait a bit for transition
        await page.wait_for_timeout(1000)

        # Open Live Data Layers section
        await page.click('text=Live Data Layers')

        # Wait for transition
        await page.wait_for_timeout(500)

        # Click on firmsStyleMode dropdown to open it
        await page.click('#firmsStyleMode')

        # Wait a bit for it to open
        await page.wait_for_timeout(500)

        # Take screenshot of open dropdown
        await page.screenshot(path='firms_dropdown.png')

        await browser.close()

asyncio.run(main())
