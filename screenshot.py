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

        # Take a screenshot
        await page.screenshot(path='control_panel.png')

        # Select s2latest radio button
        await page.click('input[value="s2latest"]')

        # Wait for text to update
        await page.wait_for_timeout(500)

        # Take screenshot of sentinel status text
        await page.screenshot(path='s2latest.png')

        await browser.close()

asyncio.run(main())
