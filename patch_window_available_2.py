import re

with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

search = '''            availableDates = Array.from(datesSet).sort();'''

replace = '''            availableDates = Array.from(datesSet).sort();
            window.availableDates = availableDates;'''

if search in content:
    content = content.replace(search, replace)
    with open('static/js/map-layers.js', 'w') as f:
        f.write(content)
    print("Successfully patched availableDates update")
else:
    print("availableDates update search string not found")
