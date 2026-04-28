from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Listen for console events
        page.on("console", lambda msg: print(f"Browser console: {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser error: {err}"))

        page.goto("http://localhost:3000/")

        # Wait for map to load
        page.wait_for_selector('.leaflet-container')
        time.sleep(3) # Wait for initial layers

        print("Clicking map...")
        page.mouse.click(800, 300)
        time.sleep(4) # wait for popup

        # Take screenshot
        page.screenshot(path="popup_test_3.png")

        browser.close()

if __name__ == '__main__':
    run()
