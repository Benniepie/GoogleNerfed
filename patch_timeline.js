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
            for (const filename of globalAllFilenames) {
                if (filename.startsWith('AP Map') || filename.startsWith('AP Pins') || filename.startsWith('SM Map') || filename.startsWith('SM Pins')) {
                    const d = extractDateFromFilename(filename);
                    if (d) datesSet.add(d);
                }
            }

            for (const filename in activeLayers) {
                const d = extractDateFromFilename(filename);
                if (d) datesSet.add(d);
            }

            availableDates = Array.from(datesSet).sort();
