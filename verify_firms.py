from playwright.sync_api import sync_playwright

def test_firms():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:8000")

        # Click the NASA FIRMS toggle
        toggle = page.get_by_text("Load VIIRS Hybrid Layer")
        toggle.click()

        # Zoom in past ZOOM_THRESHOLD (8)
        # Default zoom is 6, we need to zoom in a few times.
        # We can just double click the map a few times or use wheel

        # We can evaluate js to set zoom
        page.evaluate("map.setZoom(9)")

        # Wait for the status element to appear and become visible
        status = page.locator("#firmsStatus")
        status.wait_for(state="visible")

        page.wait_for_timeout(5000)

        page.screenshot(path="verification_zoomed.png")

        browser.close()

if __name__ == "__main__":
    test_firms()