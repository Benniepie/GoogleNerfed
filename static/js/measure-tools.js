// State for measurement tools
window.currentTool = null; // 'ruler', 'circle', or null
let measureLayerGroup = null; // LayerGroup to hold all measurements
let currentDrawLayer = null; // The temporary layer being drawn
let points = []; // Store coordinates for current drawing
let mouseMovePoint = null;

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
    }
}

function disableMeasureTools() {
    if (currentDrawLayer) {
        window.map.removeLayer(currentDrawLayer);
        currentDrawLayer = null;
    }
    window.currentTool = null;
    points = [];
    mouseMovePoint = null;

    document.getElementById('rulerBtn').classList.remove('active');
    document.getElementById('circleBtn').classList.remove('active');
    if (window.map) {
        window.map.getContainer().style.cursor = '';
        window.map.doubleClickZoom.enable();
    }
}

function onMapClick(e) {
    if (!window.currentTool) return;

    const latlng = e.latlng;

    if (window.currentTool === 'ruler') {
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
    }

    const drawPoints = [...points];
    if (mouseMovePoint) {
        drawPoints.push(mouseMovePoint);
    }

    if (drawPoints.length > 1) {
        const line = turf.lineString(drawPoints);
        currentDrawLayer = L.geoJSON(line, {
            style: { color: 'red', weight: 2, dashArray: '5, 5' }
        }).addTo(window.map);
    }
}

function updateCircleDrawing() {
    if (currentDrawLayer) {
        window.map.removeLayer(currentDrawLayer);
    }

    if (points.length > 0 && mouseMovePoint) {
        const center = turf.point(points[0]);
        const current = turf.point(mouseMovePoint);
        const radius = turf.distance(center, current, {units: 'kilometers'});

        if (radius > 0) {
            const circle = turf.circle(center, radius, {steps: 64, units: 'kilometers'});
            currentDrawLayer = L.geoJSON(circle, {
                style: { color: 'red', weight: 2, fillColor: 'red', fillOpacity: 0.2, dashArray: '5, 5' }
            }).addTo(window.map);
        }
    }
}

function finishRuler() {
    // Clean up points: Leaflet dblclick fires two clicks, resulting in duplicate or near-duplicate final points.
    // Also, user might accidentally double click in the same spot.
    const uniquePoints = [points[0]];
    for (let i = 1; i < points.length; i++) {
        const prev = uniquePoints[uniquePoints.length - 1];
        const curr = points[i];
        // If distance between points is very small (e.g. double click micro-movements), skip it
        if (curr[0] === prev[0] && curr[1] === prev[1]) continue;
        const pt1 = turf.point(prev);
        const pt2 = turf.point(curr);
        if (turf.distance(pt1, pt2, {units: 'meters'}) > 1) { // Only add if more than 1 meter apart
            uniquePoints.push(curr);
        }
    }
    points = uniquePoints;

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

    // Determine if it's a polygon by checking if the last point is close to the first point
    const firstPoint = turf.point(points[0]);
    const lastPoint = turf.point(points[points.length - 1]);
    const distToStart = turf.distance(firstPoint, lastPoint, {units: 'meters'});

    // If there are >2 points and the path is closed (within 20 meters of start)
    if (points.length > 2 && distToStart < 20) {
        // Make it a valid polygon by ensuring the last point matches the first exactly
        points[points.length - 1] = points[0];
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

    if (type === 'polygon') {
        const areaSqM = turf.area(geojson);
        const areaSqKm = areaSqM / 1000000;
        const line = turf.lineString(geojson.geometry.coordinates[0]);
        const lengthKm = turf.length(line, {units: 'kilometers'});

        contentHTML = `
            <div><b>Type:</b> Polygon</div>
            <div><b>Perimeter:</b> ${lengthKm.toFixed(2)} km</div>
            <div><b>Area:</b> ${areaSqKm.toFixed(2)} km²</div>
        `;
    } else if (type === 'line') {
        const lengthKm = turf.length(geojson, {units: 'kilometers'});
        style.fillOpacity = 0; // No fill for lines

        contentHTML = `
            <div><b>Type:</b> Line</div>
            <div><b>Length:</b> ${lengthKm.toFixed(2)} km</div>
        `;
    } else if (type === 'circle') {
        const radiusKm = geojson.properties.radiusKm;
        const areaSqKm = Math.PI * Math.pow(radiusKm, 2);
        const circumference = 2 * Math.PI * radiusKm;

        contentHTML = `
            <div><b>Type:</b> Circle</div>
            <div><b>Radius:</b> ${radiusKm.toFixed(2)} km</div>
            <div><b>Diameter:</b> ${(radiusKm * 2).toFixed(2)} km</div>
            <div><b>Circumference:</b> ${circumference.toFixed(2)} km</div>
            <div><b>Area:</b> ${areaSqKm.toFixed(2)} km²</div>
        `;
    }

    const leafletLayer = L.geoJSON(geojson, {
        style: style
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

    leafletLayer.bindPopup(popupContent, {minWidth: 200});
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
