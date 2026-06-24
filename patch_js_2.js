<<<<<<< SEARCH
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
=======
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
                loadFrontlineLayersForDate(date);
            }

            // Await specifically for the current selected date
            await loadFrontlineLayersForDate(selectedDate);

            // Toggle layer map visibility AND UI list visibility
            document.querySelectorAll('.layer-item').forEach(layerItemDiv => {
                const filename = layerItemDiv.dataset.filename;
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
