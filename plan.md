1. **Add the footprint vector layer in `static/js/map-core.js`:**
   - Define global variables `currentCacheBuster` and `currentSentinelFeatures`.
   - Uncomment or configure `layers.footprintLayer` using `L.geoJSON` with specific styling and `interactive: false` to allow clicks through to the unified popup.

2. **Add metadata sync on map pan in `static/js/map-layers.js`:**
   - Create `syncSentinelMetadata` function.
   - Attach it to `map.on('moveend')` and `layers.sentinelLayer.on('add')`.
   - The function should check zoom and Sentinel layer visibility. If conditions are met, hit `/api/sentinel-metadata` to update `currentSentinelFeatures`, update `footprintLayer`, and update the `currentCacheBuster` and `sentinelLayer` URL to break Cloudflare cache if necessary.

3. **Update unified popup fix in `static/js/map-layers.js`:**
   - Remove the existing `fetch(getFeatureInfoUrl(...))` WMS call.
   - Replace it with Turf.js local intersection logic using `turf.booleanPointInPolygon` against `currentSentinelFeatures`.
   - Format STAC properties (date and cloud cover) and display them in the popup.

4. **Add "Sentinel 2 Vector" to "Live Data Layers" in `static/index.html`:**
   - Insert a new layer toggle for the footprint layer in the control center, under the "Live Data Layers" section, right above NASA FIRMS data.
   - Also add event listeners in `map-layers.js` or `index.html` to toggle `layers.footprintLayer` via this checkbox.

5. **Pre-commit step**:
   - Run verification and Playwright visual checks.
