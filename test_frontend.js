const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Go to the local app
  await page.goto('http://127.0.0.1:3000');

  // Wait for the map to load
  await page.waitForTimeout(2000);

  // Toggle the hamburger menu to show the UI
  await page.click('.hamburger-btn');

  // Wait for the animation
  await page.waitForTimeout(500);

  // Find "Live Data Layers" and expand it if it's collapsed
  const liveDataHeaders = await page.$$('.section-header');
  for (let header of liveDataHeaders) {
    const text = await header.innerText();
    if (text.includes('Live Data Layers')) {
      await header.click();
      break;
    }
  }

  // Check the Sentinel-2 footprint toggle
  await page.waitForSelector('#toggleSentinelFootprint', {state: 'visible'});

  // Take a screenshot of the toggle panel
  await page.screenshot({ path: 'test_panel.png' });

  console.log('Test complete. Screenshot saved as test_panel.png');
  await browser.close();
})();
