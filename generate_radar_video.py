import asyncio
import argparse
from pathlib import Path
from playwright.async_api import async_playwright
import os

async def generate_video(output_filename: str):
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    final_output = output_dir / output_filename

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1280,720"])
        # Provide record_video_dir to enable recording
        context = await browser.new_context(
            record_video_dir=str(output_dir),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )

        page = await context.new_page()
        print("Navigating to radar replay...")
        # wait_until="networkidle" to make sure map/tiles load mostly
        await page.goto("http://127.0.0.1:8000/?radar_replay=1&hide_ui=1", wait_until="networkidle")

        print("Waiting for replay to finish...")
        try:
            # Wait until the radarReplayFinished variable is true in the browser context
            await page.wait_for_function("window.radarReplayFinished === true", timeout=90000)
            # Give it a second extra to settle
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Error waiting for replay to finish: {e}")

        # Close the page and context to finalize the video file
        video_path = await page.video.path()
        await context.close()
        await browser.close()

        print(f"Video saved temporarily at: {video_path}")

        # Rename to the requested filename
        if os.path.exists(video_path):
            os.rename(video_path, final_output)
            print(f"Renamed to: {final_output}")
        else:
            print("Failed to find the recorded video file.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="radar_replay.webm", help="Output filename in data directory")
    args = parser.parse_args()

    asyncio.run(generate_video(args.output))
