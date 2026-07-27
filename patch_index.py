import re

with open('static/index.html', 'r') as f:
    content = f.read()

# 1. Remove exportVideoBtn from control panel
content = re.sub(
    r'<button id="exportVideoBtn"[^>]*>.*?<\/button>',
    '',
    content
)

# 2. Add new replay controls overlay below replayOverlay
replay_controls_html = """
    <div id="replayControlsOverlay" style="display: none; position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 3000; background: rgba(30, 30, 35, 0.85); backdrop-filter: blur(10px); padding: 10px 20px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); box-shadow: 0 4px 6px rgba(0,0,0,0.3); color: white; display: flex; align-items: center; gap: 15px; min-width: 300px;">
        <button id="replayPlayPauseBtn" onclick="toggleRadarReplayPause()" class="icon-btn" style="font-size: 1.5rem; padding: 5px; background: transparent; border: none; cursor: pointer; color: white;" title="Play/Pause">⏸️</button>

        <div style="display: flex; flex-direction: column; flex-grow: 1; align-items: center;">
            <input type="range" id="replayProgressSlider" min="0" max="100" value="0" step="0.1" style="width: 100%; cursor: pointer;" oninput="seekRadarReplay(this.value)">
            <div style="display: flex; justify-content: space-between; width: 100%; font-size: 0.75rem; color: #cbd5e1; margin-top: 2px;">
                <span>0h</span>
                <span>24h</span>
            </div>
        </div>

        <select id="replaySpeedSelect" onchange="changeRadarReplaySpeed()" style="background: rgba(15, 23, 42, 0.8); color: white; border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 0.85rem; cursor: pointer;">
            <option value="60">60s</option>
            <option value="120">120s</option>
            <option value="180">180s</option>
            <option value="300">300s</option>
        </select>

        <button id="exportVideoBtn" class="primary-btn" onclick="exportRadarVideo()" style="font-size: 0.85rem; padding: 6px; background-color: #8b5cf6;">🎬 Export Video</button>
        <button onclick="closeRadarReplay()" class="icon-btn" style="font-size: 1.2rem; padding: 5px; background: transparent; border: none; cursor: pointer; color: white;" title="Close Replay">✖</button>
    </div>
"""

content = content.replace(
    '    <div id="replayOverlay"',
    replay_controls_html + '\n    <div id="replayOverlay"'
)

# We need to make sure we don't display it immediately on load
content = content.replace('id="replayControlsOverlay" style="display: none;', 'id="replayControlsOverlay" style="display: none;')
content = content.replace('id="replayControlsOverlay" style="display: flex;', 'id="replayControlsOverlay" style="display: none;')


with open('static/index.html', 'w') as f:
    f.write(content)
