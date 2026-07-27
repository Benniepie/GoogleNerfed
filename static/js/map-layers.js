const activeKMLGeoJSON = {};

window.populateOverrideName = function(encodedName) {
    const el = document.getElementById('overrideLocationName');
    if (!el) return;

    // Decode the safely encoded name
    const name = decodeURIComponent(encodedName);
    el.value = name;

    // Attempt to open Map Admin and Live Data Layers Admin sections if they are closed
    const allHeaders = document.querySelectorAll('.section-header');
    allHeaders.forEach(h => {
        const text = h.innerText.trim();
        if (text.includes('Map Admin') || text.includes('Live Data Layers Admin')) {
            const content = h.nextElementSibling;
            if (content && content.classList.contains('collapsed')) {
                // simulate toggle by calling toggleSection directly
                if (typeof window.toggleSection === 'function') {
                    window.toggleSection(h);
                } else if (typeof toggleSection === 'function') {
                    toggleSection(h);
                } else {
                    h.click(); // fallback
                }
            }
        }
    });

    // scroll into view
    setTimeout(() => {
        el.scrollIntoView({behavior: 'smooth', block: 'center'});
        // visually highlight it
        el.style.backgroundColor = 'rgba(16, 185, 129, 0.3)';
        setTimeout(() => el.style.backgroundColor = 'rgba(0,0,0,0.5)', 1000);
    }, 300); // small delay to let toggles finish
};


        // 3. Fetch and Render Layers
        async function loadLayers() {
            try {
                const response = await fetch('/api/layers');
                const data = await response.json();

                const frontlineListEl = document.getElementById('frontlineLayerList');
                const staticListEl = document.getElementById('staticLayerList');

                // Save current checked states before clearing
                const previousCheckedStates = {};
                document.querySelectorAll('#frontlineLayerList input[type="checkbox"], #staticLayerList input[type="checkbox"]').forEach(chk => {
                    if (chk.id && chk.id.startsWith('chk_')) {
                        const filename = chk.id.substring(4);
                        previousCheckedStates[filename] = chk.checked;
                    }
                });

                frontlineListEl.innerHTML = '';
                staticListEl.innerHTML = '';

                if (data.layers.length === 0) {
                    frontlineListEl.innerHTML = '<em style="font-size: 0.9rem; color: #94a3b8;">No layers available.</em>';
                    staticListEl.innerHTML = '<em style="font-size: 0.9rem; color: #94a3b8;">No layers available.</em>';
                    return;
                }

                // Sort layers by user's saved order if it exists
                let sortedLayers = data.layers;
                if (appSettings.layerOrder && appSettings.layerOrder.length > 0) {
                    sortedLayers.sort((a, b) => {
                        const idxA = appSettings.layerOrder.indexOf(a);
                        const idxB = appSettings.layerOrder.indexOf(b);
                        if (idxA === -1 && idxB === -1) return 0;
                        if (idxA === -1) return 1; // Unordered items go to bottom
                        if (idxB === -1) return -1;
                        return idxA - idxB;
                    });
                }

                const frontlineLayers = [];
                const staticLayers = [];

                sortedLayers.forEach(filename => {
                    const isFrontline = filename.startsWith('AP Map') || filename.startsWith('AP Pins') || filename.startsWith('SM Map') || filename.startsWith('SM Pins');
                    if (isFrontline) {
                        frontlineLayers.push(filename);
                    } else {
                        staticLayers.push(filename);
                    }
                });

                const getFrontlineRank = (filename) => {
                    if (filename.startsWith('AP Pins')) return 1;
                    if (filename.startsWith('SM Pins')) return 2;
                    if (filename.startsWith('AP Map')) return 3;
                    if (filename.startsWith('SM Map')) return 4;
                    return 5;
                };

                frontlineLayers.sort((a, b) => {
                    const rankA = getFrontlineRank(a);
                    const rankB = getFrontlineRank(b);
                    if (rankA !== rankB) return rankA - rankB;
                    // within same rank, sort by date descending
                    return b.localeCompare(a);
                });

                const finalSortedLayers = [...frontlineLayers, ...staticLayers];

                let latestDate = null;
                frontlineLayers.forEach(filename => {
                    const d = extractDateFromFilename(filename);
                    if (d && (!latestDate || d > latestDate)) {
                        latestDate = d;
                    }
                });

                for (const filename of finalSortedLayers) {
                    const isFrontline = filename.startsWith('AP Map') || filename.startsWith('AP Pins') || filename.startsWith('SM Map') || filename.startsWith('SM Pins');

                    const item = document.createElement('div');
                    item.className = 'layer-item';
                    item.dataset.filename = filename;

                    // Only allow drag and drop for Static Data Layers
                    if (!isFrontline) {
                        if (window.location.pathname === '/admin') {
                            item.draggable = true;

                            // Drag and Drop Events
                            item.addEventListener('dragstart', (e) => {
                                item.classList.add('dragging');
                                e.dataTransfer.setData('text/plain', filename);
                            });

                            item.addEventListener('dragend', () => {
                                item.classList.remove('dragging');
                                document.querySelectorAll('.layer-item').forEach(el => el.classList.remove('drag-over'));
                                saveLayerOrder(); // Save new order to backend
                            });

                            item.addEventListener('dragover', (e) => {
                                e.preventDefault(); // Necessary to allow dropping
                                item.classList.add('drag-over');
                            });

                            item.addEventListener('dragleave', () => {
                                item.classList.remove('drag-over');
                            });

                            item.addEventListener('drop', (e) => {
                                e.preventDefault();
                                item.classList.remove('drag-over');
                                const draggingFile = e.dataTransfer.getData('text/plain');
                                if (draggingFile === filename) return;

                                const draggingEl = document.querySelector(`.layer-item[data-filename="${draggingFile}"]`);
                                if (!draggingEl) return;

                                const layerList = document.getElementById('staticLayerList');

                                // Determine whether to insert before or after
                                const allItems = [...layerList.querySelectorAll('.layer-item')];
                                const dropIdx = allItems.indexOf(item);
                                const dragIdx = allItems.indexOf(draggingEl);

                                if (dragIdx < dropIdx) {
                                    item.after(draggingEl);
                                } else {
                                    item.before(draggingEl);
                                }
                            });
                        }
                    }

                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.id = 'chk_' + filename;
                    if (previousCheckedStates[filename] !== undefined) {
                        checkbox.checked = previousCheckedStates[filename];
                    } else {
                        if (isFrontline) {
                            checkbox.checked = true;
                        } else {
                            checkbox.checked = false;
                        }
                    }

                    const label = document.createElement('label');
                    label.htmlFor = 'chk_' + filename;
                    label.textContent = filename;

                    item.appendChild(checkbox);
                    item.appendChild(label);

                    if (window.location.pathname === '/admin') {
                        const actionsDiv = document.createElement('div');
                        actionsDiv.className = 'layer-actions';

                        const styleBtn = document.createElement('button');
                        styleBtn.className = 'icon-btn';
                        styleBtn.innerHTML = '🎨';
                        styleBtn.title = 'Change Colour';
                        styleBtn.onclick = () => openColorPicker(filename);

                        const deleteBtn = document.createElement('button');
                        deleteBtn.className = 'icon-btn delete';
                        deleteBtn.innerHTML = '🗑️';
                        deleteBtn.title = 'Delete Layer';
                        deleteBtn.onclick = () => deleteLayer(filename);

                        actionsDiv.appendChild(styleBtn);
                        actionsDiv.appendChild(deleteBtn);
                        item.appendChild(actionsDiv);
                    }
                    // ------------------------
                    if (isFrontline) {
                        frontlineListEl.appendChild(item);
                        // Initially hide the layer item until the timeline sorts it out
                        item.style.display = 'none';
                    } else {
                        staticListEl.appendChild(item);
                        // Static items are always visible
                        item.style.display = 'flex';
                    }

                    // Load KML
                    if (!activeLayers[filename]) {
                        if (checkbox.checked) {
                            if (!isFrontline) {
                                await fetchAndAddKML(filename);
                            } else {
                                const layerDate = extractDateFromFilename(filename);
                                if (layerDate === latestDate) {
                                    await fetchAndAddKML(filename);
                                }
                            }
                        }
                    } else {
                        // Ensure map matches restored checkbox state
                        if (checkbox.checked) {
                            if (!isFrontline || extractDateFromFilename(filename) === document.getElementById('currentDateDisplay').textContent) {
                                if (!map.hasLayer(activeLayers[filename])) map.addLayer(activeLayers[filename]);
                            }
                        } else {
                            if (map.hasLayer(activeLayers[filename])) map.removeLayer(activeLayers[filename]);
                        }
                    }

                    // Toggle visibility
                    checkbox.addEventListener('change', async (e) => {
                        const isChecked = e.target.checked;

                        // If it's a frontline layer, toggle all related dates to match
                        if (isFrontline) {
                            let prefix = '';
                            if (filename.startsWith('AP Map')) prefix = 'AP Map';
                            else if (filename.startsWith('AP Pins')) prefix = 'AP Pins';
                            else if (filename.startsWith('SM Map')) prefix = 'SM Map';
                            else if (filename.startsWith('SM Pins')) prefix = 'SM Pins';

                            if (prefix) {
                                // Iterate over all layer items, not just loaded activeLayers
                                document.querySelectorAll('#frontlineLayerList .layer-item').forEach(item => {
                                    const fn = item.dataset.filename;
                                    if (fn.startsWith(prefix)) {
                                        const otherChk = document.getElementById('chk_' + fn);
                                        if (otherChk && otherChk !== checkbox) {
                                            otherChk.checked = isChecked;
                                        }

                                        // Update map visibility ONLY if this layer is meant for the CURRENT selected date
                                        const layerDate = extractDateFromFilename(fn);
                                        const currentDisplayDate = document.getElementById('currentDateDisplay').textContent;
                                        if (!layerDate || layerDate === currentDisplayDate) {
                                            if (isChecked) {
                                                if (activeLayers[fn] && !map.hasLayer(activeLayers[fn])) {
                                                    map.addLayer(activeLayers[fn]);
                                                } else if (!activeLayers[fn]) {
                                                    fetchAndAddKML(fn);
                                                }
                                            } else if (!isChecked && activeLayers[fn] && map.hasLayer(activeLayers[fn])) {
                                                map.removeLayer(activeLayers[fn]);
                                            }
                                        }
                                    }
                                });
                            }
                        }

                        // Handle current target specifically
                        if (!isFrontline) {
                            if (isChecked) {
                                if (!activeLayers[filename]) {
                                    await fetchAndAddKML(filename);
                                } else {
                                    map.addLayer(activeLayers[filename]);
                                }
                            } else {
                                if (activeLayers[filename] && map.hasLayer(activeLayers[filename])) {
                                    map.removeLayer(activeLayers[filename]);
                                }
                            }
                        }
                        reorderActiveLayers();
                    });
                }
                updateTimeline();
                reorderActiveLayers();
                // Force dispatch the event so the map actually updates to only show the latest
                const slider = document.getElementById('timelineSlider');
                slider.dispatchEvent(new Event('input'));
                document.getElementById('timelineSlider').dispatchEvent(new Event('input'));
            } catch (err) {
                console.error("Failed to load layers:", err);
            }
        }

        async function fetchAndAddKML(filename) {
            try {
                const response = await fetch(`/data/${filename}?t=${new Date().getTime()}`);
                const kmlText = await response.text();

                const parser = new DOMParser();
                const xmlDoc = parser.parseFromString(kmlText, "text/xml");
                const geoJsonData = toGeoJSON.kml(xmlDoc);

                const styleConfig = layerStyles[filename] || { type: 'single', color: '#3b82f6', opacity: 0.5 }; // Default style

                function getFeatureStyle(feature) {
                    if (styleConfig.type === 'grouped' && styleConfig.styles) {
                        const name = feature.properties ? feature.properties.name : null;
                        if (name && styleConfig.styles[name]) {
                            return styleConfig.styles[name];
                        }
                    }
                    return { color: styleConfig.color || '#3b82f6', opacity: styleConfig.opacity !== undefined ? styleConfig.opacity : 0.5 };
                }

                const layer = L.geoJSON(geoJsonData, {
                    interactive: false, // CRITICAL: Lets clicks pass through to the map
                    style: function (feature) {
                        const style = getFeatureStyle(feature);
                        return { color: style.color, weight: 2, fillOpacity: style.opacity };
                    },
                    pointToLayer: function (feature, latlng) {
                        const style = getFeatureStyle(feature);
                        return L.circle(latlng, {
                            interactive: false, // Let clicks pass through points too
                            radius: 50,
                            fillColor: style.color,
                            color: '#ffffff',
                            weight: 1,
                            opacity: 1,
                            fillOpacity: style.opacity
                        });
                    }
                    // REMOVED onEachFeature bindPopup logic entirely
                });

                // Store the raw GeoJSON for our master click event
                activeKMLGeoJSON[filename] = geoJsonData;

                if (activeLayers[filename]) {
                    map.removeLayer(activeLayers[filename]);
                }

                const chk = document.getElementById('chk_' + filename);
                const isFrontlineLayer = filename.startsWith('AP Map') || filename.startsWith('AP Pins') || filename.startsWith('SM Map') || filename.startsWith('SM Pins');
                const layerDate = extractDateFromFilename(filename);

                if (!chk || chk.checked) {
                    let shouldAdd = true;
                    if (isFrontlineLayer) {
                        const selectedDate = document.getElementById('currentDateDisplay').textContent;
                        if (selectedDate && layerDate && layerDate !== selectedDate) {
                            shouldAdd = false; // It's preloaded, don't show yet
                        }
                    }
                    if (shouldAdd) {
                        layer.addTo(map);
                    }
                }
                activeLayers[filename] = layer;

            } catch (err) {
                console.error(`Error processing KML ${filename}:`, err);
            }
        }

        async function fetchAndRenderFirmsBBox() {

            const statusEl = document.getElementById('firmsStatus');



            statusEl.style.display = 'block';
            statusEl.textContent = 'Fetching vector data (SNPP, NOAA-20 & NOAA-21)...';
            statusEl.style.color = '#94a3b8';

            // Calculate Bounding Box
            const bounds = map.getBounds();
            const bbox = `${bounds.getWest() - 0.5},${bounds.getSouth() - 0.5},${bounds.getEast() + 0.5},${bounds.getNorth() + 0.5}`;



            try {
                // --- THE CHANGE IS HERE ---
                // Fire ONE request to the new combined backend endpoint
                const response = await fetch(`/api/firms/combined/${bbox}`);
        
                if (!response.ok) {
                    throw new Error("API limits reached or invalid area.");
                }
        
                // If the backend returns 204 No Content (meaning no fires or NASA failed)
                if (response.status === 204) {
                    currentFirmsData = [];
                    firmsVectorGroup.clearLayers();
                    statusEl.textContent = 'No thermal anomalies in this specific view.';
                    statusEl.style.color = '#94a3b8';
                    return;
                }
        
                const csvText = await response.text();
                const rows = csvText.split('\n').filter(row => row.trim() !== '');
        
                if (rows.length <= 1) { // Only header, or empty
                    currentFirmsData = [];
                    firmsVectorGroup.clearLayers();
                    statusEl.textContent = 'No thermal anomalies in this specific view.';
                    statusEl.style.color = '#94a3b8';
                    return;
                }
        
                // Parse our newly combined massive dataset
                const headers = rows.shift().split(','); // Extract header row once
        
                currentFirmsData = rows.map(row => {
                    const values = row.split(',');
                    let data = {};
                    headers.forEach((header, index) => { data[header] = values[index]; });
                    return data;
                });
        
                // Sort by date/time ascending so older fires render first, and newer ones render on top
                currentFirmsData.sort((a, b) => {
                    const timeA = a.acq_date + "T" + a.acq_time.padStart(4, '0');
                    const timeB = b.acq_date + "T" + b.acq_time.padStart(4, '0');
                    return timeA.localeCompare(timeB);
                });
        
                renderFirmsVectorData();
        
                statusEl.textContent = `Loaded ${currentFirmsData.length} active fires from 3 satellites.`;
                statusEl.style.color = '#22c55e';
        
            } catch (error) {
                console.error("FIRMS Error:", error);
                statusEl.textContent = 'Error fetching vector data.';
                statusEl.style.color = '#ef4444';
            }
        }

        function renderFirmsVectorData() {
            firmsVectorGroup.clearLayers();
            const styleMode = document.getElementById('firmsStyleMode').value;
            const now = new Date();

            currentFirmsData.forEach(fire => {
                if (!fire.latitude || !fire.longitude) return;

                const timeStr = fire.acq_time.padStart(4, '0');
                const isoString = `${fire.acq_date}T${timeStr.substring(0,2)}:${timeStr.substring(2,4)}:00Z`;
                const fireTime = new Date(isoString);
                const ageHours = (now - fireTime) / (1000 * 60 * 60);

                let fillColor = '#ef4444';
                let fillOpacity = 0.6;

                if (styleMode === 'time') {
                    if (ageHours <= 3) { fillColor = '#7f1d1d'; fillOpacity = 0.9; }
                    else if (ageHours <= 6) { fillColor = '#dc2626'; fillOpacity = 0.8; }
                    else if (ageHours <= 12) { fillColor = '#ea580c'; fillOpacity = 0.7; }
                    else { fillColor = '#eab308'; fillOpacity = 0.5; }
                }

                const fireCircle = L.circle([parseFloat(fire.latitude), parseFloat(fire.longitude)], {
                    color: fillColor,
                    weight: 1,
                    fillColor: fillColor,
                    fillOpacity: fillOpacity,
                    radius: 187.5 // 375m VIIRS footprint
                });

                // REMOVED fireCircle.bindPopup(...) entirely

                firmsVectorGroup.addLayer(fireCircle);
            });
        }

        // --- Core Map Event Listeners for Hybrid Logic ---
        function updateFirmsDisplay() {
            if (!isFirmsActive) return;

            const currentZoom = map.getZoom();

            if (currentZoom < ZOOM_THRESHOLD) {
                // Zoomed Out: Show Raster, Hide Vector
                if (!map.hasLayer(nasaRasterLayer)) map.addLayer(nasaRasterLayer);
                if (map.hasLayer(firmsVectorGroup)) map.removeLayer(firmsVectorGroup);
                document.getElementById('firmsStatus').textContent = 'Zoom in for vector details...';
                document.getElementById('firmsStatus').style.color = '#94a3b8';
            } else {
                // Zoomed In: Show Vector, Hide Raster, Fetch Data
                if (map.hasLayer(nasaRasterLayer)) map.removeLayer(nasaRasterLayer);
                if (!map.hasLayer(firmsVectorGroup)) map.addLayer(firmsVectorGroup);
                fetchAndRenderFirmsBBox();
            }
        }





        // --- LIVE DATA: TELEGRAM RADAR RUSSIA ---
        let isRadarRussiaActive = false;
        let radarRussiaPollInterval = null;
        let radarRussiaLayerGroup = L.layerGroup();
        let seenRadarAlertIds = new Set();
        let radarInitialLoad = true;
        let radarAudioContext = null;
        let radarLastFetchTime = null;
        let radarAllFeatures = []; // Maintain the full list of active features locally
        window.radarReplayTime = null;

        window.forceRadarRefresh = async function() {
            if (isRadarRussiaActive) {
                radarLastFetchTime = null;
                radarInitialLoad = true;
                seenRadarAlertIds.clear();
                radarAllFeatures = [];
                radarRussiaLayerGroup.clearLayers();
                await fetchRadarRussiaData();
            }
        };

        function playBeep() {
            try {
                if (!radarAudioContext) {
                    radarAudioContext = new (window.AudioContext || window.webkitAudioContext)();
                }
                const oscillator = radarAudioContext.createOscillator();
                const gainNode = radarAudioContext.createGain();

                oscillator.type = 'sine';
                oscillator.frequency.setValueAtTime(880, radarAudioContext.currentTime); // A5

                gainNode.gain.setValueAtTime(0, radarAudioContext.currentTime);
                gainNode.gain.linearRampToValueAtTime(0.5, radarAudioContext.currentTime + 0.05);
                gainNode.gain.exponentialRampToValueAtTime(0.001, radarAudioContext.currentTime + 0.5);

                oscillator.connect(gainNode);
                gainNode.connect(radarAudioContext.destination);

                oscillator.start();
                oscillator.stop(radarAudioContext.currentTime + 0.5);
            } catch (e) {
                console.error("Audio error", e);
            }
        }

        async function fetchRadarRussiaData() {
            if (!isRadarRussiaActive) return;

            const statusEl = document.getElementById('radarRussiaStatus');
            statusEl.textContent = 'Fetching latest alerts...';

            try {
                let url = '/api/radar-russia';
                if (radarLastFetchTime && !radarInitialLoad) {
                    url += `?since=${encodeURIComponent(radarLastFetchTime)}`;
                }

                const res = await fetch(url);
                if (!res.ok) throw new Error("API error");

                const data = await res.json();

                let newAlertsFound = false;
                let maxTime = radarLastFetchTime;

                data.features.forEach(f => {
                    const id = f.properties.id;
                    const alertTime = f.properties.time;
                    if (alertTime) {
                        if (!maxTime || new Date(alertTime) > new Date(maxTime)) {
                            maxTime = alertTime;
                        }
                    }

                    if (id) {
                        if (!seenRadarAlertIds.has(id)) {
                            seenRadarAlertIds.add(id);
                            radarAllFeatures.push(f);
                            if (!radarInitialLoad) {
                                newAlertsFound = true;
                            }
                        } else {
                            // Update existing feature to ensure overrides propagate
                            const idx = radarAllFeatures.findIndex(existing => existing.properties.id === id);
                            if (idx !== -1) {
                                radarAllFeatures[idx] = f;
                            }
                        }
                    }
                });

                if (newAlertsFound && document.getElementById('radarRussiaAudioToggle') && document.getElementById('radarRussiaAudioToggle').checked) {
                    playBeep();
                }

                radarInitialLoad = false;
                radarLastFetchTime = maxTime; // Update with the most recent alert time received

                renderRadarRussiaData();

                statusEl.textContent = `Tracking ${radarAllFeatures.length} locations.`;
                statusEl.style.color = '#22c55e';
            } catch (e) {
                console.error("Radar Russia API error:", e);
                statusEl.textContent = 'Error fetching data.';
                statusEl.style.color = '#ef4444';
            }
        }

        function renderRadarRussiaData() {
            radarRussiaLayerGroup.clearLayers();
            const now = window.radarReplayTime || new Date();
            const realNow = new Date();

            // First prune old features from the master list
            radarAllFeatures = radarAllFeatures.filter(f => {
                const alertTime = new Date(f.properties.time);
                // Prune based on real time
                const ageHours = (realNow - alertTime) / (1000 * 60 * 60);
                return ageHours <= 24;
            });

            // Sort features newest to oldest (for popups)
            radarAllFeatures.sort((a, b) => new Date(b.properties.time) - new Date(a.properties.time));

            // Filter out features in the future when replaying
            const currentFeatures = radarAllFeatures.filter(f => new Date(f.properties.time) <= now);

            // Build intersection data (all valid features)
            activeKMLGeoJSON['RadarRussia'] = {
                type: "FeatureCollection",
                features: currentFeatures
            };

            // The user requested stacked opacities for Red/Orange/Yellow (active alerts) to show intensity,
            // but older Green (clear) or Grey (stale) alerts should not render if there's a newer alert,
            // as it causes muddy color mixing. And if the latest is clear/stale, we only render it once (no stacking).

            const latestStatePerLoc = new Map();
            currentFeatures.forEach(feature => {
                const locName = feature.properties.name;
                // Since radarAllFeatures is sorted newest to oldest, the first one we see is the newest
                if (!latestStatePerLoc.has(locName)) {
                    latestStatePerLoc.set(locName, feature);
                }
            });

            const locationCentroids = new Map();
            const locationAreas = new Map();
            latestStatePerLoc.forEach((feature, locName) => {
                try {
                    locationCentroids.set(locName, turf.centroid(feature));
                } catch (e) {
                    if (feature.geometry && feature.geometry.type === 'Point') {
                        locationCentroids.set(locName, turf.point(feature.geometry.coordinates));
                    }
                }
                try {
                    locationAreas.set(locName, turf.area(feature));
                } catch (e) {
                    locationAreas.set(locName, 0);
                }
            });

            const effectiveLatestStatePerLoc = new Map();
            const parentRegions = new Map();

            locationCentroids.forEach((pt, locName) => {
                let effectiveFeature = latestStatePerLoc.get(locName);
                let maxTime = new Date(effectiveFeature.properties.time);
                let overridingParent = null;

                let locArea = locationAreas.get(locName) || 0;
                latestStatePerLoc.forEach((candidateFeature, candidateName) => {
                    let candArea = locationAreas.get(candidateName) || 0;
                    // Candidate must be significantly larger to be considered a parent (e.g. 20% larger)
                    if (candidateName !== locName && candArea > locArea * 1.2 && pt && candidateFeature.geometry && (candidateFeature.geometry.type === 'Polygon' || candidateFeature.geometry.type === 'MultiPolygon')) {
                        try {
                            if (turf.booleanPointInPolygon(pt, candidateFeature)) {
                                let candidateTime = new Date(candidateFeature.properties.time);
                                if (candidateTime > maxTime) {
                                    maxTime = candidateTime;
                                    effectiveFeature = candidateFeature;
                                    overridingParent = candidateFeature;
                                } else if (!overridingParent) {
                                    overridingParent = candidateFeature; // Keep track of parent even if it doesn't override time, for overlap checks
                                }
                            }
                        } catch(e) {}
                    }
                });
                effectiveLatestStatePerLoc.set(locName, effectiveFeature);
                parentRegions.set(locName, overridingParent);
            });

            // Count recent active alerts per location for opacity
            const recentAlertCounts = new Map();
            currentFeatures.forEach(feature => {
                const locName = feature.properties.name;
                const props = feature.properties;
                const ageMinutes = (now - new Date(props.time)) / (1000 * 60);
                if (props.status !== 'over' && ageMinutes <= 60 && ageMinutes >= 0) {
                    recentAlertCounts.set(locName, (recentAlertCounts.get(locName) || 0) + 1);
                }
            });

            // We only iterate over the *latest* feature for each location.
            // This prevents rendering multiple polygons for the same location.
            latestStatePerLoc.forEach((feature, locName) => {
                const latestFeature = effectiveLatestStatePerLoc.get(locName);
                const latestProps = latestFeature.properties;
                const latestAgeMinutes = (now - new Date(latestProps.time)) / (1000 * 60);

                const props = feature.properties;
                const ageSeconds = (now - new Date(props.time)) / 1000;

                const latestAgeHours = latestAgeMinutes / 60;

                let fillColor = '#ef4444'; // Red default
                let fillOpacity = 0.4; // Base opacity for red/orange/yellow
                let animationClass = '';
                let borderClass = '';
                let isGrey = false;

                if (latestProps.status === 'over') {
                    if (latestAgeHours > 1) {
                        fillColor = '#64748b'; // Darker grey
                        fillOpacity = 0.3;
                        isGrey = true;
                    } else {
                        fillColor = '#22c55e'; // Green
                        fillOpacity = 0.3;
                    }
                } else {
                    if (latestAgeMinutes <= 20) {
                        fillColor = '#ef4444'; // Red
                        animationClass = 'radar-pulse';
                    } else if (latestAgeMinutes <= 40) {
                        fillColor = '#f97316'; // Orange
                    } else if (latestAgeMinutes <= 60) {
                        fillColor = '#eab308'; // Yellow
                    } else {
                        fillColor = '#64748b'; // Darker grey
                        fillOpacity = 0.3;
                        isGrey = true;
                    }
                }

                // Calculate opacity based on count of recent alerts (for active colors)
                if (fillColor === '#ef4444' || fillColor === '#f97316' || fillColor === '#eab308') {
                    // Use effective feature's count because we inherited its state
                    const effectiveLocName = latestFeature.properties.name;
                    const count = recentAlertCounts.get(effectiveLocName) || 1;
                    fillOpacity = Math.min(0.8, 0.4 + ((count - 1) * 0.1)); // Max opacity 0.8
                }

                // Overlap check: If this feature is inside a larger feature that shares the same effective state,
                // set fillOpacity to 0 to prevent compounding the fill, but keep the border.
                const parentFeature = parentRegions.get(locName);
                if (parentFeature) {
                    const parentEffectiveFeature = effectiveLatestStatePerLoc.get(parentFeature.properties.name);
                    if (parentEffectiveFeature && parentEffectiveFeature === latestFeature) {
                        fillOpacity = 0.0;
                    }
                }

                // Add 60s flash for brand new alerts, using the location's true latest timestamp
                if (ageSeconds <= 60) {
                    borderClass = 'radar-flash-path';
                    animationClass += ' radar-flash-anim';
                }

                // Determine if this is a small polygon or has an emoji
                let isSmallOrPoint = feature.geometry.type === 'Point' || feature.geometry.type === 'MultiPoint';

                // Never render districts, regions, oblasts, republics as markers
                const rawName = feature.properties.raw_name ? feature.properties.raw_name.toLowerCase() : "";
                const enName = feature.properties.name ? feature.properties.name.toLowerCase() : "";
                const isRegionOrDistrict =
                    rawName.includes('область') || rawName.includes('край') ||
                    rawName.includes('республика') || rawName.includes('район') ||
                    rawName.includes('округ') || rawName.includes('область') || rawName.includes('район') || rawName.includes('край') || rawName.includes('республика') ||
                    enName.includes('oblast') || enName.includes('region') || enName.includes('district') ||
                    enName.includes('republic') || enName.includes('krai');

                if (isRegionOrDistrict) {
                    isSmallOrPoint = false; // Never make a region or district a map marker!
                } else if (!isSmallOrPoint && (feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon')) {
                    if (feature.properties.icon) {
                        isSmallOrPoint = true;
                    }
                }

                // For small polygons or emoji locations, we render a large point instead
                if (isSmallOrPoint || feature.geometry.type === 'Point' || feature.geometry.type === 'MultiPoint') {
                    let center = feature.geometry.type === 'Point' ? [feature.geometry.coordinates[1], feature.geometry.coordinates[0]] : null;
                    if (!center) {
                        const centroid = turf.centroid(feature);
                        center = [centroid.geometry.coordinates[1], centroid.geometry.coordinates[0]];
                    }

                    const iconHtml = feature.properties.icon || '';
                    let markerHtml = '';

                    if (iconHtml) {
                        markerHtml = `<div style="background:${fillColor}; width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; border:2px solid ${isGrey ? '#cbd5e1' : 'white'}; font-size:20px; box-shadow:0 0 10px rgba(0,0,0,0.5);">${iconHtml}</div>`;
                    } else {
                        // Clean circle for small cities (no ugly teardrop, no emoji)
                        markerHtml = `<div style="background:${fillColor}; width:20px; height:20px; border-radius:50%; display:flex; align-items:center; justify-content:center; border:2px solid ${isGrey ? '#cbd5e1' : 'white'}; box-shadow:0 0 10px rgba(0,0,0,0.5);"></div>`;
                    }

                    const customIcon = L.divIcon({
                        className: `radar-custom-icon ${animationClass}`,
                        html: markerHtml,
                        iconSize: iconHtml ? [30, 30] : [20, 20],
                        iconAnchor: iconHtml ? [15, 15] : [10, 10]
                    });

                    const markerLayer = L.marker(center, {icon: customIcon, interactive: false});
                    radarRussiaLayerGroup.addLayer(markerLayer);
                } else {
                    const layer = L.geoJSON(feature, {
                        interactive: false,
                        style: {
                            color: isGrey ? '#64748b' : fillColor,
                            weight: isGrey ? 2 : 2,
                            fillColor: fillColor,
                            fillOpacity: fillOpacity,
                            className: borderClass
                        }
                    });
                    radarRussiaLayerGroup.addLayer(layer);
                }
            });

            // Only add to map if active
            if (isRadarRussiaActive && !map.hasLayer(radarRussiaLayerGroup)) {
                radarRussiaLayerGroup.addTo(map);
            }
        }

        document.getElementById('radarRussiaToggle').addEventListener('change', (e) => {
            isRadarRussiaActive = e.target.checked;
            const statusEl = document.getElementById('radarRussiaStatus');
            const legendEl = document.getElementById('radarLegend');

            if (isRadarRussiaActive) {
                statusEl.style.display = 'block';
                if (legendEl) legendEl.style.display = 'block';
                // Fetch immediately, then every 60s
                fetchRadarRussiaData();
                radarRussiaPollInterval = setInterval(fetchRadarRussiaData, 60000);
            } else {
                statusEl.style.display = 'none';
                if (radarRussiaPollInterval) clearInterval(radarRussiaPollInterval);
                radarRussiaLayerGroup.clearLayers();
                if (radarRussiaLayerGroup && map.hasLayer(radarRussiaLayerGroup)) {
                    map.removeLayer(radarRussiaLayerGroup);
                }
                if (legendEl) legendEl.style.display = 'none';
            }
        });

        // --- RADAR REPLAY LOGIC ---
        window.startRadarReplay = async function() {
                        window.radarReplayFinished = false;
            window.radarReplayPaused = false;

            // Sync UI state
            const playPauseBtn = document.getElementById('replayPlayPauseBtn');
            if (playPauseBtn) playPauseBtn.innerHTML = '⏸️';

            const speedSelect = document.getElementById('replaySpeedSelect');
            if (speedSelect) {
                window.radarReplayDurationMs = parseInt(speedSelect.value) * 1000;
            }

            const cp = document.getElementById('controlPanel');
            if (cp) {
                cp.classList.remove('open');
                // Alse set style to none so it completely disappears if the class removal isn't enough

            }

            const replayParams = new URLSearchParams(window.location.search);
            const isVideoExport = replayParams.get('hide_ui') === '1';

            const controls = document.getElementById('replayControlsOverlay');
            if (controls && !isVideoExport) {
                controls.style.display = 'flex';
            }

            if (!isRadarRussiaActive) {
                document.getElementById('radarRussiaToggle').click();
            }

            // Wait for initial load to finish
            while (radarInitialLoad) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }

            if (radarAllFeatures.length === 0) {
                console.log("No features to replay.");
                window.radarReplayFinished = true;
                return;
            }

            const hasInitialView = replayParams.has('lat') && replayParams.has('lng') && replayParams.has('zoom');

            if (!hasInitialView) {
                // Calculate bounding box for all current features
                let fg = L.featureGroup();
                radarAllFeatures.forEach(f => {
                    if (f.geometry && f.geometry.coordinates) {
                        fg.addLayer(L.geoJSON(f));
                    }
                });
                if (fg.getLayers().length > 0) {
                    map.fitBounds(fg.getBounds(), {padding: [100, 100]});
                }
            }

            if (replayParams.get('setup_only') === '1') {
                window.radarSetupDone = true;
                return; // End early if only setting up bounds for video capture
            }

            const realNow = new Date();
            const startReplayTime = new Date(realNow.getTime() - 24 * 60 * 60 * 1000);
            window.radarReplayTime = startReplayTime;

            let lastFrameTime = performance.now();
            window.radarReplayStartTime = performance.now();
            window.radarReplayDurationMs = window.radarReplayDurationMs || 60000;

            const overlay = document.getElementById('replayOverlay');
            if (overlay) overlay.style.display = 'block';

            function animate(currentTime) {
                if (window.radarReplayFinished) return;

                if (!window.radarReplayPaused) {
                    let elapsed = currentTime - window.radarReplayStartTime;
                    let progress = elapsed / window.radarReplayDurationMs;

                    if (progress >= 1.0) {
                        progress = 1.0;
                    }

                    const timeWindowMs = 24 * 60 * 60 * 1000;
                    window.radarReplayTime = new Date(startReplayTime.getTime() + (progress * timeWindowMs));

                    // Update slider
                    const slider = document.getElementById('replayProgressSlider');
                    if (slider) {
                        slider.value = progress * 100;
                    }

                    if (progress >= 1.0) {
                        window.radarReplayTime = null;
                        renderRadarRussiaData();
                        window.radarReplayFinished = true;
                        if (overlay) overlay.style.display = 'none';
                        const controls = document.getElementById('replayControlsOverlay');
                        if (controls) controls.style.display = 'none';
                        const cp = document.getElementById('controlPanel');
                        if (cp) {
                            cp.style.display = '';
                        }
                        return;
                    }
                } else {
                    // if paused, shift the start time forward so we don't jump ahead on unpause
                    let dt = currentTime - lastFrameTime;
                    window.radarReplayStartTime += dt;
                }

                lastFrameTime = currentTime;

                // Calculate stats for overlay
                let redAlertsCount = 0;
                let totalAlertsCount = 0;

                // We use radarAllFeatures which are all features in the last 24 real hours.
                // Filter to what's happened up to simulated time.
                const currentFeatures = radarAllFeatures.filter(f => new Date(f.properties.time) <= window.radarReplayTime);

                // Track total locations alerted
                const alertedLocations = new Set();

                currentFeatures.forEach(feature => {
                    const locName = feature.properties.name;
                    alertedLocations.add(locName);

                    const ageMinutes = (window.radarReplayTime - new Date(feature.properties.time)) / (1000 * 60);
                    // A "red alert" is an active alert (not over) within the first 20 minutes
                    if (feature.properties.status !== 'over' && ageMinutes >= 0 && ageMinutes <= 20) {
                        redAlertsCount++;
                    }
                });

                totalAlertsCount = alertedLocations.size;

                // Update UI overlay if it exists
                if (overlay) {
                    // Format Date nicely
                    const timeStr = window.radarReplayTime.toLocaleString('en-GB', {
                        timeZone: 'UTC',
                        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                    }) + ' (UTC)';

                    overlay.innerHTML = `
                        <div style="font-size: 1.2rem; font-weight: bold; color: #93c5fd; margin-bottom: 5px;">${timeStr}</div>
                        <div style="display: flex; justify-content: space-around; font-size: 1.1rem; gap: 20px;">
                            <div><span style="color: #ef4444;">🔴</span> Active Red Alerts: <b>${redAlertsCount}</b></div>
                            <div><span style="color: #eab308;">📍</span> Total Locations: <b>${totalAlertsCount}</b></div>
                        </div>
                    `;
                }

                renderRadarRussiaData();
                requestAnimationFrame(animate);
            }

            requestAnimationFrame(animate);
        };

        // Autoplay logic for video generator
        window.addEventListener('load', () => {
            const params = new URLSearchParams(window.location.search);
            if (params.get('radar_replay') === '1') {
                if (params.get('hide_ui') === '1') {
                    document.getElementById('controlPanel').style.display = 'none';
                    const rco = document.getElementById('replayControlsOverlay');
                    if (rco) rco.style.display = 'none';
                    const lcc = document.querySelector('.leaflet-control-container');
                    if (lcc) lcc.style.display = 'none';
                    window.radarReplayDurationMs = 60000;
                }

                const hasInitialView = params.has('lat') && params.has('lng') && params.has('zoom');
                const isSetup = params.get('setup_only') === '1';

                let delayMs = 2000;
                if (isSetup) {
                    delayMs = 100;
                } else if (hasInitialView) {
                    delayMs = 15000; // Give basemap tiles time to load completely before starting replay
                }

                setTimeout(() => {
                    startRadarReplay();
                }, delayMs);
            }
        });


        // --- LIVE DATA: NASA FIRMS (Hybrid Raster/Vector) ---
        const ZOOM_THRESHOLD = 8; // Zoom level at which we switch from Raster to Vector
        let isFirmsActive = false;

        // 1. The Raster Layer (Grouped for all 3 satellites)
        const snppRaster = L.tileLayer.wms("https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi", {
            layers: 'VIIRS_SNPP_Thermal_Anomalies_375m_All',
            format: 'image/png', transparent: true, zIndex: 100
        });

        const noaa20Raster = L.tileLayer.wms("https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi", {
            layers: 'VIIRS_NOAA20_Thermal_Anomalies_375m_All',
            format: 'image/png', transparent: true, zIndex: 100
        });

        const noaa21Raster = L.tileLayer.wms("https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi", {
            layers: 'VIIRS_NOAA21_Thermal_Anomalies_375m_All',
            format: 'image/png', transparent: true, zIndex: 100
        });

        // Bundle them together so they toggle as a single layer
        const nasaRasterLayer = L.layerGroup([snppRaster, noaa20Raster, noaa21Raster]);

        // 2. The Vector Layer (for zoomed-in detailed views)
        let firmsVectorGroup = L.layerGroup();
        let currentFirmsData = [];


        // Listen for user panning and zooming
        map.on('moveend', updateFirmsDisplay);

        // Listen for the toggle switch
        document.getElementById('nasaFirmsToggle').addEventListener('change', (e) => {
            isFirmsActive = e.target.checked;
            const statusEl = document.getElementById('firmsStatus');

            if (isFirmsActive) {
                statusEl.style.display = 'block';
                updateFirmsDisplay();
            } else {
                map.removeLayer(nasaRasterLayer);
                map.removeLayer(firmsVectorGroup);
                statusEl.style.display = 'none';
            }
        });

        // Listen for dropdown styling changes
        document.getElementById('firmsStyleMode').addEventListener('change', (e) => {
            const timeKey = document.getElementById('firmsTimeKey');
            if (e.target.value === 'time') {
                timeKey.style.display = 'block';
            } else {
                timeKey.style.display = 'none';
            }
            if (isFirmsActive && map.getZoom() >= ZOOM_THRESHOLD) {
                renderFirmsVectorData();
            }
        });
        // --- Timeline & Automation Logic ---
        let availableDates = [];
        window.availableDates = availableDates;

        function extractDateFromFilename(filename) {
            // Looks for YYYY-MM-DD pattern
            const match = filename.match(/(\d{4}-\d{2}-\d{2})/);
            if (match) return match[1];

            // Looks for DD MM pattern
            const altMatch = filename.match(/(\d{2})[ _]?(\d{2})/);
            if (altMatch) return `2026-${altMatch[2]}-${altMatch[1]}`; // Default to 2026 per user

            return null;
        }

        function updateTimeline() {
            const datesSet = new Set();

            // Collect all dates from frontline items in the DOM
            document.querySelectorAll('#frontlineLayerList .layer-item').forEach(item => {
                const filename = item.dataset.filename;
                const d = extractDateFromFilename(filename);
                if (d) datesSet.add(d);
            });

            availableDates = Array.from(datesSet).sort();
            window.availableDates = availableDates;
            const slider = document.getElementById('timelineSlider');
            const display = document.getElementById('currentDateDisplay');
            const btnBack = document.getElementById('btnTimelineBack');
            const btnForward = document.getElementById('btnTimelineForward');
            const btnLatest = document.getElementById('btnTimelineLatest');

            if (availableDates.length > 0) {
                slider.disabled = false;
                if (btnBack) btnBack.disabled = false;
                if (btnForward) btnForward.disabled = false;
                if (btnLatest) btnLatest.disabled = false;
                slider.max = availableDates.length - 1;

                // If this is the very first time we're setting it, or if it was empty, default to latest.
                // Otherwise, preserve the current selected date index if it's still valid.
                let newIndex = slider.value;
                const currentDate = display.textContent;
                const foundIndex = availableDates.indexOf(currentDate);

                if (currentDate === 'Latest' || foundIndex === -1) {
                    newIndex = availableDates.length - 1;
                } else {
                    newIndex = foundIndex;
                }

                slider.value = newIndex;
                display.textContent = availableDates[newIndex];
            } else {
                slider.disabled = true;
                if (btnBack) btnBack.disabled = true;
                if (btnForward) btnForward.disabled = true;
                if (btnLatest) btnLatest.disabled = true;
                slider.value = 0;
                display.textContent = "Latest";
            }
        }

        async function loadFrontlineLayersForDate(date) {
            const promises = [];
            document.querySelectorAll('#frontlineLayerList .layer-item').forEach(item => {
                const filename = item.dataset.filename;
                const layerDate = extractDateFromFilename(filename);
                const chk = document.getElementById('chk_' + filename);

                if (layerDate === date && chk && chk.checked) {
                    if (!activeLayers[filename]) {
                        promises.push(fetchAndAddKML(filename));
                    }
                }
            });
            await Promise.all(promises);
        }

        document.getElementById('timelineSlider').addEventListener('input', async (e) => {
            if (availableDates.length === 0) return;
            const idx = parseInt(e.target.value, 10);
            const selectedDate = availableDates[idx];
            document.getElementById('currentDateDisplay').textContent = selectedDate;

            // Load logic:
            // Only load the current date layers, but optionally preload a few around it if timeline section is open.
            const timelineSectionContent = document.getElementById('timelineContainer').closest('.section-content');
            const isTrackerExpanded = timelineSectionContent && !timelineSectionContent.classList.contains('collapsed');

            const datesToLoad = new Set([selectedDate]);
            if (isTrackerExpanded) {
                // If expanded, preload the next 3 and previous 3 to make timeline smoother
                for (let i = 1; i <= 3; i++) {
                    if (idx - i >= 0) datesToLoad.add(availableDates[idx - i]);
                    if (idx + i < availableDates.length) datesToLoad.add(availableDates[idx + i]);
                }
            }

            // Fire and forget loading of adjacent dates
            for (const date of datesToLoad) {
                if (date !== selectedDate) {
                    loadFrontlineLayersForDate(date);
                }
            }

            // Await specifically for the current selected date
            await loadFrontlineLayersForDate(selectedDate);

            // Toggle layer map visibility AND UI list visibility
            document.querySelectorAll('.layer-item').forEach(layerItemDiv => {
                const filename = layerItemDiv.dataset.filename;
                if (!filename) return;

                const chk = document.getElementById('chk_' + filename);
                const isFrontline = filename.startsWith('AP Map') || filename.startsWith('AP Pins') || filename.startsWith('SM Map') || filename.startsWith('SM Pins');
                const layerDate = extractDateFromFilename(filename);

                if (isFrontline) {
                    // If it matches the current timeline date
                    if (!layerDate || layerDate === selectedDate) {
                        layerItemDiv.style.display = 'flex'; // Show in UI list

                        if (activeLayers[filename]) {
                            const isChecked = chk?.checked;
                            if (isChecked && !map.hasLayer(activeLayers[filename])) {
                                map.addLayer(activeLayers[filename]);
                            }
                        }
                    } else {
                        layerItemDiv.style.display = 'none'; // Hide from UI list

                        if (activeLayers[filename] && map.hasLayer(activeLayers[filename])) {
                            map.removeLayer(activeLayers[filename]);
                        }
                    }
                } else {
                    // Static layer
                    if (activeLayers[filename]) {
                        const isChecked = chk?.checked;
                        if (isChecked && !map.hasLayer(activeLayers[filename])) {
                            map.addLayer(activeLayers[filename]);
                        } else if (!isChecked && map.hasLayer(activeLayers[filename])) {
                            map.removeLayer(activeLayers[filename]);
                        }
                    }
                }
            });

            // Reapply z-index ordering after layers are added/removed
            reorderActiveLayers();
        });

        const timelineSlider = document.getElementById('timelineSlider');

        const btnTimelineBack = document.getElementById('btnTimelineBack');
        if (btnTimelineBack) {
            btnTimelineBack.addEventListener('click', () => {
                if (timelineSlider.disabled) return;
                let val = parseInt(timelineSlider.value, 10);
                if (val > parseInt(timelineSlider.min, 10)) {
                    timelineSlider.value = val - 1;
                    timelineSlider.dispatchEvent(new Event('input'));
                }
            });
        }

        const btnTimelineForward = document.getElementById('btnTimelineForward');
        if (btnTimelineForward) {
            btnTimelineForward.addEventListener('click', () => {
                if (timelineSlider.disabled) return;
                let val = parseInt(timelineSlider.value, 10);
                if (val < parseInt(timelineSlider.max, 10)) {
                    timelineSlider.value = val + 1;
                    timelineSlider.dispatchEvent(new Event('input'));
                }
            });
        }

        const btnTimelineLatest = document.getElementById('btnTimelineLatest');
        if (btnTimelineLatest) {
            btnTimelineLatest.addEventListener('click', () => {
                if (timelineSlider.disabled) return;
                let val = parseInt(timelineSlider.value, 10);
                let maxVal = parseInt(timelineSlider.max, 10);
                if (val !== maxVal) {
                    timelineSlider.value = maxVal;
                    timelineSlider.dispatchEvent(new Event('input'));
                }
            });
        }

    // Helper function to calculate estimated sun-synchronous pass times
        function calculatePassEstimates(lng) {
            const now = new Date();
            // Longitude offset in hours (15 degrees = 1 hour)
            const lngOffsetHours = lng / 15;

            // Sentinel-2 crosses equator at ~10:30 AM Local Solar Time
            // VIIRS (SNPP, NOAA-20, NOAA-21) cross at ~13:30 PM Local Solar Time
            const s2TargetLST = 10.5;
            const viirsTargetLST = 13.5;

            // Calculate UTC times for today's passes
            let s2UtcPass = s2TargetLST - lngOffsetHours;
            let viirsUtcPass = viirsTargetLST - lngOffsetHours;

            // Adjust if the pass time goes negative (previous day UTC)
            if (s2UtcPass < 0) s2UtcPass += 24;
            if (viirsUtcPass < 0) viirsUtcPass += 24;

            // Format hours and minutes
            const formatTime = (decimalHours) => {
                const h = Math.floor(decimalHours);
                const m = Math.round((decimalHours - h) * 60).toString().padStart(2, '0');
                return `${h.toString().padStart(2, '0')}:${m} UTC`;
            };

            return {
                sentinel: formatTime(s2UtcPass),
                viirs: formatTime(viirsUtcPass)
            };
        }

        // Helper function to build the complicated WMS GetFeatureInfo URL
        function getFeatureInfoUrl(map, layer, latlng) {
            const point = map.latLngToContainerPoint(latlng, map.getZoom());
            const size = map.getSize();
            const bounds = map.getBounds();
            const sw = bounds.getSouthWest();
            const ne = bounds.getNorthEast();

            const params = {
                request: 'GetFeatureInfo',
                service: 'WMS',
                srs: 'EPSG:4326',
                styles: '',
                transparent: true,
                version: '1.3.0',
                format: 'image/png',
                bbox: sw.lat + ',' + sw.lng + ',' + ne.lat + ',' + ne.lng, // EPSG:4326 is Lat,Lng
                height: size.y,
                width: size.x,
                layers: layer.wmsParams.layers,
                query_layers: layer.wmsParams.layers,
                info_format: 'application/json', // Ask Sentinel Hub for JSON metadata
                i: Math.round(point.x),
                j: Math.round(point.y)
            };

            return layer._url + L.Util.getParamString(params, layer._url, true);
        }


// The Click Event Listener
        // The Master Unified Click Event Listener

// Helper to look up what a location actually is
async function reverseGeocodeLocation(lat, lng) {
    try {
        // Zoom 18 targets specific buildings and POIs (Points of Interest)
        // Added extratags=1, namedetails=1, and accept-language=en for more specific English identification
        const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1&extratags=1&namedetails=1&accept-language=en`;

        const response = await fetch(url, {
            headers: {
                'Accept-Language': 'en' // Forces English results where available
            }
        });

        const data = await response.json();

        if (data && (data.address || data.class || data.type)) {
            let featureDescription = '';
            let specificName = '';

            // Try to extract a specific name from namedetails or address dictionary
            if (data.namedetails && (data.namedetails.name || data.namedetails['name:en'])) {
                specificName = data.namedetails['name:en'] || data.namedetails.name;
            } else if (data.address && data.address.amenity) {
                specificName = data.address.amenity;
            } else if (data.address && data.address.building) {
                specificName = data.address.building;
            } else if (data.name) {
                specificName = data.name;
            }

            // Fallback for missing category (older API uses class/type)
            const catRaw = data.class || data.category;
            const typeRaw = data.type;

            // OSM categorises things nicely. Let's extract that if it exists.
            if (catRaw && typeRaw && catRaw !== 'boundary') {
                // Capitalise and clean up the tags (e.g., turns "power" and "substation" into "Power - Substation")
                const cat = catRaw.charAt(0).toUpperCase() + catRaw.slice(1).replace(/_/g, ' ');
                const type = typeRaw.charAt(0).toUpperCase() + typeRaw.slice(1).replace(/_/g, ' ');

                let titleHtml = `<b>Feature:</b> ${cat} - ${type}`;

                // If we found a specific name, inject it
                if (specificName && specificName.toLowerCase() !== type.toLowerCase()) {
                    titleHtml = `<b>${specificName}</b><br><span style="font-size: 0.8em; color: #cbd5e1;">${cat} - ${type}</span>`;
                }

                featureDescription = `<div style="margin-bottom: 6px; color: #facc15;">${titleHtml}</div>`;
            } else if (specificName) {
                // Fallback if we have a name but no valid category
                featureDescription = `<div style="margin-bottom: 6px; color: #facc15;"><b>${specificName}</b></div>`;
            }

            // Check extratags for useful structural metadata
            let extraInfo = '';
            if (data.extratags) {
                if (data.extratags.building) extraInfo += `<div><span style="color:#94a3b8">Building:</span> ${data.extratags.building}</div>`;
                if (data.extratags.operator) extraInfo += `<div><span style="color:#94a3b8">Operator:</span> ${data.extratags.operator}</div>`;
                if (data.extratags.usage) extraInfo += `<div><span style="color:#94a3b8">Usage:</span> ${data.extratags.usage}</div>`;
            }
            if (extraInfo) {
                extraInfo = `<div style="font-size: 0.8rem; margin-bottom: 6px; padding-left: 6px; border-left: 2px solid #64748b;">${extraInfo}</div>`;
            }

            // Display name usually contains the full address string
            const addressString = data.display_name ? `<div><b style="color: #94a3b8;">Address:</b> ${data.display_name}</div>` : '';

            return `${featureDescription}${extraInfo}${addressString}`;
        }
        return '<em style="color: #94a3b8;">No detailed location data found.</em>';
    } catch (error) {
        console.error("Geocoding lookup failed:", error);
        return '<em style="color: #ef4444;">Failed to look up location.</em>';
    }
}

map.on('click', async function(e) {
            window.highlightedVesselMmsi = null;
            if (shadowFleetTrackLayer) {
                shadowFleetTrackLayer.setStyle(shadowFleetTrackLayer.options.style);
            }

            if (window.currentTool && (window.currentTool === 'ruler' || window.currentTool === 'circle')) {
                return;
            }

            const lat = e.latlng.lat;
            const lng = e.latlng.lng;
            const clickPoint = turf.point([lng, lat]);
            const estimates = calculatePassEstimates(lng);

            // We will build one giant, scrollable HTML string
            let popupHTML = `<div style="min-width: 250px; max-width: 320px; max-height: 400px; overflow-y: auto; padding-right: 5px;">`;

            // Generate a unique ID for this specific popup instance
            const popupId = 'osmGeoLookup_' + Math.random().toString(36).substr(2, 9);

            // --- 1. Location Intelligence (Always shows) ---
            popupHTML += `
                <h3 style="margin: 0 0 8px 0; border-bottom: 1px solid #475569; padding-bottom: 4px;">Location Intelligence</h3>
                <p style="margin: 4px 0; font-size: 0.85rem;"><b>Lat:</b> ${lat.toFixed(4)}<br><b>Lng:</b> ${lng.toFixed(4)}</p>

                <div id="${popupId}" style="margin: 8px 0; padding: 6px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 0.85rem; border-left: 2px solid #3b82f6;">
                    <em style="color: #94a3b8;">Scanning location data...</em>
                </div>



                <div id="wmsInfo_${popupId}" style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #475569; display: none;">
                    <h4 style="margin: 0 0 4px 0; color: #22c55e;">📸 Sentinel Image Data</h4>
                    <div id="wmsLoading_${popupId}">Querying Copernicus...</div>
                </div>
            `;

            // --- 2. KML Data & Metadata Extraction ---
            let kmlHitsHTML = '';
            for (const filename in activeKMLGeoJSON) {
                // Only drill down if the layer is visibly checked on the map
                if (activeLayers[filename] && map.hasLayer(activeLayers[filename])) {
                    turf.featureEach(activeKMLGeoJSON[filename], function (currentFeature) {
                        let isHit = false;

                        // Mathematical intersection based on geometry type
                        if (currentFeature.geometry.type === 'Polygon' || currentFeature.geometry.type === 'MultiPolygon') {
                            isHit = turf.booleanPointInPolygon(clickPoint, currentFeature);
                        } else if (currentFeature.geometry.type === 'Point') {
                            const dist = turf.distance(clickPoint, currentFeature, {units: 'meters'});
                            isHit = dist < 500; // 500m hit tolerance for points
                        } else if (currentFeature.geometry.type === 'LineString' || currentFeature.geometry.type === 'MultiLineString') {
                            const dist = turf.pointToLineDistance(clickPoint, currentFeature, {units: 'meters'});
                            isHit = dist < 500; // 500m hit tolerance for lines
                        }

                        if (isHit) {
                            kmlHitsHTML += `<div style="margin-top: 12px; border-top: 1px solid #475569; padding-top: 8px;">`;
                            kmlHitsHTML += `<h4 style="margin: 0 0 6px 0; color: #facc15;">📁 ${filename}</h4>`;

                            // The Magic Loop: Extracts ALL metadata dynamically
                            if (currentFeature.properties) {
                                let metaCount = 0;
                                let hiddenMetaHTML = '';

                                for (const key in currentFeature.properties) {
                                    // Ignore useless internal styling keys generated by toGeoJSON
                                    if (key !== 'styleUrl' && key !== 'styleHash' && key !== 'styleMapHash') {
                                        const val = currentFeature.properties[key];
                                        // Format links cleanly if they exist
                                        if (val) {
                                            const displayVal = String(val).startsWith('http') ? `<a href="${val}" target="_blank" style="color:#3b82f6;">Link</a>` : val;
                                            const rowHTML = `<div style="font-size: 0.85rem; margin-bottom: 3px; word-wrap: break-word;"><b>${key}:</b> ${displayVal}</div>`;

                                            if (metaCount < 4) {
                                                kmlHitsHTML += rowHTML;
                                            } else {
                                                hiddenMetaHTML += rowHTML;
                                            }
                                            metaCount++;
                                        }
                                    }
                                }

                                // Wrap excess metadata in a details block
                                if (hiddenMetaHTML) {
                                    kmlHitsHTML += `
                                        <details style="margin-top: 6px; font-size: 0.85rem;">
                                            <summary style="cursor: pointer; color: #94a3b8; user-select: none;">More info...</summary>
                                            <div style="margin-top: 6px; padding-left: 8px; border-left: 2px solid #475569;">
                                                ${hiddenMetaHTML}
                                            </div>
                                        </details>
                                    `;
                                }
                            }
                            kmlHitsHTML += `</div>`;
                        }
                    });
                }
            }
            if (kmlHitsHTML) popupHTML += kmlHitsHTML;

            // --- 2.5 Shadow Fleet Drill-down ---
            if (window.currentShadowFleetFeatures) {
                const chk = document.getElementById('chk_shadowFleet');
                if (chk && chk.checked) {
                    let shadowHitsHTML = '';

                    // Find the single closest vessel within a small screen-space tolerance (in pixels)
                    let closestFeature = null;
                    let minScreenDist = 15; // match if within 15 screen pixels of the click
                    const clickPointPx = map.latLngToContainerPoint(e.latlng);

                    turf.featureEach(window.currentShadowFleetFeatures, function (currentFeature) {
                        if (!currentFeature || !currentFeature.geometry || !currentFeature.geometry.coordinates) return;
                        const coords = currentFeature.geometry.coordinates; // [lon, lat]

                        // Validate coords exist before accessing array elements
                        if (coords.length >= 2 && coords[0] != null && coords[1] != null) {
                            // Leaflet takes [lat, lon]
                            const featureLatLng = L.latLng(coords[1], coords[0]);
                            const featurePx = map.latLngToContainerPoint(featureLatLng);

                            const distPx = Math.sqrt(Math.pow(clickPointPx.x - featurePx.x, 2) + Math.pow(clickPointPx.y - featurePx.y, 2));

                            if (distPx < minScreenDist) {
                                closestFeature = currentFeature;
                                minScreenDist = distPx;
                            }
                        }
                    });

                    if (closestFeature) {
                        const props = closestFeature.properties;
                        window.highlightedVesselMmsi = props.mmsi;
                        if (shadowFleetTrackLayer) {
                            shadowFleetTrackLayer.setStyle(shadowFleetTrackLayer.options.style);
                        }
                        const status = props.is_live ? "🔴 LIVE" : "⚫ DARK (AIS OFF)";
                        shadowHitsHTML += `<div style="margin-top: 12px; border-top: 1px solid #475569; padding-top: 8px;">`;
                        shadowHitsHTML += `<h4 style="margin: 0 0 6px 0; color: #3b82f6;">🚢 Shadow Fleet: ${props.name}</h4>`;
                        shadowHitsHTML += `<div style="font-size: 0.85rem; margin-bottom: 3px;"><b>MMSI:</b> ${props.mmsi}</div>`;
                        shadowHitsHTML += `<div style="font-size: 0.85rem; margin-bottom: 3px;"><b>Type:</b> ${props.type}</div>`;
                        shadowHitsHTML += `<div style="font-size: 0.85rem; margin-bottom: 3px;"><b>Status:</b> ${status}</div>`;
                        shadowHitsHTML += `<div style="font-size: 0.85rem; margin-bottom: 3px;"><b>Last Seen:</b> ${new Date(props.last_seen).toLocaleString()}</div>`;

                        // Tracks are now rendered globally

                        shadowHitsHTML += `</div>`;
                    }
                    if (shadowHitsHTML) popupHTML += shadowHitsHTML;
                }
            }

            // --- 3. Radar Russia Data Drill-down ---
            if (map.hasLayer(radarRussiaLayerGroup) && activeKMLGeoJSON['RadarRussia']) {
                let radarHitsHTML = '';
                const radarHits = [];
                turf.featureEach(activeKMLGeoJSON['RadarRussia'], function (currentFeature) {
                    let isHit = false;

                    if (currentFeature.geometry.type === 'Polygon' || currentFeature.geometry.type === 'MultiPolygon') {
                        isHit = turf.booleanPointInPolygon(clickPoint, currentFeature);

                        // Hit testing fallback for small polygons rendered as markers
                        if (!isHit) {
                            if (currentFeature.properties.icon) {
                                const centroid = turf.centroid(currentFeature);
                                const dist = turf.distance(clickPoint, centroid, {units: 'kilometers'});
                                // Give a 10km click radius for these tiny areas/markers
                                if (dist < 10) {
                                    isHit = true;
                                }
                            }
                        }
                    } else if (currentFeature.geometry.type === 'Point') {
                        const dist = turf.distance(clickPoint, currentFeature, {units: 'meters'});
                        isHit = dist < 20000; // Allow 20km hit tolerance for cities/regions point representations
                    } else if (currentFeature.geometry.type === 'LineString' || currentFeature.geometry.type === 'MultiLineString') {
                        const dist = turf.pointToLineDistance(clickPoint, currentFeature, {units: 'meters'});
                        isHit = dist < 5000;
                    }

                    if (isHit) {
                        radarHits.push(currentFeature);
                    }
                });

                if (radarHits.length > 0) {
                    const liveCount = radarHits.filter(f => f.properties.status !== 'over').length;

                    radarHitsHTML += `<div style="font-size: 0.85rem; margin-bottom: 4px; color: #ef4444;"><b>${liveCount} live alert${liveCount === 1 ? '' : 's'} received (24 hours)</b></div>`;

                    const now = new Date();
                    radarHits.forEach(currentFeature => {
                        const props = currentFeature.properties;
                        const timeStr = new Date(props.time).toLocaleString('en-GB');

                        const diffMs = now - new Date(props.time);
                        const diffMins = Math.floor(diffMs / 60000);
                        const hours = Math.floor(diffMins / 60);
                        const mins = diffMins % 60;
                        let relativeTime = '';
                        if (hours > 0) {
                            relativeTime = `(${hours} hour${hours > 1 ? 's' : ''}${mins > 0 ? ` and ${mins} min${mins > 1 ? 's' : ''}` : ''} ago)`;
                        } else if (mins > 0) {
                            relativeTime = `(${mins} min${mins > 1 ? 's' : ''} ago)`;
                        } else {
                            relativeTime = `(just now)`;
                        }

                        radarHitsHTML += `
                            <div style="margin-top: 12px; border-top: 1px solid #475569; padding-top: 8px;">
                                <h4 style="margin: 0 0 4px 0; color: #3b82f6;">🚨 Air Alert</h4>
                                <div style="font-size: 0.85rem;">
                                    <b>Location:</b> ${props.name}<br>
                                    ${window.location.pathname.startsWith('/admin') ? `<b>Nominatim Query:</b> <span style="cursor: pointer; text-decoration: underline;" onclick="if(window.populateOverrideName) window.populateOverrideName('${encodeURIComponent(props.raw_name).replace(/'/g, "%27")}');">${props.raw_name}</span><br>` : ''}
                                    <b>Threat:</b> ${props.threat}<br>
                                    <b>Status:</b> ${props.status === 'over' ? '<span style="color:#22c55e;">Over</span>' : '<span style="color:#ef4444;">Active</span>'}<br>
                                    <b>Time:</b> ${timeStr} ${relativeTime}
                                </div>
                            </div>
                        `;
                    });
                }

                if (radarHitsHTML) popupHTML += radarHitsHTML;
            }

            // --- 4. FIRMS Data Drill-down ---
            if (map.hasLayer(firmsVectorGroup)) {
                const firmsHits = [];
                const now = new Date();

                currentFirmsData.forEach(fire => {
                    const firePt = turf.point([parseFloat(fire.longitude), parseFloat(fire.latitude)]);
                    const dist = turf.distance(clickPoint, firePt, {units: 'meters'});

                    // If click is within the visual radius of the drawn circle (187.5m), count it as a hit
                    if (dist < 187.5) {
                        const timeStr = fire.acq_time.padStart(4, '0');
                        const fireDate = new Date(`${fire.acq_date}T${timeStr.substring(0, 2)}:${timeStr.substring(2, 4)}:00Z`);
                        const ageHours = (now - fireDate) / (1000 * 60 * 60);

                        firmsHits.push({
                            fire,
                            timeStr,
                            fireDate,
                            ageHours
                        });
                    }
                });

                if (firmsHits.length > 0) {
                    // Sort reverse chronological (newest first)
                    firmsHits.sort((a, b) => b.fireDate - a.fireDate);

                    let firmsHitsHTML = '';
                    firmsHits.forEach(hit => {
                        firmsHitsHTML += `
                            <div style="margin-top: 12px; border-top: 1px solid #475569; padding-top: 8px;">
                                <h4 style="margin: 0 0 4px 0; color: #ef4444;">🔥 Thermal Anomaly</h4>
                                <div style="font-size: 0.85rem;">
                                    <b>Detected:</b> ${hit.fire.acq_date} at ${hit.timeStr} UTC<br>
                                    <b>Age:</b> ${Math.round(hit.ageHours)} hours ago<br>
                                    <b>Confidence:</b> ${hit.fire.confidence}
                                </div>
                            </div>
                        `;
                    });
                    popupHTML += firmsHitsHTML;
                }
            }

            // Close the master container and trigger Leaflet
            popupHTML += `</div>`;

            const popup = L.popup()
                .setLatLng(e.latlng)
                .setContent(popupHTML)
                .openOn(map);

            // Fire the reverse geocoding API in the background
            if (typeof reverseGeocodeLocation === 'function') {
                reverseGeocodeLocation(lat, lng).then(resultHTML => {
                    const lookupDiv = document.getElementById(popupId);
                    if (lookupDiv) {
                        lookupDiv.innerHTML = resultHTML;
                    }
                });
            }

            // If the Sentinel layer is currently active on the map, find the image date
            if (map.hasLayer(layers.sentinelLayer) && map.getZoom() >= 11) {
                const wmsInfo = document.getElementById(`wmsInfo_${popupId}`);
                if (wmsInfo) wmsInfo.style.display = 'block';

                const wmsLoading = document.getElementById(`wmsLoading_${popupId}`);
                if (wmsLoading) {
                    let clickedFeature = null;

                    // Because currentSentinelFeatures is sorted newest-to-oldest by the backend,
                    // the FIRST footprint we hit is mathematically the one visible on top of the mosaic.
                    for (const feature of window.currentSentinelFeatures) {
                        if (feature.geometry && turf.booleanPointInPolygon(clickPoint, feature)) {
                            clickedFeature = feature;
                            break;
                        }
                    }

                    if (clickedFeature) {
                        // Extract date and cloud cover from the STAC properties
                        const captureDate = new Date(clickedFeature.properties.datetime).toLocaleString('en-GB');
                        const cloudCover = clickedFeature.properties['eo:cloud_cover']
                            ? clickedFeature.properties['eo:cloud_cover'].toFixed(1)
                            : "Unknown";

                        wmsLoading.innerHTML = `
                            <b>Acquired:</b> ${captureDate}<br>
                            <span style="font-size: 0.8em; color: #94a3b8;">Cloud Cover: ${cloudCover}%</span>
                        `;
                    } else {
                        wmsLoading.innerHTML = `<em style="color: #94a3b8;">No recent imagery data for this exact point.</em>`;
                    }
                }
            }
        });
        window.loadSettingsAndInit = async function loadSettingsAndInit() {
            try {
                const response = await fetch('/api/settings');
                appSettings = await response.json();

                layerStyles = appSettings.layerStyles || {};

                // Apply default map settings if available, overridden by URL parameters
                const urlParams = new URLSearchParams(window.location.search);
                const urlLat = urlParams.get('lat');
                const urlLng = urlParams.get('lng');
                const urlZoom = urlParams.get('zoom');
                const urlBasemap = urlParams.get('basemap');

                const defaultLat = urlLat ? parseFloat(urlLat) : (appSettings.defaultLat ?? 49.0);
                const defaultLng = urlLng ? parseFloat(urlLng) : (appSettings.defaultLng ?? 31.0);
                const defaultZoom = urlZoom ? parseFloat(urlZoom) : (appSettings.defaultZoom ?? 6);
                map.setView([defaultLat, defaultLng], defaultZoom, {animate: false});

                const defaultBasemap = urlBasemap ? urlBasemap : (appSettings.defaultBasemap ?? 'dark');
                const radioInput = document.querySelector(`input[name="basemap"][value="${defaultBasemap}"]`);
                if (radioInput) radioInput.checked = true;

                // Support baseMaps from global scope if available (defined in map-core.js)
                if (window.baseMaps && window.baseMaps[defaultBasemap]) {
                    window.baseMaps[defaultBasemap].addTo(map);
                } else if (typeof baseMaps !== 'undefined' && baseMaps[defaultBasemap]) {
                    baseMaps[defaultBasemap].addTo(map);
                } else {
                    if (window.baseMaps) {
                        window.baseMaps.dark.addTo(map);
                    } else if (typeof baseMaps !== 'undefined') {
                        baseMaps.dark.addTo(map);
                    }
                }

                if (window.updateSentinelStatus) window.updateSentinelStatus();

            } catch (err) {
                console.error("Failed to load settings:", err);
                baseMaps.dark.addTo(map); // Fallback
            }
            loadLayers();
        }
        function reorderActiveLayers() {
            // We want Static Layers on the BOTTOM and Frontline on the TOP.
            // Because `.bringToFront()` successively pushes layers to the absolute top of the Leaflet pane,
            // the *last* layer we call it on will be the *highest* visible layer.
            //
            // In the UI list (top-to-bottom):
            // The top-most item in a list should be visually higher than the bottom-most item in that list.
            // Therefore, we must process the bottom-most UI item first, and the top-most UI item last.
            //
            // Order of calling `bringToFront()`:
            // 1. Static Layers (bottom UI item up to top UI item)
            // 2. Frontline Layers (bottom UI item up to top UI item)

            const staticItems = document.querySelectorAll('#staticLayerList .layer-item');
            const frontlineItems = document.querySelectorAll('#frontlineLayerList .layer-item');

            // Process Static Layers (iterate backwards)
            for (let i = staticItems.length - 1; i >= 0; i--) {
                const filename = staticItems[i].dataset.filename;
                if (activeLayers[filename] && map.hasLayer(activeLayers[filename])) {
                    activeLayers[filename].bringToFront();
                }
            }

            // Process Frontline Layers (iterate backwards)
            for (let i = frontlineItems.length - 1; i >= 0; i--) {
                const filename = frontlineItems[i].dataset.filename;
                if (activeLayers[filename] && map.hasLayer(activeLayers[filename])) {
                    activeLayers[filename].bringToFront();
                }
            }
        }
        // --- RIGHT-CLICK TIMELINE SCRUBBER ---
        let isRightMouseDown = false;
        let didScrub = false;
        let scrubTimeout;
        let timelineOriginalParent = null;
        let timelineOriginalNextSibling = null;

        // 1. Track Right Mouse Button
        document.addEventListener('mousedown', (e) => {
            if (e.button === 2) {
                isRightMouseDown = true;
                didScrub = false;
                map.scrollWheelZoom.disable(); // Stop Leaflet from zooming
            }
        });

        document.addEventListener('mouseup', (e) => {
            if (e.button === 2) {
                isRightMouseDown = false;
                map.scrollWheelZoom.enable(); // Re-enable Leaflet zoom
                // Brief delay to prevent the context menu from flashing if they scrubbed
                setTimeout(() => { didScrub = false; }, 50);
            }
        });

        // 2. Block the context menu ONLY if they used the scroll wheel
        document.addEventListener('contextmenu', (e) => {
            if (didScrub) e.preventDefault();
        });

        // 3. The Scrubbing Logic
        document.addEventListener('wheel', (e) => {
            if (isRightMouseDown) {
                e.preventDefault(); // Stop page scrolling
                didScrub = true;

                const slider = document.getElementById('timelineSlider');
                if (!slider || slider.max === "0") return; // Exit if no timeline exists

                // Determine direction (Up = Future, Down = Past)
                const step = e.deltaY > 0 ? -1 : 1;
                let newValue = parseInt(slider.value) + step;

                // Clamp values
                if (newValue < parseInt(slider.min)) newValue = parseInt(slider.min);
                if (newValue > parseInt(slider.max)) newValue = parseInt(slider.max);

                if (slider.value != newValue) {
                    slider.value = newValue;
                    slider.dispatchEvent(new Event('input')); // Trigger map update
                }

                // 4. Floating UI Logic (If panel is closed, pop the timeline into the center of the screen)
                const panel = document.getElementById('controlPanel');
                const timelineContainer = document.getElementById('timelineContainer');

                if (!panel.classList.contains('open')) {
                    if (!timelineOriginalParent) {
                        timelineOriginalParent = timelineContainer.parentNode;
                        timelineOriginalNextSibling = timelineContainer.nextSibling;
                        document.body.appendChild(timelineContainer);
                    }
                    timelineContainer.classList.add('scrubbing-float');

                    // Reset the disappearance timer
                    clearTimeout(scrubTimeout);
                    scrubTimeout = setTimeout(() => {
                        timelineContainer.classList.remove('scrubbing-float');
                        if (timelineOriginalParent) {
                            if (timelineOriginalNextSibling) {
                                timelineOriginalParent.insertBefore(timelineContainer, timelineOriginalNextSibling);
                            } else {
                                timelineOriginalParent.appendChild(timelineContainer);
                            }
                            timelineOriginalParent = null;
                            timelineOriginalNextSibling = null;
                        }
                    }, 1500); // Hides 1.5s after they stop scrolling
                }
            }

        }, { passive: false }); // Passive: false is required to preventDefault on wheel events

async function syncSentinelMetadata() {
    // Only bother fetching metadata if the Sentinel layer is actually active and zoomed in
    // "layers.sentinelLive" was the old check, but here let's check layers.sentinelLayer
    if (!map.hasLayer(layers.sentinelLayer)) return;
    const zoom = map.getZoom();
    if (zoom < 11) {
        layers.footprintLayer.clearLayers();
        return;
    }

    const center = map.getCenter();
    try {
        const res = await fetch(`/api/sentinel-metadata?lat=${center.lat}&lng=${center.lng}&z=${Math.round(zoom)}`);
        if (!res.ok) return;
        const data = await res.json();

        window.currentSentinelFeatures = data.features || [];

        // 1. Update footprints if the user has them toggled on
        if (map.hasLayer(layers.footprintLayer)) {
            layers.footprintLayer.clearLayers();

            // Filter to only add footprints that have valid data and aren't overlapping needlessly
            // Since data is sorted newest-first, we can just use the most recent ones
            // that cover the bounding box, or just the top 5 to avoid clutter
            const topFeatures = window.currentSentinelFeatures.slice(0, 5);
            layers.footprintLayer.addData({
                type: 'FeatureCollection',
                features: topFeatures
            });
        }

        // 2. The Cloudflare Cache Buster
        if (window.currentSentinelFeatures.length > 0) {
            const newestPass = window.currentSentinelFeatures[0].properties.datetime;

            // If the newest image timestamp has changed since we last checked...
            if (window.currentCacheBuster !== newestPass) {
                window.currentCacheBuster = newestPass;
                // Update the URL to force Leaflet (and Cloudflare) to fetch fresh WEBP tiles
                layers.sentinelLayer.setUrl(`/api/sentinel-latest/{z}/{x}/{y}.webp?v=${window.currentCacheBuster}`);
            }
        }
    } catch (e) {
        console.error("Failed to sync Sentinel metadata", e);
    }
}

// Hook it into Leaflet's pan/zoom event
map.on('moveend', syncSentinelMetadata);
// Also trigger it when the layer is toggled on manually
layers.sentinelLayer.on('add', syncSentinelMetadata);

document.getElementById('toggleSentinelFootprint')?.addEventListener('change', function(e) {
    if (e.target.checked) {
        map.addLayer(layers.footprintLayer);
        syncSentinelMetadata(); // Fetch data immediately if needed
    } else {
        map.removeLayer(layers.footprintLayer);
    }
});

// --- SHADOW FLEET LOGIC ---
function getShadowFleetStyle(feature) {
    let fillColor = '#3B82F6'; // Default Blue
    let color = '#ffffff';     // Stroke color

    if (!feature.properties.is_live) {
        fillColor = '#6B7280'; // Gray for Dark/Offline vessels
        color = '#9CA3AF';
    } else if (feature.properties.type === 'Tanker') {
        fillColor = '#EF4444'; // Red for live Tanker
    } else if (feature.properties.type === 'Cargo') {
        fillColor = '#F97316'; // Orange for live Cargo
    }

    return {
        radius: 6,
        fillColor: fillColor,
        color: color,
        weight: 1,
        opacity: 1,
        fillOpacity: 0.8
    };
}

let shadowFleetLayer = null;
let shadowFleetTrackLayer = null;
window.highlightedVesselMmsi = null;

async function loadShadowFleetLayer() {
    const statusDiv = document.getElementById('shadowFleetStatus');

    try {
        if (statusDiv) statusDiv.textContent = 'Fetching vessels...';

        const response = await fetch('/api/shadow-fleet/vessels');
        if (!response.ok) throw new Error("HTTP error " + response.status);
        const geojsonData = await response.json();

        // Remove existing layer if refreshing
        if (shadowFleetLayer) {
            map.removeLayer(shadowFleetLayer);
        }

        shadowFleetLayer = L.geoJSON(geojsonData, {
            pointToLayer: function (feature, latlng) {
                return L.circleMarker(latlng, getShadowFleetStyle(feature));
            },
            interactive: false // CRITICAL: Lets clicks pass through to the unified master map click event
        });

        // Globally expose the raw data so the unified click handler in map-core.js or map-layers.js can intersect it using Turf.js
        window.currentShadowFleetFeatures = geojsonData;

        // Load all tracks simultaneously
        const trackResponse = await fetch('/api/shadow-fleet/tracks');
        let trackGeoJSON = { type: "FeatureCollection", features: [] };
        if (trackResponse.ok) {
            trackGeoJSON = await trackResponse.json();
        }

        if (shadowFleetTrackLayer) {
            map.removeLayer(shadowFleetTrackLayer);
        }

                shadowFleetTrackLayer = L.geoJSON(trackGeoJSON, {
            style: function(feature) {
                let color = '#EF4444'; // Red
                let weight = 2;
                let opacity = 0.6;
                let dashArray = '5, 5';

                if (feature.properties.is_dark) {
                    color = '#9CA3AF'; // Gray
                }

                if (window.highlightedVesselMmsi) {
                    if (feature.properties.mmsi === window.highlightedVesselMmsi) {
                        weight = 4;
                        opacity = 1.0;
                        dashArray = '8, 8'; // Make the dashes larger to highlight the track more
                    } else {
                        weight = 0;
                        opacity = 0;
                    }
                }

                return {
                    color: color,
                    weight: weight,
                    opacity: opacity,
                    dashArray: dashArray
                };
            }
        });

        // Only add to map if the checkbox is checked, since this might be called on interval
        const chk = document.getElementById('chk_shadowFleet');
        if (chk && chk.checked) {
            shadowFleetLayer.addTo(map);
            shadowFleetTrackLayer.addTo(map); // Add tracks as well
            if (statusDiv) {
                const count = geojsonData.features ? geojsonData.features.length : 0;
                statusDiv.textContent = `Tracking ${count} vessel(s)`;
                statusDiv.style.color = '#10b981'; // Green to show success
            }
        }
    } catch (error) {
        console.error("Failed to load Shadow Fleet data:", error);
        if (statusDiv) {
            statusDiv.textContent = 'Error fetching vessels';
            statusDiv.style.color = '#ef4444'; // Red to show error
        }
    }
}

async function loadVesselTrack(mmsi) {
    try {
        const response = await fetch(`/api/shadow-fleet/tracks/${mmsi}`);
        if (!response.ok) throw new Error("HTTP error " + response.status);
        const trackGeoJSON = await response.json();

        if (shadowFleetTrackLayer) {
            map.removeLayer(shadowFleetTrackLayer);
        }

                shadowFleetTrackLayer = L.geoJSON(trackGeoJSON, {
            style: function(feature) {
                let color = '#EF4444'; // Red
                let weight = 2;
                let opacity = 0.6;
                let dashArray = '5, 5';

                if (feature.properties.is_dark) {
                    color = '#9CA3AF'; // Gray
                }

                if (window.highlightedVesselMmsi) {
                    if (feature.properties.mmsi === window.highlightedVesselMmsi) {
                        weight = 4;
                        opacity = 1.0;
                        dashArray = '8, 8'; // Make the dashes larger to highlight the track more
                    } else {
                        weight = 0;
                        opacity = 0;
                    }
                }

                return {
                    color: color,
                    weight: weight,
                    opacity: opacity,
                    dashArray: dashArray
                };
            }
        });

        shadowFleetTrackLayer.addTo(map);
    } catch (error) {
        console.error("Failed to load track:", error);
    }
}

// Auto-refresh shadow fleet data
setInterval(() => {
    const chk = document.getElementById('chk_shadowFleet');
    if (chk && chk.checked) {
        loadShadowFleetLayer();
    }
}, 60000); // Poll every 60 seconds


window.toggleRadarReplayPause = function() {
    window.radarReplayPaused = !window.radarReplayPaused;
    const btn = document.getElementById('replayPlayPauseBtn');
    if (btn) {
        btn.innerHTML = window.radarReplayPaused ? '▶️' : '⏸️';
    }
};

window.seekRadarReplay = function(percent) {
    if (!window.radarReplayStartTime) return;
    const progress = parseFloat(percent) / 100.0;

    // Instead of seeking, it's easier to adjust the start time of the replay
    // so that the current time evaluates to the desired progress.
    const duration = window.radarReplayDurationMs || 60000;
    const newElapsed = progress * duration;

    // The current performance.now() needs to be equivalent to radarReplayStartTime + newElapsed
    window.radarReplayStartTime = performance.now() - newElapsed;

    // If paused, we must manually update the replay time, because the animation loop skips time logic when paused.
    if (window.radarReplayPaused) {
        const realNow = new Date();
        const startReplayTime = new Date(realNow.getTime() - 24 * 60 * 60 * 1000);
        const timeWindowMs = 24 * 60 * 60 * 1000;
        window.radarReplayTime = new Date(startReplayTime.getTime() + (progress * timeWindowMs));
    }

    // Force a render
    renderRadarRussiaData();
};

window.changeRadarReplaySpeed = function() {
    const sel = document.getElementById('replaySpeedSelect');
    if (sel && window.radarReplayStartTime) {
        const oldDuration = window.radarReplayDurationMs || 60000;
        const newDuration = parseInt(sel.value) * 1000;

        // Calculate current progress so we can maintain the same relative position
        const elapsed = performance.now() - window.radarReplayStartTime;
        let progress = elapsed / oldDuration;
        if (progress > 1) progress = 1;

        window.radarReplayDurationMs = newDuration;

        // Adjust start time to maintain progress
        window.radarReplayStartTime = performance.now() - (progress * newDuration);
    } else if (sel) {
        window.radarReplayDurationMs = parseInt(sel.value) * 1000;
    }
};

window.closeRadarReplay = function() {
    window.radarReplayTime = null;
    window.radarReplayFinished = true;
    window.radarReplayPaused = false;

    const overlay = document.getElementById('replayOverlay');
    if (overlay) overlay.style.display = 'none';

    const controls = document.getElementById('replayControlsOverlay');
    if (controls) controls.style.display = 'none';

    const cp = document.getElementById('controlPanel');
    if (cp) {
        cp.style.display = ''; // Reset display
        // Optional: you can remove the open class, or let the user click it open again
    }

    // Re-render to show live data
    renderRadarRussiaData();
};
