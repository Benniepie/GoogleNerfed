from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:3000/")

        # Wait for map to load
        page.wait_for_selector('.leaflet-container')
        time.sleep(3) # Wait for initial layers

        # Click on the map in Ukraine center
        page.mouse.click(400, 300)
        time.sleep(2) # wait for popup

        # Wait for geocoding to resolve potentially
        time.sleep(2)

        # Take screenshot
        page.screenshot(path="popup_test.png")

        browser.close()

if __name__ == '__main__':
    run()
