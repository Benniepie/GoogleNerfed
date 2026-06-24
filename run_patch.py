import sys

def patch_file(filename, search, replace):
    with open(filename, 'r') as f:
        content = f.read()

    if search not in content:
        print(f"Search string not found in {filename}")
        return

    content = content.replace(search, replace)

    with open(filename, 'w') as f:
        f.write(content)
    print(f"Successfully patched {filename}")

patch_file('static/index.html', '''        <div class="section-header" onclick="toggleSection(this)">
            Front Line Tracker <span class="toggle-icon">▼</span>
        </div>
        <div class="section-content">''', '''        <div class="section-header" onclick="toggleSection(this)">
            Front Line Tracker <span class="toggle-icon">▶</span>
        </div>
        <div class="section-content collapsed">''')

patch_file('static/js/map-layers.js', '''                    // Load KML
                    if (!activeLayers[filename]) {
                        if (checkbox.checked || isFrontline) {
                            await fetchAndAddKML(filename);
                        }
                    } else {''', '''                    // Load KML
                    if (!activeLayers[filename]) {
                        if (checkbox.checked) {
                            await fetchAndAddKML(filename);
                        }
                    } else {''')
