import re

with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

search = '''        let availableDates = [];'''

replace = '''        let availableDates = [];
        window.availableDates = availableDates;'''

if search in content:
    content = content.replace(search, replace)
    with open('static/js/map-layers.js', 'w') as f:
        f.write(content)
    print("Successfully patched availableDates")
else:
    print("availableDates search string not found")
