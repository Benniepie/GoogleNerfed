import asyncio
import argparse
from pathlib import Path
from playwright.async_api import async_playwright
import os

async def generate_video(output_filename: str, basemap: str):
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    final_output = output_dir / output_filename

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1920,1080"])
        # Provide record_video_dir to enable recording
        context = await browser.new_context(
            record_video_dir=str(output_dir),
            record_video_size={"width": 1920, "height": 1080},
            viewport={"width": 1920, "height": 1080}
        )

        # PASS 1: Setup - load page without UI, get initial view bounds
        page1 = await context.new_page()
        print("Running setup pass to determine map view...")
        await page1.goto(f"http://127.0.0.1:8000/?radar_replay=1&hide_ui=1&setup_only=1&basemap={basemap}", wait_until="networkidle")

        lat, lng, zoom = 54.0, 38.0, 5 # default fallback
        try:
            await page1.wait_for_function("window.radarSetupDone === true", timeout=60000)
            await asyncio.sleep(2) # Give Leaflet time to finish animations
            center = await page1.evaluate("map.getCenter()")
            zoom = await page1.evaluate("map.getZoom()")
            lat = center['lat']
            lng = center['lng']
            print(f"Setup complete. Map view: lat={lat}, lng={lng}, zoom={zoom}")
        except Exception as e:
            print(f"Error determining initial setup: {e}")

        video1_path = await page1.video.path()
        await page1.close()

        # Cleanup setup video
        if video1_path and os.path.exists(video1_path):
            try:
                os.remove(video1_path)
            except Exception as e:
                print(f"Failed to remove temp setup video: {e}")

        # PASS 2: Record - map instantly initializes to bounds and uses cached tiles
        page2 = await context.new_page()
        print(f"Recording radar replay video with basemap '{basemap}'...")
        url = f"http://127.0.0.1:8000/?radar_replay=1&hide_ui=1&lat={lat}&lng={lng}&zoom={zoom}&basemap={basemap}"
        await page2.goto(url)
        # Allow 2 seconds after page load for initial tile renders and any small adjustments before recording starts
        await asyncio.sleep(2)

        print("Waiting for replay to finish...")
        try:
            # Wait until the radarReplayFinished variable is true in the browser context
            await page2.wait_for_function("window.radarReplayFinished === true", timeout=90000)
            # Give it a second extra to settle
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Error waiting for replay to finish: {e}")

        # Close the page and context to finalize the video file
        video2_path = await page2.video.path()
        await context.close()
        await browser.close()

        print(f"Video saved temporarily at: {video2_path}")

        # Rename to the requested filename
        if video2_path and os.path.exists(video2_path):
            os.rename(video2_path, final_output)
            print(f"Renamed to: {final_output}")
        else:
            print("Failed to find the recorded video file.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="radar_replay.webm", help="Output filename in data directory")
    parser.add_argument("--basemap", default="dark", help="Basemap identifier to use")
    args = parser.parse_args()

    asyncio.run(generate_video(args.output, args.basemap))
