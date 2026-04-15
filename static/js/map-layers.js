
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
                        checkbox.checked = isFrontline;
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
                        await fetchAndAddKML(filename);
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
                    checkbox.addEventListener('change', (e) => {
                        const isChecked = e.target.checked;

                        // If it's a frontline layer, toggle all related dates to match
                        if (isFrontline) {
                            let prefix = '';
                            if (filename.startsWith('AP Map')) prefix = 'AP Map';
                            else if (filename.startsWith('AP Pins')) prefix = 'AP Pins';
                            else if (filename.startsWith('SM Map')) prefix = 'SM Map';
                            else if (filename.startsWith('SM Pins')) prefix = 'SM Pins';

                            if (prefix) {
                                for (const fn in activeLayers) {
                                    if (fn.startsWith(prefix)) {
                                        const otherChk = document.getElementById('chk_' + fn);
                                        if (otherChk && otherChk !== checkbox) {
                                            otherChk.checked = isChecked;
                                        }

                                        // Update map visibility ONLY if this layer is meant for the CURRENT selected date
                                        const layerDate = extractDateFromFilename(fn);
                                        const currentDisplayDate = document.getElementById('currentDateDisplay').textContent;
                                        if (!layerDate || layerDate === currentDisplayDate) {
                                            if (isChecked && !map.hasLayer(activeLayers[fn])) {
                                                map.addLayer(activeLayers[fn]);
                                            } else if (!isChecked && map.hasLayer(activeLayers[fn])) {
                                                map.removeLayer(activeLayers[fn]);
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Handle current target specifically
                        if (isChecked) {
                            if (activeLayers[filename] && (!isFrontline || extractDateFromFilename(filename) === document.getElementById('currentDateDisplay').textContent)) {
                                map.addLayer(activeLayers[filename]);
                            }
                        } else {
                            if (activeLayers[filename] && map.hasLayer(activeLayers[filename])) {
                                map.removeLayer(activeLayers[filename]);
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
                    // Style for polygons/lines
                    style: function (feature) {
                        const style = getFeatureStyle(feature);
                        return { color: style.color, weight: 2, fillOpacity: style.opacity };
                    },
                    // Style for points/markers
                    pointToLayer: function (feature, latlng) {
                        const style = getFeatureStyle(feature);

                        // CHANGE 1: Use L.circle instead of L.circleMarker
                        return L.circle(latlng, {
                            // CHANGE 2: Radius is now in METRES.
                            // Try 50, 100, or 200 depending on how spaced out they are!
                            radius: 50,
                            fillColor: style.color,
                            color: '#ffffff',
                            weight: 1,
                            opacity: 1,
                            fillOpacity: style.opacity
                        });
                    },
                    onEachFeature: function (feature, layer) {
                        let popupContent = "";
                        if (feature.properties && feature.properties.name) {
                            popupContent += "<h3>" + feature.properties.name + "</h3>";
                        }
                        if (feature.properties && feature.properties.description) {
                            popupContent += "<p>" + feature.properties.description + "</p>";
                        }
                        if (popupContent) {
                            layer.bindPopup(popupContent);
                        }
                    }
                });

                if (activeLayers[filename]) {
                    map.removeLayer(activeLayers[filename]);
                }

                const chk = document.getElementById('chk_' + filename);
                if (!chk || chk.checked) {
                    layer.addTo(map);
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

        // Query all THREE primary VIIRS satellites over 2 days
        const sources = ['VIIRS_SNPP_NRT', 'VIIRS_NOAA20_NRT', 'VIIRS_NOAA21_NRT'];

            try {
            // Fire off all API requests simultaneously
            const fetchPromises = sources.map(source =>
                    fetch(`/api/firms/${source}/${bbox}`)
                );

                const responses = await Promise.all(fetchPromises);

                let allRows = [];
                let headers = [];

                for (const response of responses) {
                    if (!response.ok) throw new Error("API limits reached or invalid area.");

                    const csvText = await response.text();
                    const rows = csvText.split('\n').filter(row => row.trim() !== '');

                    // If we have more than just the header row
                    if (rows.length > 1) {
                        if (headers.length === 0) {
                            headers = rows.shift().split(','); // Keep headers from the first file
                        } else {
                        rows.shift(); // Discard headers from subsequent files
                        }
                        allRows.push(...rows); // Merge the data
                    }
                }

                if (allRows.length === 0) {
                    currentFirmsData = [];
                    firmsVectorGroup.clearLayers();
                    statusEl.textContent = 'No thermal anomalies in this specific view.';
                    statusEl.style.color = '#94a3b8';
                    return;
                }

                // Parse our newly combined massive dataset
                currentFirmsData = allRows.map(row => {
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

                fireCircle.bindPopup(`
                    <b>Thermal Anomaly</b><br>
                    Detected: ${fire.acq_date} at ${timeStr} UTC<br>
                    Age: ${Math.round(ageHours)} hours ago<br>
                    Confidence: ${fire.confidence}
                `);

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
            for (const filename in activeLayers) {
                const d = extractDateFromFilename(filename);
                if (d) datesSet.add(d);
            }

            availableDates = Array.from(datesSet).sort();
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

        document.getElementById('timelineSlider').addEventListener('input', (e) => {
            if (availableDates.length === 0) return;
            const idx = e.target.value;
            const selectedDate = availableDates[idx];
            document.getElementById('currentDateDisplay').textContent = selectedDate;

            // Toggle layer map visibility AND UI list visibility
            for (const filename in activeLayers) {
                const layerDate = extractDateFromFilename(filename);

                // Find the UI container for this layer
                const chk = document.getElementById('chk_' + filename);
                const layerItemDiv = chk ? chk.closest('.layer-item') : null;

                // If it matches the current timeline date (or lacks a parsable date)
                if (!layerDate || layerDate === selectedDate) {
                    if (layerItemDiv) layerItemDiv.style.display = 'flex'; // Show in UI list

                    const isChecked = chk?.checked;
                    if (isChecked && !map.hasLayer(activeLayers[filename])) {
                        map.addLayer(activeLayers[filename]);
                    }
                } else {
                    if (layerItemDiv) layerItemDiv.style.display = 'none'; // Hide from UI list

                    if (map.hasLayer(activeLayers[filename])) {
                        map.removeLayer(activeLayers[filename]);
                    }
                }
            }

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
        map.on('click', async function(e) {
            // Suppress Location Intelligence popup if a measurement tool is active
            if (window.currentTool && (window.currentTool === 'ruler' || window.currentTool === 'circle')) {
                return;
            }

            const lat = e.latlng.lat;
            const lng = e.latlng.lng;
            const estimates = calculatePassEstimates(lng);

            // Create a loading popup
            let popupContent = `
                <div style="min-width: 220px;">
                    <h3 style="margin: 0 0 8px 0; border-bottom: 1px solid #475569; padding-bottom: 4px;">Location Intelligence</h3>
                    <p style="margin: 4px 0; font-size: 0.85rem;"><b>Lat:</b> ${lat.toFixed(4)}<br><b>Lng:</b> ${lng.toFixed(4)}</p>

                    <h4 style="margin: 10px 0 4px 0; color: #93c5fd;">🛰️ Estimated Daily Passes</h4>
                    <ul style="margin: 0; padding-left: 20px; font-size: 0.85rem;">
                        <li><b>Sentinel-2:</b> ~${estimates.sentinel}</li>
                        <li><b>FIRMS (VIIRS):</b> ~${estimates.viirs}</li>
                    </ul>
                    <em style="font-size: 0.75rem; color: #94a3b8;">*Sun-synchronous estimates based on longitude. High latitudes (e.g. Ukraine) receive multiple overlapping swath looks.</em>

                    <div id="wmsInfo" style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #475569; display: none;">
                        <h4 style="margin: 0 0 4px 0; color: #22c55e;">📸 Sentinel Image Data</h4>
                        <div id="wmsLoading">Querying Copernicus...</div>
                    </div>
                </div>
            `;

            const popup = L.popup()
                .setLatLng(e.latlng)
                .setContent(popupContent)
                .openOn(map);

            // If the Sentinel layer is currently active on the map, fetch the image date
            if (map.hasLayer(layers.sentinelLive) && map.getZoom() > 9) {
                document.getElementById('wmsInfo').style.display = 'block';

                const url = getFeatureInfoUrl(map, layers.sentinelLive, e.latlng);

                try {
                    const response = await fetch(url);
                    if (!response.ok) throw new Error("Network response was not ok");

                    const data = await response.json();

                    if (data && data.features && data.features.length > 0) {
                        // Sentinel Hub returns the date in the properties object
                        const date = data.features[0].properties.date || "Date unknown";
                        const time = data.features[0].properties.time || "";
                        document.getElementById('wmsLoading').innerHTML = `
                            <b>Acquired:</b> ${date} ${time} UTC
                        `;
                    } else {
                        document.getElementById('wmsLoading').innerHTML = `<em style="color: #94a3b8;">No image metadata found for this pixel.</em>`;
                    }
                } catch (error) {
                    console.error("WMS GetFeatureInfo Error:", error);
                    document.getElementById('wmsLoading').innerHTML = `<em style="color: #ef4444;">Failed to retrieve image data.</em>`;
                }
            }
        });
        async function loadSettingsAndInit() {
            try {
                const response = await fetch('/api/settings');
                appSettings = await response.json();

                layerStyles = appSettings.layerStyles || {};

                // Apply default map settings if available
                const defaultLat = appSettings.defaultLat ?? 49.0;
                const defaultLng = appSettings.defaultLng ?? 31.0;
                const defaultZoom = appSettings.defaultZoom ?? 6;
                map.setView([defaultLat, defaultLng], defaultZoom);

                const defaultBasemap = appSettings.defaultBasemap ?? 'dark';
                const radioInput = document.querySelector(`input[name="basemap"][value="${defaultBasemap}"]`);
                if (radioInput) radioInput.checked = true;

                if (baseMaps[defaultBasemap]) {
                    baseMaps[defaultBasemap].addTo(map);
                } else {
                    baseMaps.dark.addTo(map);
                }

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
