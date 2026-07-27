with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

# We need to compute speedMultiplier dynamically inside animate, not beforehand,
# because durationMs can change on the fly now. Also dt * speedMultiplier was failing because
# speedMultiplier wasn't defined.

content = content.replace("let simulatedMs = dt * speedMultiplier;", "let speedMultiplier = (24 * 60 * 60 * 1000) / window.radarReplayDurationMs;\n                let simulatedMs = dt * speedMultiplier;")

with open('static/js/map-layers.js', 'w') as f:
    f.write(content)
