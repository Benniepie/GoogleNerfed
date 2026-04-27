

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
            }
        }
        // 2. Base Maps Setup
	    const esriAttr = 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community';
        const eoxAttr = '<a href="https://s2maps.eu" target="_blank">Sentinel-2 cloudless - https://s2maps.eu</a> by <a href="https://eox.at" target="_blank">EOX IT Services GmbH</a> (Contains modified Copernicus Sentinel data 2022 & 2023)';
        // Sentinel hub
        const localSentinelWMS = "/api/sentinel";




        // 1. Initialise the Map
        const map = L.map('map', { zoomControl: false, zoomSnap: 0.25, zoomDelta: 0.25 }).setView([49.0, 31.0], 6); // Default view centered on Ukraine
        L.control.zoom({ position: 'bottomright' }).addTo(map);
        L.control.scale({ position: 'bottomleft', imperial: true, metric: true }).addTo(map);
        window.map = map; // Expose map globally for other scripts

        // --- MiniMap Setup ---
        // A single minimap basemap using the specified dark OpenFreeMap tiles
        window.minimapLayer = L.maplibreGL({
            style: 'https://tiles.openfreemap.org/styles/liberty',
            attribution: '<a href="https://openfreemap.org/" target="_blank">OpenFreeMap</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> Data from <a href="https://openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'
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
        const layers = {
            openFreeDark: L.maplibreGL({
                style: 'https://tiles.openfreemap.org/styles/dark',
                attribution: '<a href="https://openfreemap.org/" target="_blank">OpenFreeMap</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> Data from <a href="https://openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'
            }),
            openFreeLight: L.maplibreGL({
                style: 'https://tiles.openfreemap.org/styles/liberty',
                attribution: '<a href="https://openfreemap.org/" target="_blank">OpenFreeMap</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> Data from <a href="https://openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'
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
    			attribution: '&copy; <a href="https://dataspace.copernicus.eu/" target="_blank">Copernicus Sentinel data 2026</a>',
				zIndex: 10,
				zoomOffset: -1
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
        const liveSatelliteHybrid = L.layerGroup();

        map.on('zoomend', function() {
            if (map.hasLayer(liveSatelliteHybrid)) {
                liveSatelliteHybrid.clearLayers();
                if (map.getZoom() > 9) {
                    liveSatelliteHybrid.addLayer(layers.sentinelNRT);
                } else {
                    liveSatelliteHybrid.addLayer(layers.modisDaily);
                }
                // Always add labels and roads over live satellite
                liveSatelliteHybrid.addLayer(layers.roads);
                liveSatelliteHybrid.addLayer(layers.labels);
            }
        });



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
            liveSat: liveSatelliteHybrid,
			s2latest: layers.sentinelLayer,
        };

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
        baseMaps.dark.addTo(map);

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



        // Handle Base Map Switching
        document.querySelectorAll('input[name="basemap"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                // Clear all active base layers and hybrid groups safely
                Object.values(baseMaps).forEach(layer => {
                    if (map.hasLayer(layer)) {
                        map.removeLayer(layer);
                    }
                });

                // Add the newly selected map option
                baseMaps[e.target.value].addTo(map);
                // --- THE ALIGNMENT FIX ---
                // Wait 50ms for the new MapLibre canvas to be injected into the DOM
                setTimeout(() => {
                    // Force Leaflet to recalculate container sizes
                    map.invalidateSize();
                    // Give the map a microscopic, invisible 1-pixel jiggle to force MapLibre to sync!
                    map.panBy([1, 0], { animate: false });
                    map.panBy([-1, 0], { animate: false });
                }, 50);

            });
        });


		// // --- Topography Legend ---
        // const topoLegend = L.control({ position: 'bottomright' });

        // topoLegend.onAdd = function (map) {
        //     const div = L.DomUtil.create('div', 'info legend');
        //     // Create a CSS gradient block that matches our 'cfastie' Titiler colormap
        //     div.innerHTML = `
        //         <div style="background: rgba(30, 30, 35, 0.85); padding: 10px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1); color: white; font-size: 12px; backdrop-filter: blur(12px);">
        //             <h4 style="margin: 0 0 5px 0; border-bottom: 1px solid #475569; padding-bottom: 3px;">Elevation</h4>
        //             <div style="display: flex;">
        //                 <div style="background: linear-gradient(to top, #0000ff, #00ffff, #00ff00, #ffff00, #ff0000, #ffffff); width: 15px; height: 150px; border-radius: 3px; margin-right: 10px;"></div>
        //                 <div style="display: flex; flex-direction: column; justify-content: space-between; height: 150px;">
        //                     <span>1500m+</span>
        //                     <span>1200m</span>
        //                     <span>900m</span>
        //                     <span>600m</span>
        //                     <span>300m</span>
        //                     <span>0m</span>
        //                 </div>
        //             </div>
        //         </div>
        //     `;
        //     return div;
        // };

        // // Only show the legend when the topography layer is active
        // map.on('layeradd', function(event) {
        //     if (event.layer === layers.topography) {
        //         topoLegend.addTo(map);
        //     }
        // });

        // map.on('layerremove', function(event) {
        //     if (event.layer === layers.topography) {
        //         map.removeControl(topoLegend);
        //     }
        // });


// Dynamic MiniMap Resizing based on screen aspect ratio
function resizeMiniMap() {
    if (!window.miniMap) return;

    // If the minimap is minimized, don't force our custom responsive dimensions
    if (window.miniMap._minimized) {
        return; // Let the leaflet-minimap plugin handle the minimized dimensions
    }

    // We want it to be small enough not to get in the way.
    const baseWidthVW = 15;
    const minWidth = 120;
    const maxWidth = 300;

    let targetWidth = (window.innerWidth * baseWidthVW) / 100;
    targetWidth = Math.max(minWidth, Math.min(maxWidth, targetWidth));

    // Calculate aspect ratio
    const ratio = window.innerHeight / window.innerWidth;
    const targetHeight = targetWidth * ratio;

    // Update the miniMap plugin's internal size settings so transitions restore properly
    window.miniMap.options.width = targetWidth;
    window.miniMap.options.height = targetHeight;

    // Update the miniMap container size
    const container = window.miniMap._container;
    if (container) {
        container.style.width = targetWidth + 'px';
        container.style.height = targetHeight + 'px';

        // When restoring from minimize, there's a CSS transition.
        // We need to invalidate size *after* the container has reached its final state.
        // We'll run it immediately (for normal window resize) AND after 350ms (transition duration).
        const triggerMapResize = () => {
            if (window.miniMap._miniMap) {
                window.miniMap._miniMap.invalidateSize();

                // Force maplibre map to resize if present globally
                if (window.minimapLayer && window.minimapLayer.getMaplibreMap) {
                    const glMap = window.minimapLayer.getMaplibreMap();
                    if (glMap) {
                        glMap.resize();
                    }
                }
            }
        };

        setTimeout(triggerMapResize, 10);
        setTimeout(triggerMapResize, 400); // 400ms is a safe buffer for CSS transitions
    }
}

// Ensure the minimap catches up with its container right after being added to the map.
if (window.miniMap) {
    window.miniMap.on('toggle', function() {
        setTimeout(resizeMiniMap, 50);
    });
}

// Call on load and on resize
window.addEventListener('resize', resizeMiniMap);
// Wait a bit for the control to be fully added and rendered
setTimeout(resizeMiniMap, 100);
setTimeout(resizeMiniMap, 500); // extra safety net for initial load
