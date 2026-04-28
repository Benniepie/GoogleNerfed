const fs = require('fs');

const file = 'static/js/map-layers.js';
let content = fs.readFileSync(file, 'utf8');

const regex = /const layer = L\.geoJSON\([\s\S]*?onEachFeature: function \([\s\S]*?\}\s*\);/;

const newGeoJSONBlock = `const layer = L.geoJSON(geoJsonData, {
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
                activeKMLGeoJSON[filename] = geoJsonData;`;

if (regex.test(content)) {
    content = content.replace(regex, newGeoJSONBlock);
    fs.writeFileSync(file, content);
    console.log("Updated L.geoJSON block in map-layers.js");
} else {
    console.log("Could not find L.geoJSON regex match.");
}
