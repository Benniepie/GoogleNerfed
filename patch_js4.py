with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

hide_logic = """
                if (params.get('hide_ui') === '1') {
                    document.getElementById('controlPanel').style.display = 'none';
                    // Hide other map controls like zoom, minimap, etc for video export
                    document.querySelectorAll('.leaflet-control').forEach(el => {
                        el.style.display = 'none';
                    });
                }
"""

content = content.replace("""
                if (params.get('hide_ui') === '1') {
                    document.getElementById('controlPanel').style.display = 'none';
                }
""".strip("\n"), hide_logic.strip("\n"))

with open('static/js/map-layers.js', 'w') as f:
    f.write(content)
