with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

state_vars = """
        // --- Radar Replay Controls State ---
        window.radarReplayPaused = false;
        window.radarReplayDurationMs = 60000; // default 60s
        window.radarReplayRealNow = null;
        window.radarReplayStartTime = null;

        window.toggleRadarReplayPause = function() {
            window.radarReplayPaused = !window.radarReplayPaused;
            const btn = document.getElementById('replayPlayPauseBtn');
            if (btn) {
                btn.innerHTML = window.radarReplayPaused ? '▶️' : '⏸️';
            }
        };

        window.changeRadarReplaySpeed = function() {
            const select = document.getElementById('replaySpeedSelect');
            if (select) {
                window.radarReplayDurationMs = parseInt(select.value) * 1000;
            }
        };

        window.seekRadarReplay = function(percent) {
            if (!window.radarReplayStartTime || !window.radarReplayRealNow) return;
            const totalSimulatedMs = window.radarReplayRealNow.getTime() - window.radarReplayStartTime.getTime();
            const targetMs = (percent / 100) * totalSimulatedMs;
            window.radarReplayTime = new Date(window.radarReplayStartTime.getTime() + targetMs);

            // force render to update map and overlays immediately
            renderRadarRussiaData();
        };

        window.closeRadarReplay = function() {
            window.radarReplayTime = null;
            window.radarReplayFinished = true;
            window.radarReplayPaused = false;

            const overlay = document.getElementById('replayOverlay');
            if (overlay) overlay.style.display = 'none';

            const controls = document.getElementById('replayControlsOverlay');
            if (controls) controls.style.display = 'none';

            // Re-render to show live data
            renderRadarRussiaData();
        };

        window.startRadarReplay = async function() {
"""

content = content.replace("        window.startRadarReplay = async function() {", state_vars)

with open('static/js/map-layers.js', 'w') as f:
    f.write(content)
