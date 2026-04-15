from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto('http://127.0.0.1:3000')
    page.wait_for_timeout(5000)

    # Check if we can see the minimap container
    page.screenshot(path="minimap_screenshot.png")

    browser.close()
