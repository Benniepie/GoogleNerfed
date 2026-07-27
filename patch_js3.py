with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

animate_logic = """
            function animate(currentTime) {
                let dt = currentTime - lastFrameTime;
                lastFrameTime = currentTime;

                if (!window.radarReplayPaused) {
                    let speedMultiplier = (24 * 60 * 60 * 1000) / window.radarReplayDurationMs;
                    let simulatedMs = dt * speedMultiplier;
                    window.radarReplayTime = new Date(window.radarReplayTime.getTime() + simulatedMs);
                }

                if (window.radarReplayTime >= realNow) {
                    window.radarReplayTime = null;
                    renderRadarRussiaData();
                    window.radarReplayFinished = true; // Signal Playwright
                    if (overlay) overlay.style.display = 'none';
                    if (controls) controls.style.display = 'none';
                    return;
                }

                // Update slider value
                const slider = document.getElementById('replayProgressSlider');
                if (slider && window.radarReplayTime && window.radarReplayStartTime && window.radarReplayRealNow) {
                    const totalSimMs = window.radarReplayRealNow.getTime() - window.radarReplayStartTime.getTime();
                    const elapsedSimMs = window.radarReplayTime.getTime() - window.radarReplayStartTime.getTime();
                    const percent = (elapsedSimMs / totalSimMs) * 100;
                    slider.value = percent;
                }
"""

# Replace the beginning of animate()
import re
content = re.sub(
    r'function animate\(currentTime\) \{.*?if \(window\.radarReplayTime >= realNow\) \{.*?return;\n                \}',
    animate_logic.strip(),
    content,
    flags=re.DOTALL
)

with open('static/js/map-layers.js', 'w') as f:
    f.write(content)
