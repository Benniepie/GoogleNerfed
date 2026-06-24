<<<<<<< SEARCH
                    // Load KML
                    if (!activeLayers[filename]) {
                        if (checkbox.checked || isFrontline) {
                            await fetchAndAddKML(filename);
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
=======
                    // Load KML
                    if (!activeLayers[filename]) {
                        if (checkbox.checked) {
                            await fetchAndAddKML(filename);
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
