import re

with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

search = '''                            if (prefix) {
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
                            }'''

replace = '''                            if (prefix) {
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
                            }'''

if search in content:
    content = content.replace(search, replace)
    with open('static/js/map-layers.js', 'w') as f:
        f.write(content)
    print("Successfully patched toggle visibility frontline")
else:
    print("toggle visibility frontline search string not found")
