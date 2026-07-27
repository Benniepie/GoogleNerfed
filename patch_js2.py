import re

with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

# 1. Close controlPanel and hide UI on start
start_logic = """
            window.radarReplayFinished = false;
            window.radarReplayPaused = false;

            // Sync UI state
            const playPauseBtn = document.getElementById('replayPlayPauseBtn');
            if (playPauseBtn) playPauseBtn.innerHTML = '⏸️';

            const speedSelect = document.getElementById('replaySpeedSelect');
            if (speedSelect) {
                window.radarReplayDurationMs = parseInt(speedSelect.value) * 1000;
            }

            const cp = document.getElementById('controlPanel');
            if (cp) {
                cp.classList.remove('open');
            }
"""

content = content.replace("            window.radarReplayFinished = false;", start_logic)

# 2. Setup the UI overlays at the start of replay
overlay_logic = """
            window.radarReplayRealNow = realNow;
            window.radarReplayStartTime = startReplayTime;

            let lastFrameTime = performance.now();

            const overlay = document.getElementById('replayOverlay');
            if (overlay) overlay.style.display = 'block';

            const controls = document.getElementById('replayControlsOverlay');
            if (controls && params.get('hide_ui') !== '1') {
                controls.style.display = 'flex';
            }
"""

content = content.replace("""
            let lastFrameTime = performance.now();
            let durationMs = 60000; // 60 seconds for 24 hours
            let speedMultiplier = (24 * 60 * 60 * 1000) / durationMs;

            const overlay = document.getElementById('replayOverlay');
            if (overlay) overlay.style.display = 'block';
""", overlay_logic)

with open('static/js/map-layers.js', 'w') as f:
    f.write(content)
