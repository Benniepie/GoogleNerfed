import re

with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

search = '''        function updateTimeline() {
            const datesSet = new Set();
            for (const filename in activeLayers) {
                const d = extractDateFromFilename(filename);
                if (d) datesSet.add(d);
            }

            availableDates = Array.from(datesSet).sort();'''

replace = '''        function updateTimeline() {
            const datesSet = new Set();

            // Collect all dates from frontline items in the DOM
            document.querySelectorAll('#frontlineLayerList .layer-item').forEach(item => {
                const filename = item.dataset.filename;
                const d = extractDateFromFilename(filename);
                if (d) datesSet.add(d);
            });

            availableDates = Array.from(datesSet).sort();'''

if search in content:
    content = content.replace(search, replace)
    with open('static/js/map-layers.js', 'w') as f:
        f.write(content)
    print("Successfully patched updateTimeline")
else:
    print("updateTimeline search string not found")
