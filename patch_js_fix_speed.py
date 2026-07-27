with open('static/js/map-layers.js', 'r') as f:
    content = f.read()

speed_logic = """
        window.changeRadarReplaySpeed = function() {
            const select = document.getElementById('replaySpeedSelect');
            if (select) {
                const oldDuration = window.radarReplayDurationMs;
                window.radarReplayDurationMs = parseInt(select.value) * 1000;

                // Adjust lastFrameTime to prevent sudden jumps
                // Not strictly necessary since we calculate dt each frame, but good practice.
                // Wait, dt is just real time since last frame. Simulated ms added is dt * multiplier.
                // So changing durationMs just changes the multiplier for the *next* frame.
                // There is no jump! The jump would happen if we were calculating simulated time based on elapsed total real time.
            }
        };
"""

# The logic above is already correct because we use dt * multiplier each frame rather than
# totalElapsedMs * multiplier. So no fix needed for speed jump!
