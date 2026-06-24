<<<<<<< SEARCH
        function updateTimeline() {
            const datesSet = new Set();
            for (const filename in activeLayers) {
                const d = extractDateFromFilename(filename);
                if (d) datesSet.add(d);
            }

            availableDates = Array.from(datesSet).sort();
=======
        function updateTimeline() {
            const datesSet = new Set();

            // Collect all dates from frontline items in the DOM
            document.querySelectorAll('#frontlineLayerList .layer-item').forEach(item => {
                const filename = item.dataset.filename;
                const d = extractDateFromFilename(filename);
                if (d) datesSet.add(d);
            });

            availableDates = Array.from(datesSet).sort();
