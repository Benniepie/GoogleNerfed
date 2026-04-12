// State for measurement tools
window.currentTool = null; // 'ruler', 'circle', or null
let measureLayerGroup = null; // LayerGroup to hold all measurements
let currentDrawLayer = null; // The temporary layer being drawn
let points = []; // Store coordinates for current drawing
let mouseMovePoint = null;
let currentTooltip = null; // Temporary tooltip for dynamic measurement text

function initMeasureTools() {
    if (!window.map) {
        setTimeout(initMeasureTools, 100);
        return;
    }

    measureLayerGroup = L.layerGroup().addTo(window.map);

    // CSS for interactive popup styles and selected buttons
    const style = document.createElement('style');
    style.innerHTML = `
        .measure-btn.active {
            background-color: rgba(59, 130, 246, 0.5); /* accent-color with opacity */
            border-radius: 4px;
            color: white;
        }
        .measure-popup-content {
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 0.9rem;
            color: #e2e8f0;
        }
        .measure-popup-controls {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 5px;
            border-top: 1px solid rgba(255,255,255,0.1);
            padding-top: 5px;
        }
        .measure-popup-controls input[type="color"] {
            cursor: pointer;
            width: 25px;
            height: 25px;
            padding: 0;
            border: none;
            background: none;
        }
        .measure-popup-controls input[type="range"] {
            width: 60px;
        }
        .measure-tooltip {
            background: rgba(0, 0, 0, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white;
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 4px;
        }
        /* Suppress pointer events on existing vector layers when measuring */
        .is-measuring .leaflet-interactive {
            pointer-events: none !important;
        }
        /* Ensure finished measurement layers remain interactable to allow opening their popups and editing */
        .is-measuring .measure-interactive {
            pointer-events: auto !important;
        }
    `;
    document.head.appendChild(style);

    // Add map event listeners
    window.map.on('click', onMapClick);
    window.map.on('mousemove', onMapMouseMove);
    window.map.on('dblclick', onMapDblClick);
}

function toggleMeasureTool(toolName) {
    if (window.currentTool === toolName) {
        disableMeasureTools();
    } else {
        disableMeasureTools();
        window.currentTool = toolName;
        document.getElementById(`${toolName}Btn`).classList.add('active');
        window.map.getContainer().style.cursor = 'crosshair';
        window.map.doubleClickZoom.disable();
        // Add class to map container to suppress interactions with other layers
        window.map.getContainer().classList.add('is-measuring');
    }
}

function disableMeasureTools() {
    if (currentDrawLayer) {
        window.map.removeLayer(currentDrawLayer);
        currentDrawLayer = null;
    }
    if (currentTooltip) {
        window.map.removeLayer(currentTooltip);
        currentTooltip = null;
    }
    window.currentTool = null;
    points = [];
    mouseMovePoint = null;

    document.getElementById('rulerBtn').classList.remove('active');
    document.getElementById('circleBtn').classList.remove('active');
    if (window.map) {
        window.map.getContainer().style.cursor = '';
        window.map.doubleClickZoom.enable();
        // Remove class to restore interactions
        window.map.getContainer().classList.remove('is-measuring');
    }
}

function onMapClick(e) {
    if (!window.currentTool) return;

    const latlng = e.latlng;
    const clickPt = window.map.latLngToContainerPoint(latlng);

    if (window.currentTool === 'ruler') {
        if (points.length > 0) {
            // Deduplicate points (ignore rapid double clicks or microscopic mouse movements)
            const lastPt = window.map.latLngToContainerPoint([points[points.length-1][1], points[points.length-1][0]]);
            const distFromLastPx = Math.sqrt(Math.pow(clickPt.x - lastPt.x, 2) + Math.pow(clickPt.y - lastPt.y, 2));

            // If click is within 5 pixels of the last point, ignore it completely to prevent double click bugs
            if (distFromLastPx <= 5) {
                return;
            }

            // Check if we clicked near the start point to close a polygon
            if (points.length >= 3) { // Require at least a triangle before allowing closing
                const startPt = window.map.latLngToContainerPoint([points[0][1], points[0][0]]);
                const distFromStartPx = Math.sqrt(Math.pow(clickPt.x - startPt.x, 2) + Math.pow(clickPt.y - startPt.y, 2));

                // If click is within 15 pixels of the start point, close the polygon and finish
                if (distFromStartPx <= 15) {
                    // Snap final point to exactly the first point
                    points.push([...points[0]]);
                    finishRuler();
                    return;
                }
            }
        }

        points.push([latlng.lng, latlng.lat]);
        updateRulerDrawing();
    } else if (window.currentTool === 'circle') {
        if (points.length === 0) {
            // First click: center
            points.push([latlng.lng, latlng.lat]);
        } else {
            // Second click: outer perimeter
            finishCircle(latlng);
        }
    }
}

function onMapMouseMove(e) {
    if (!window.currentTool || points.length === 0) return;
    mouseMovePoint = [e.latlng.lng, e.latlng.lat];

    if (window.currentTool === 'ruler') {
        updateRulerDrawing();
    } else if (window.currentTool === 'circle') {
        updateCircleDrawing();
    }
}

function onMapDblClick(e) {
    if (window.currentTool === 'ruler') {
        L.DomEvent.stopPropagation(e);
        if (points.length > 1) {
            finishRuler();
        }
    }
}

function updateRulerDrawing() {
    if (currentDrawLayer) {
        window.map.removeLayer(currentDrawLayer);
        currentDrawLayer = null;
    }
    if (currentTooltip) {
        window.map.removeLayer(currentTooltip);
        currentTooltip = null;
    }

    const drawPoints = [...points];
    if (mouseMovePoint) {
        drawPoints.push(mouseMovePoint);
    }

    if (drawPoints.length > 1) {
        const line = turf.lineString(drawPoints);
        currentDrawLayer = L.geoJSON(line, {
            style: { color: 'red', weight: 2, dashArray: '5, 5' },
            interactive: false
        }).addTo(window.map);

        if (points.length > 0 && mouseMovePoint) {
            const lastPoint = turf.point(points[points.length - 1]);
            const currentPoint = turf.point(mouseMovePoint);
            const currentLegDistance = turf.distance(lastPoint, currentPoint, {units: 'kilometers'});

            currentTooltip = L.tooltip({
                permanent: true,
                direction: 'right',
                className: 'measure-tooltip'
            })
            .setContent(formatLength(currentLegDistance))
            .setLatLng([mouseMovePoint[1], mouseMovePoint[0]])
            .addTo(window.map);
        }
    }
}

function formatLength(km) {
    if (km < 1) {
        return `${(km * 1000).toFixed(2)} m`;
    }
    return `${km.toFixed(2)} km`;
}

function formatArea(sqKm) {
    if (sqKm < 1) {
        return `${(sqKm * 1000000).toFixed(2)} m²`;
    }
    return `${sqKm.toFixed(2)} km²`;
}

function updateCircleDrawing() {
    if (currentDrawLayer) {
        window.map.removeLayer(currentDrawLayer);
        currentDrawLayer = null;
    }
    if (currentTooltip) {
        window.map.removeLayer(currentTooltip);
        currentTooltip = null;
    }

    if (points.length > 0 && mouseMovePoint) {
        const center = turf.point(points[0]);
        const current = turf.point(mouseMovePoint);
        const radius = turf.distance(center, current, {units: 'kilometers'});

        if (radius > 0) {
            const circle = turf.circle(center, radius, {steps: 64, units: 'kilometers'});
            const line = turf.lineString([points[0], mouseMovePoint]);

            // Create a feature collection with both circle and radius line
            const featureCollection = turf.featureCollection([circle, line]);

            currentDrawLayer = L.geoJSON(featureCollection, {
                style: { color: 'red', weight: 2, fillColor: 'red', fillOpacity: 0.2, dashArray: '5, 5' },
                interactive: false
            }).addTo(window.map);

            currentTooltip = L.tooltip({
                permanent: true,
                direction: 'right',
                className: 'measure-tooltip'
            })
            .setContent(formatLength(radius))
            .setLatLng([mouseMovePoint[1], mouseMovePoint[0]])
            .addTo(window.map);
        }
    }
}

function finishRuler() {
    if (points.length < 2) {
        points = [];
        mouseMovePoint = null;
        return;
    }

    if (currentDrawLayer) {
        window.map.removeLayer(currentDrawLayer);
        currentDrawLayer = null;
    }

    let geojson;
    let type = 'line';

    // Determine if it's a polygon by checking if the last point is strictly identical
    // to the first point, which happens if we snap-closed it during onMapClick
    const isExplicitlyClosed = (points.length > 2 &&
                                points[0][0] === points[points.length-1][0] &&
                                points[0][1] === points[points.length-1][1]);

    if (isExplicitlyClosed) {
        geojson = turf.polygon([points]);
        type = 'polygon';
    } else {
        geojson = turf.lineString(points);
    }

    addMeasurementToMap(geojson, type);

    // Reset points for the next measurement if we are still using ruler
    points = [];
    mouseMovePoint = null;
}

function finishCircle(latlng) {
    if (currentDrawLayer) {
        window.map.removeLayer(currentDrawLayer);
        currentDrawLayer = null;
    }
    if (currentTooltip) {
        window.map.removeLayer(currentTooltip);
        currentTooltip = null;
    }

    const center = turf.point(points[0]);
    const perimeter = turf.point([latlng.lng, latlng.lat]);
    const radius = turf.distance(center, perimeter, {units: 'kilometers'});

    if (radius > 0) {
        const circleGeojson = turf.circle(center, radius, {steps: 64, units: 'kilometers'});

        // Add radius property for display
        circleGeojson.properties = { radiusKm: radius };

        addMeasurementToMap(circleGeojson, 'circle');
    }

    points = [];
    mouseMovePoint = null;

    // Auto-disable tool after single circle measurement (or keep it? Usually keep it)
    // disableMeasureTools();
}

function addMeasurementToMap(geojson, type) {
    const layerId = Date.now().toString();

    // Default style
    let style = {
        color: '#ff0000',
        weight: 2,
        fillColor: '#ff0000',
        fillOpacity: 0.2
    };

    let contentHTML = '';

    if (type === 'polygon' || type === 'line') {
        const coords = type === 'polygon' ? geojson.geometry.coordinates[0] : geojson.geometry.coordinates;

        let legsHTML = '';
        for (let i = 0; i < coords.length - 1; i++) {
            const legLine = turf.lineString([coords[i], coords[i+1]]);
            const legLength = turf.length(legLine, {units: 'kilometers'});
            legsHTML += `<div><span style="color:#94a3b8; font-size:0.85em;">Leg ${i+1}:</span> ${formatLength(legLength)}</div>`;
        }

        if (type === 'polygon') {
            const areaSqM = turf.area(geojson);
            const areaSqKm = areaSqM / 1000000;
            const line = turf.lineString(coords);
            const totalLengthKm = turf.length(line, {units: 'kilometers'});

            contentHTML = `
                <div><b>Type:</b> Polygon</div>
                ${legsHTML}
                <hr style="border-color: rgba(255,255,255,0.1); margin: 4px 0;">
                <div><b>Total Perimeter:</b> ${formatLength(totalLengthKm)}</div>
                <div><b>Area:</b> ${formatArea(areaSqKm)}</div>
            `;
        } else {
            const totalLengthKm = turf.length(geojson, {units: 'kilometers'});
            style.fillOpacity = 0; // No fill for lines

            contentHTML = `
                <div><b>Type:</b> Line</div>
                ${legsHTML}
                <hr style="border-color: rgba(255,255,255,0.1); margin: 4px 0;">
                <div><b>Total Length:</b> ${formatLength(totalLengthKm)}</div>
            `;
        }
    } else if (type === 'circle') {
        const radiusKm = geojson.properties.radiusKm;
        const areaSqKm = Math.PI * Math.pow(radiusKm, 2);
        const circumference = 2 * Math.PI * radiusKm;

        contentHTML = `
            <div><b>Type:</b> Circle</div>
            <div><b>Radius:</b> ${formatLength(radiusKm)}</div>
            <div><b>Diameter:</b> ${formatLength(radiusKm * 2)}</div>
            <div><b>Circumference:</b> ${formatLength(circumference)}</div>
            <div><b>Area:</b> ${formatArea(areaSqKm)}</div>
        `;
    }

    const leafletLayer = L.geoJSON(geojson, {
        style: Object.assign({}, style, {className: 'measure-interactive'})
    }).addTo(measureLayerGroup);

    // Save ID on layer
    leafletLayer.layerId = layerId;

    const popupContent = document.createElement('div');
    popupContent.className = 'measure-popup-content';
    popupContent.innerHTML = `
        ${contentHTML}
        <div class="measure-popup-controls">
            <input type="color" value="${style.color}" onchange="updateMeasureStyle('${layerId}', 'color', this.value)">
            <input type="range" min="0" max="1" step="0.1" value="${style.fillOpacity}" onchange="updateMeasureStyle('${layerId}', 'opacity', this.value)" title="Fill Opacity">
            <button class="icon-btn delete" onclick="deleteMeasurement('${layerId}')" title="Delete">🗑️</button>
        </div>
    `;

    // Ensure our popups stay on top
    leafletLayer.bindPopup(popupContent, {minWidth: 200, className: 'measure-popup-container'});

    // We want the interactive capabilities of our measurements to be restored despite .is-measuring
    leafletLayer.options.interactive = true;

    leafletLayer.openPopup();
}

window.updateMeasureStyle = function(layerId, property, value) {
    measureLayerGroup.eachLayer(groupLayer => {
        if (groupLayer.layerId === layerId) {
            groupLayer.eachLayer(layer => {
                if (property === 'color') {
                    layer.setStyle({ color: value, fillColor: value });
                } else if (property === 'opacity') {
                    layer.setStyle({ fillOpacity: parseFloat(value) });
                }
            });
        }
    });
};

window.deleteMeasurement = function(layerId) {
    measureLayerGroup.eachLayer(groupLayer => {
        if (groupLayer.layerId === layerId) {
            measureLayerGroup.removeLayer(groupLayer);
        }
    });
};

window.toggleMeasureTool = toggleMeasureTool;

// Initialize on load
document.addEventListener('DOMContentLoaded', initMeasureTools);
