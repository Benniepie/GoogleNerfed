<<<<<<< SEARCH
                    if (isFrontlineLayer) {
                        const selectedDate = document.getElementById('currentDateDisplay').textContent;
                        if (layerDate && layerDate !== selectedDate) {
                            shouldAdd = false; // It's preloaded, don't show yet
                        }
                    }
=======
                    if (isFrontlineLayer) {
                        const selectedDate = document.getElementById('currentDateDisplay').textContent;
                        // On initial load, selectedDate might be empty, so allow it to load if it's the latest Date or if no selectedDate is set yet
                        if (selectedDate) {
                            if (layerDate && layerDate !== selectedDate) {
                                shouldAdd = false; // It's preloaded, don't show yet
                            }
                        }
                    }
>>>>>>> REPLACE
