

function toggleSection(header) {
            const content = header.nextElementSibling;
            const sectionName = header.innerText.trim();
            const isOpening = content.classList.contains('collapsed'); // Check content, not header!

            // 1. Toggle ONLY the content
            content.classList.toggle('collapsed');
            header.querySelector('.toggle-icon').innerText = isOpening ? '▼' : '▶';

            // 2. Auto-close logic
            if (isOpening) {
                const allHeaders = document.querySelectorAll('.section-header');
                allHeaders.forEach(h => {
                    const name = h.innerText.trim();
                    if (h === header) return;

                    let shouldClose = false;
                    if (sectionName.includes('Front Line') && name.includes('Static')) shouldClose = true;
                    if (sectionName.includes('Map Admin') && (name.includes('Front Line') || name.includes('Base Map') || name.includes('Static'))) shouldClose = true;

                    if (shouldClose) {
                        h.nextElementSibling.classList.add('collapsed'); // Hide content
                        h.querySelector('.toggle-icon').innerText = '▶'; // Reset arrow
                    }
                });

                // If opening Front Line Tracker, preload a few layers
                if (sectionName.includes('Front Line')) {
                    if (window.availableDates && window.availableDates.length > 0) {
                        const slider = document.getElementById('timelineSlider');
                        if (slider) {
                            slider.dispatchEvent(new Event('input'));
                        }
                    }
                }
            }
        }
        // 2. Base Maps Setup
	    const esriAttr = 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community';
        const eoxAttr = '<a href="https://s2maps.eu" target="_blank">Sentinel-2 cloudless - https://s2maps.eu</a> by <a href="https://eox.at" target="_blank">EOX IT Services GmbH</a> (Contains modified Copernicus Sentinel data 2022 & 2023)';
        // Sentinel hub
        const localSentinelWMS = "/api/sentinel";




        // 1. Initialise the Map
        // Parse URL parameters for initialization
        const urlParams = new URLSearchParams(window.location.search);

        let initialZoom = 6;
        let initialLat = 49.0;
        let initialLng = 31.0;
        let urlSetLocation = false;

        if (urlParams.has('zoom')) { initialZoom = parseInt(urlParams.get('zoom')); urlSetLocation = true; }
        if (urlParams.has('lat')) { initialLat = parseFloat(urlParams.get('lat')); urlSetLocation = true; }
        if (urlParams.has('lng')) { initialLng = parseFloat(urlParams.get('lng')); urlSetLocation = true; }

        window.urlSetLocation = urlSetLocation;

        const map = L.map('map', { zoomControl: false, zoomSnap: 0.1, zoomDelta: 0.5, center: [initialLat, initialLng], zoom: initialZoom });


        L.control.zoom({ position: 'bottomright' }).addTo(map);
        L.control.scale({ position: 'bottomleft', imperial: true, metric: true }).addTo(map);
        window.map = map; // Expose map globally for other scripts

        // --- MiniMap Setup ---
        // A single minimap basemap using the specified dark OpenFreeMap tiles
        window.minimapLayer = L.maplibreGL({
            style: 'https://tiles.openfreemap.org/styles/liberty',
            attribution: '<a href="https://openfreemap.org/" target="_blank">OpenFreeMap</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> Data from <a href="https://openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
            maplibreLogo: true,
            preserveDrawingBuffer: true
        });

        const minimapLayer = window.minimapLayer; // Keep local ref for rest of function


        minimapLayer.on('add', function() {
            const glMap = this.getMaplibreMap();
            glMap.once('load', function() {
                                if (glMap.getLayer('boundary_state')) {
                    glMap.setLayoutProperty('boundary_state', 'visibility', 'none');
                }
                if (glMap.getLayer('place_state')) {
                    glMap.setLayoutProperty('place_state', 'visibility', 'none');
                }
            });
        });

        const miniMap = new L.Control.MiniMap(minimapLayer, {
            position: 'bottomleft',
            zoomLevelFixed: 4,
            toggleDisplay: true,
            minimized: false,
            width: 200,
            height: 150
        }).addTo(map);
        window.miniMap = miniMap;

        // --- NEW CUSTOM PANE FIX ---
        map.createPane('hybridLabels');
        map.getPane('hybridLabels').style.zIndex = 250; // Sits above satellite (200) but below KMLs (400)
        map.getPane('hybridLabels').style.pointerEvents = 'none'; // Ensures clicks pass through to your KMLs!
        // ---------------------------

        const activeLayers = {};

            // Settings from backend
        let appSettings = {};
        let layerStyles = {};
        let currentStylingLayer = null;



		    // Individual Layers
		window.currentCacheBuster = null;
		window.currentSentinelFeatures = [];

        const layers = {
            openFreeDark: L.maplibreGL({
                style: 'https://tiles.openfreemap.org/styles/dark',
                attribution: '<a href="https://openfreemap.org/" target="_blank">OpenFreeMap</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> Data from <a href="https://openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
                preserveDrawingBuffer: true
            }),
            openFreeLight: L.maplibreGL({
                style: 'https://tiles.openfreemap.org/styles/liberty',
                attribution: '<a href="https://openfreemap.org/" target="_blank">OpenFreeMap</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> Data from <a href="https://openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
                preserveDrawingBuffer: true
            }),

            esriSatellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: esriAttr
            }),
            esriFirefly: L.tileLayer('https://fly.maptiles.arcgis.com/arcgis/rest/services/World_Imagery_Firefly/MapServer/tile/{z}/{y}/{x}', {
                attribution: esriAttr
            }),
            sentinel2: L.tileLayer('https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2023_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg', {
                attribution: eoxAttr
            }),
            sentinel2Grayscale: L.tileLayer('https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2023_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg', {
                attribution: eoxAttr,
                className: 'grayscale-tile'
            }),
            // Transparent overlays for Hybrid views
            roads: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}', {
                pane: 'hybridLabels'
            }),
            labels: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
                pane: 'hybridLabels'

            }),

            // Modern Vector Labels (Transparent Overlay via OpenFreeMap)
            vectorLabels: L.maplibreGL({
                style: 'https://tiles.openfreemap.org/styles/liberty',
                attribution: '<a href="https://openfreemap.org/" target="_blank">OpenFreeMap</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> Data from <a href="https://openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
                pane: 'hybridLabels',
                interactive: false
            }),

            topo: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
                attribution: 'Map data: &copy; <a href="https://openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href="https://opentopomap.org/" target="_blank">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank">CC-BY-SA</a>)'
            }),
            hot: L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors, <a href="https://hotosm.org" target="_blank">Humanitarian OpenStreetMap Team</a>'
            }),

            // NASA GIBS MODIS (Daily, 250m) - Good for global/regional overview
            modisDaily: L.tileLayer('https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg', {
                attribution: 'NASA Global Imagery Browse Services (GIBS)',
                tileSize: 256
            }),

            // NASA GIBS Sentinel-2 (NRT, 10m) - Good for high-res detail
            sentinelNRT: L.tileLayer('https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/Sentinel-2_L2A_CorrectedReflectance_TrueColor/default/GoogleMapsCompatible_Level12/{z}/{y}/{x}.jpg', {
                attribution: 'NASA GIBS / Copernicus Sentinel-2',
                tileSize: 256
            }),
            sentinelLive: L.tileLayer.wms(localSentinelWMS, {
                layers: 'TRUE-COLOR-S2L2A', // Your specific Layer ID
                format: 'image/png',
                transparent: true,
                maxcc: 20, // Only show images with < 20% cloud cover
                attribution: '&copy; <a href="https://dataspace.copernicus.eu/" target="_blank">Copernicus Sentinel data 2026</a>',
                tileSize: 512, // Sentinel Hub works better with larger tiles
                zIndex: 10
            }),

            sentinelNatural: L.tileLayer.wms(localSentinelWMS, {
                layers: 'NATURAL-COLOR',
                format: 'image/png',
                transparent: true,
                maxcc: 20,
                attribution: '&copy; <a href="https://dataspace.copernicus.eu/" target="_blank">Copernicus Sentinel data 2026</a>',
                tileSize: 512,
                zIndex: 10
            }),
			sentinelLayer: L.tileLayer('/api/sentinel-latest/{z}/{x}/{y}.webp', {
    			tileSize: 512,
				minZoom: 11,
				maxNativeZoom: 15,
				maxZoom: 22,
    			attribution: '&copy; <a href="https://dataspace.copernicus.eu/" target="_blank">Copernicus Sentinel data 2026</a>',
				zIndex: 10,
				zoomOffset: -1
			}),

			footprintLayer: L.geoJSON(null, {
			    style: {
			        color: "#facc15",
			        weight: 2,
			        fillOpacity: 0.05,
			        dashArray: '5, 5'
			    },
			    interactive: false
			}),
			
		//topography: L.tileLayer('/api/dynamic-topo/{z}/{x}/{y}.png', {
            //	attribution: 'Elevation data &copy; Copernicus',
            //	opacity: 0.8, // Slight transparency looks great over a dark base map
            //	maxNativeZoom: 14 // DEM data gets blurry past zoom 14, this scales it smoothly
	        //})
        };




        // ----------------------------------------
        // --- The Hybrid Live Satellite Logic ---
        // Swaps from MODIS to Sentinel automatically based on zoom
        // const liveSatelliteHybrid = L.layerGroup();





                // Grouped Options for the UI
        const baseMaps = {
            dark: layers.openFreeDark,
            light: layers.openFreeLight,
            satellite: layers.esriSatellite,
            satellitehybrid: L.layerGroup([layers.esriSatellite, layers.vectorLabels]),
            firefly: layers.esriFirefly,
            fireflyhybrid: L.layerGroup([layers.esriFirefly, layers.vectorLabels]),
            s2cloud: layers.sentinel2,
            s2cloudhybrid: L.layerGroup([layers.sentinel2, layers.vectorLabels]),
	        s2tc: layers.sentinelLive,
            s2tchybrid: L.layerGroup([layers.sentinelLive, layers.vectorLabels]),
	        s2nc: layers.sentinelNatural,
            s2nchybrid: L.layerGroup([layers.sentinelNatural, layers.vectorLabels]),
            topo: layers.topo,
            hot: layers.hot,
        };

        // Define dynamic layer groups that only add sentinelLayer when zoom >= 11
        // This prevents Leaflet from forcing the map's minZoom to 11.
        function createDynamicSentinelGroup(baseLayers) {
            const group = L.layerGroup(baseLayers);

            function updateDynamicLayer() {
                if (!map.hasLayer(group)) return;
                if (map.getZoom() >= 11) {
                    if (!group.hasLayer(layers.sentinelLayer)) group.addLayer(layers.sentinelLayer);
                } else {
                    if (group.hasLayer(layers.sentinelLayer)) group.removeLayer(layers.sentinelLayer);
                }
            }

            group.on('add', () => {
                map.on('zoomend', updateDynamicLayer);
                updateDynamicLayer();
            });

            group.on('remove', () => {
                map.off('zoomend', updateDynamicLayer);
                if (group.hasLayer(layers.sentinelLayer)) group.removeLayer(layers.sentinelLayer);
            });

            return group;
        }

        baseMaps.s2latest = createDynamicSentinelGroup([layers.sentinel2Grayscale]);
        baseMaps.s2latesthybrid = createDynamicSentinelGroup([layers.sentinel2Grayscale, layers.vectorLabels]);

        // Add loading indicator events to sentinelLayer
        layers.sentinelLayer.on('tileloadstart', function(e) {
            e.tile.classList.add('sentinel-loading');
            e.tile.title = "Fetching imagery...";
        });

        layers.sentinelLayer.on('tileload', function(e) {
            e.tile.classList.remove('sentinel-loading');
            e.tile.removeAttribute('title');
        });

        layers.sentinelLayer.on('tileerror', function(e) {
            e.tile.classList.remove('sentinel-loading');
            e.tile.title = "Failed to load imagery";
        });

                // --- THIS IS THE NEW TRANSPARENCY FIX ---
        // Listen for Leaflet adding the layer to the map
        layers.vectorLabels.on('add', function() {
            const glMap = this.getMaplibreMap();

            // Wait for MapLibre to finish drawing its default solid map
            glMap.once('load', function() {
                const style = glMap.getStyle();
                if (!style || !style.layers) return;

                style.layers.forEach(layer => {
                    // 1. Hide the solid backgrounds
                    if (layer.type === 'background' || layer.type === 'fill' || layer.id.includes('water') || layer.id.includes('land') || layer.id.includes('building')) {
                        glMap.setLayoutProperty(layer.id, 'visibility', 'none');
                    }

                    // 2. Make text white with a dark outline
                    if (layer.type === 'symbol' && layer.layout && layer.layout['text-field']) {
                        glMap.setPaintProperty(layer.id, 'text-color', '#ffffff');
                        glMap.setPaintProperty(layer.id, 'text-halo-color', '#000000');
                        glMap.setPaintProperty(layer.id, 'text-halo-width', 2);
                    }

                    // 3. Make the roads translucent white
                    if (layer.type === 'line' && (layer.id.includes('road') || layer.id.includes('highway') || layer.id.includes('bridge') || layer.id.includes('tunnel'))) {
                        glMap.setPaintProperty(layer.id, 'line-color', '#ffffff');
                        glMap.setPaintProperty(layer.id, 'line-opacity', 0.4);
                    }
                });
            });
        });


        // Add default

        // Handle URL parameter basemap overriding
        if (urlParams.has('basemap')) {
            const requestedBasemap = urlParams.get('basemap');
            if (baseMaps[requestedBasemap]) {
                setTimeout(() => {
                    const radio = document.querySelector(`input[name="basemap"][value="${requestedBasemap}"]`);
                    if (radio) {
                        radio.checked = true;
                    }
                }, 500);
                baseMaps[requestedBasemap].addTo(map);
            } else {
                baseMaps.dark.addTo(map);
            }
        } else {
            baseMaps.dark.addTo(map);
        }


        // Radio button listener
        document.querySelectorAll('input[name="basemap"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                baseMaps[e.target.value].addTo(map);
            });
        });

                // --- 3. Location Search (Geocoder) ---
        const geocoder = L.Control.geocoder({
            defaultMarkGeocode: false,
            placeholder: "Search location...",
            collapsed: true,
            position: 'topright'
        })
        .on('markgeocode', function(e) {
            const bbox = e.geocode.bbox;
            const poly = L.polygon([
                bbox.getSouthEast(),
                bbox.getNorthEast(),
                bbox.getNorthWest(),
                bbox.getSouthWest()
            ]);
            map.fitBounds(poly.getBounds());

            // Optional: Drop a temporary marker at search result
            //L.marker(e.geocode.center).addTo(map)
            //    .bindPopup(e.geocode.name)
            //    .openPopup();
        })
        .addTo(map);
        // Native Leaflet Control for the Hamburger Button
        const HamburgerControl = L.Control.extend({
            options: { position: 'topright' },
            onAdd: function () {
                const div = L.DomUtil.create('div', 'hamburger-btn');
                div.innerHTML = '☰';
                div.title = "Toggle Map Controls";

                L.DomEvent.disableClickPropagation(div);

                div.onclick = function() {
                    document.getElementById('controlPanel').classList.toggle('open');
                };
                return div;
            }
        });
        map.addControl(new HamburgerControl());

        // Native Leaflet Control for the Share Button
        const ShareControl = L.Control.extend({
            options: { position: 'topright' },
            onAdd: function () {
                const div = L.DomUtil.create('div', 'share-btn');
                div.innerHTML = '🔗';
                div.title = "Share Map";

                L.DomEvent.disableClickPropagation(div);

                div.onclick = function() {
                    if (window.shareMap) {
                        window.shareMap();
                    }
                };
                return div;
            }
        });
        map.addControl(new ShareControl());


        window.shareMap = async function() {
            const center = map.getCenter();
            const zoom = map.getZoom();

            const activeBasemapEl = document.querySelector('input[name="basemap"]:checked');
            const basemap = activeBasemapEl ? activeBasemapEl.value : 'dark';

            let activeLayerKeys = [];
            const listItems = document.querySelectorAll('.layer-item');
            listItems.forEach(item => {
                const fn = item.dataset.filename;
                const chk = document.getElementById('chk_' + fn);
                if (chk && chk.checked && item.style.display !== 'none') {
                    activeLayerKeys.push(fn);
                }
            });

            const dateDisplay = document.getElementById('currentDateDisplay');
            const date = dateDisplay ? dateDisplay.textContent : '';

            const url = new URL(window.location.origin + window.location.pathname);
            url.searchParams.set('lat', center.lat.toFixed(4));
            url.searchParams.set('lng', center.lng.toFixed(4));
            url.searchParams.set('zoom', zoom);
            url.searchParams.set('basemap', basemap);
            if (activeLayerKeys.length > 0) {
                 url.searchParams.set('layers', activeLayerKeys.join(','));
            }
            if (date) url.searchParams.set('date', date);

            const shareUrl = url.toString();

            document.body.style.cursor = 'wait';

            try {
                // Ensure leaflet map panes have transform reset to capture correctly
                const mapPanes = document.querySelectorAll('.leaflet-pane');
                const origTransforms = [];
                mapPanes.forEach((pane) => {
                     origTransforms.push(pane.style.transform);
                     const match = pane.style.transform.match(/translate3d\((.*?)px,\s*(.*?)px/);
                     if (match) {
                         pane.style.left = match[1] + 'px';
                         pane.style.top = match[2] + 'px';
                     }
                     pane.style.transform = 'none';
                });
                const canvas = await html2canvas(document.body, {
                    useCORS: true,
                    allowTaint: false,
                    backgroundColor: '#1a1a1a',
                    onclone: function(clonedDoc) {
                        const glMapLayer = document.querySelector('.maplibregl-canvas');
                        if (glMapLayer) {
                            const clonedGlMapLayer = clonedDoc.querySelector('.maplibregl-canvas');
                            if (clonedGlMapLayer) {
                                // Provide image copy directly if needed.
                                const dataUrl = glMapLayer.toDataURL();
                                const img = clonedDoc.createElement('img');
                                img.src = dataUrl;
                                img.style.position = 'absolute';
                                img.style.width = '100%';
                                img.style.height = '100%';
                                img.style.zIndex = clonedGlMapLayer.style.zIndex;
                                clonedGlMapLayer.parentNode.replaceChild(img, clonedGlMapLayer);
                            }
                        }
                    },
                    ignoreElements: (element) => {
                        return element.id === 'shareModal' || (element.classList && element.classList.contains('leaflet-control-container'));
                    }
                });


                // Restore transforms
                mapPanes.forEach((pane, i) => {
                     pane.style.transform = origTransforms[i];
                     pane.style.left = '';
                     pane.style.top = '';
                });

                const imgData = canvas.toDataURL('image/png');

                const modal = document.getElementById('shareModal');
                const imgPreview = document.getElementById('shareImagePreview');
                const urlInput = document.getElementById('shareUrlInput');

                imgPreview.src = imgData;
                urlInput.value = shareUrl;

                modal.style.display = 'flex';
            } catch (err) {
                console.error("Failed to generate map snapshot", err);
                alert("Failed to generate snapshot. You can still copy the URL: " + shareUrl);
            } finally {
                document.body.style.cursor = 'default';
            }
        };
