import re

with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

search = '''                        // Handle current target specifically
                        if (isChecked) {
                            if (!activeLayers[filename]) {
                                await fetchAndAddKML(filename);
                            } else if (!isFrontline || extractDateFromFilename(filename) === document.getElementById('currentDateDisplay').textContent) {
                                map.addLayer(activeLayers[filename]);
                            }
                        } else {
                            if (activeLayers[filename] && map.hasLayer(activeLayers[filename])) {
                                map.removeLayer(activeLayers[filename]);
                            }
                        }'''

replace = '''                        // Handle current target specifically
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
                        }'''

if search in content:
    content = content.replace(search, replace)
    with open('static/js/map-layers.js', 'w') as f:
        f.write(content)
    print("Successfully patched toggle visibility current target")
else:
    print("toggle visibility current target search string not found")
