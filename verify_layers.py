from playwright.sync_api import sync_playwright

def test_layer_ordering():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the local server
        page.goto("http://localhost:8000")

        # Wait for the API to load the layers
        page.wait_for_selector(".layer-item", state="attached")
        page.wait_for_timeout(2000)

        # Make the layers visible explicitly by removing display: none just for the screenshot
        page.evaluate('''() => {
            document.querySelectorAll('#frontlineLayerList .layer-item').forEach(el => {
                el.style.display = 'flex';
            });
        }''')

        panel = page.locator(".control-panel")
        panel.screenshot(path="/home/jules/verification/verification_panel_3.png")

        browser.close()

if __name__ == "__main__":
    test_layer_ordering()
