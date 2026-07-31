
// --- map-admin.js ---

// --- 1. Inject Admin HTML & Modals ---

// Add the Settings Button to the Admin Panel
document.getElementById('admin-panel-container').innerHTML = `
    <div class="section-header" onclick="toggleSection(this)">
        Map Admin <span class="toggle-icon">▼</span>
    </div>
    <div class="section-content" style="border-top: none; padding-top: 10px;">

        <!-- 1. Automate Map Update (unchanged) -->
        <button class="primary-btn" onclick="openAutomateModal()" style="width: 100%; margin-bottom: 10px; background: #8b5cf6;">🤖 Automate Map Update</button>

        <!-- 2. Map Settings (unchanged) -->
        <button class="primary-btn" onclick="window.openSettingsModal()" style="width: 100%; margin-bottom: 10px; background: #0ea5e9;">⚙️ Map Settings</button>

        <!-- 3. Static Data Layers Admin (toggle - new) -->
        <div class="section-header" onclick="toggleSection(this)" style="background: rgba(255,255,255,0.05); margin: 0 -15px 10px -15px; padding: 10px 15px; border-top: 1px solid var(--border-color); border-bottom: 1px solid var(--border-color);">
            Static Data Layers Admin <span class="toggle-icon">▶</span>
        </div>
        <div class="section-content collapsed upload-section" style="padding-bottom: 15px; border-bottom: 1px solid var(--border-color); margin: 0 -15px 15px -15px; padding-left: 15px; padding-right: 15px; border-top: none;">
            <form id="uploadForm">
                <input type="file" id="kmlFile" accept=".kml,.kmz" multiple required style="width: 100%; margin-bottom: 10px;" />
                <button type="submit" id="uploadBtn" class="primary-btn" style="width: 100%;">Upload KML / KMZ</button>
                <div id="statusMsg" class="status-msg"></div>
            </form>
            <div style="display: flex; gap: 10px; margin-top: 10px;">
                <button class="primary-btn" onclick="exportKML()" style="flex: 1; background: var(--border-color); font-size: 0.8rem;">⬇️ Export Data</button>
                <button class="primary-btn" onclick="window.addNewMarker()" style="flex: 1; background: #3b82f6; font-size: 0.8rem;">➕ Add Marker</button>
            </div>
        </div>

        <!-- 4. Live Data Layers Admin (toggle - new) -->
        <div class="section-header" onclick="toggleSection(this)" style="background: rgba(255,255,255,0.05); margin: 0 -15px 10px -15px; padding: 10px 15px; border-top: 1px solid var(--border-color); border-bottom: 1px solid var(--border-color);">
            Live Data Layers Admin <span class="toggle-icon">▶</span>
        </div>
        <div class="section-content collapsed upload-section" style="padding-bottom: 15px; border-bottom: 1px solid var(--border-color); margin: 0 -15px 15px -15px; padding-left: 15px; padding-right: 15px; border-top: none;">

            <h3 style="margin-top:0; font-size: 0.95rem;">🚢 Shadow Fleet Target List</h3>
            <form id="shadowFleetForm" style="margin-bottom: 20px;">
                <input type="file" id="shadowFile" accept=".json" required style="width: 100%; margin-bottom: 10px;" />
                <button type="submit" id="shadowBtn" class="primary-btn" style="width: 100%; background: #eab308; color: #0f172a;">Upload Shadow Fleet Target List</button>
                <div id="shadowStatusMsg" class="status-msg" style="display: none; margin-top: 10px; font-size: 0.85rem; color: #10b981;"></div>
            </form>

            <hr style="border-top: 1px solid rgba(255,255,255,0.1); margin: 15px 0;">

            <h3 style="margin-top:0; font-size: 0.95rem;">🚨 Radar Russia Overrides</h3>
            <p style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 10px;">Fix bad geocoding or translations. Leave ID/Translation blank to delete cache and retry.</p>
            <form id="overrideForm" style="display: flex; flex-direction: column; gap: 8px;">
                <div>
                    <label style="font-size: 0.8rem; color: #94a3b8;">Location Name (Russian text):</label>
                    <input type="text" id="overrideLocationName" required placeholder="e.g. Орловский район" style="width: 100%; box-sizing: border-box; padding: 5px; background: rgba(0,0,0,0.5); border: 1px solid var(--border-color); color: white; border-radius: 4px;">
                </div>
                <div>
                    <label style="font-size: 0.8rem; color: #94a3b8;">OSM ID (optional):</label>
                    <input type="text" id="overrideOsmId" placeholder="e.g. R140291" style="width: 100%; box-sizing: border-box; padding: 5px; background: rgba(0,0,0,0.5); border: 1px solid var(--border-color); color: white; border-radius: 4px;">
                </div>
                <div>
                    <label style="font-size: 0.8rem; color: #94a3b8;">English Translation (optional):</label>
                    <input type="text" id="overrideEnglishName" placeholder="e.g. Oryol District" style="width: 100%; box-sizing: border-box; padding: 5px; background: rgba(0,0,0,0.5); border: 1px solid var(--border-color); color: white; border-radius: 4px;">
                </div>
                <div style="display: flex; align-items: center; gap: 5px; margin-top: 5px;">
                    <input type="checkbox" id="overrideSuppress" style="cursor: pointer;">
                    <label for="overrideSuppress" style="font-size: 0.8rem; color: #94a3b8; cursor: pointer;">Suppress marker (hide permanently)</label>
                </div>
                <button type="submit" id="overrideBtn" class="primary-btn" style="width: 100%; background: #10b981; margin-top: 5px;">Save Override</button>
                <div id="overrideStatusMsg" style="display: none; font-size: 0.85rem; color: #10b981; margin-top: 5px;"></div>
            </form>

        </div>
    </div>
`;

// Inject the Modals dynamically at the bottom of the body
const adminModalsHTML = `
    <div id="settingsModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 2000; align-items: center; justify-content: center;">
        <div class="modal-content">
            <h3 style="margin-top:0;">Settings</h3>
            <div style="text-align: left; margin-bottom: 15px;">
                <label style="display:block; margin-bottom:5px;">Default Map Center (Lat, Lng):</label>
                <input type="number" id="defaultLat" step="any" style="width: 45%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px;"> ,
                <input type="number" id="defaultLng" step="any" style="width: 45%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px;">
            </div>
            <div style="text-align: left; margin-bottom: 15px;">
                <label style="display:block; margin-bottom:5px;">Default Zoom:</label>
                <input type="number" id="defaultZoom" step="0.25" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px;">
            </div>
            <div style="text-align: left; margin-bottom: 15px;">
                <label style="display:block; margin-bottom:5px;">Default Basemap:</label>
                <select id="defaultBasemap" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px;">
                    <option value="dark">Dark Map</option>
                    <option value="satellite">Satellite</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="firefly">Firefly</option>
                    <option value="fireflyHybrid">Firefly Hybrid</option>
                </select>
            </div>
            <div style="margin-bottom: 15px;">
                <button class="icon-btn" onclick="useCurrentView()" style="font-size: 0.9rem; background: rgba(255,255,255,0.1); padding: 5px 10px; width: 100%;">📍 Use Current Map View</button>
            </div>
            <button class="primary-btn" onclick="saveSettings()" style="width:100%; margin-bottom:10px;">Save Settings</button>
            <button class="primary-btn" onclick="document.getElementById('settingsModal').style.display='none'" style="width:100%; background:var(--border-color);">Close</button>
        </div>
    </div>

    <div id="colorModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 2000; align-items: center; justify-content: center;">
        <div class="modal-content" style="width: 320px;">
            <h3 style="margin-top:0;">Layer Styling</h3>
            <p id="stylingLayerName" style="font-size:0.8rem; color:#94a3b8; word-break:break-all;"></p>

            <div style="text-align: left; margin-bottom: 15px;">
                <label style="display:block; margin-bottom:5px;">Style Type:</label>
                <select id="styleTypeSelect" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px;" onchange="renderColorPickers()">
                    <option value="single">Single Style</option>
                    <option value="grouped">Group by Name</option>
                </select>
            </div>

            <div id="globalMarkerConfig" style="text-align: left; margin-bottom: 15px;">
                <label style="display:block; margin-bottom:3px; font-size: 0.85rem;">Default Marker Type:</label>
                <select id="globalMarkerType" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px; box-sizing: border-box; margin-bottom: 5px;">
                    <option value="circle">Circle</option>
                    <option value="icon">Image URL</option>
                    <option value="emoji">Emoji</option>
                </select>
                <input type="text" id="globalMarkerIcon" placeholder="Icon URL or Emoji" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px; box-sizing: border-box;">
                <label style="display:block; margin-bottom:3px; margin-top:5px; font-size: 0.85rem;">Marker Border Color:</label>
                <input type="color" id="globalMarkerBorder" style="width: 100%; height: 30px;">
            </div>

            <div id="colorPickerContainer" style="max-height: 300px; overflow-y: auto; margin-bottom: 15px; padding-right: 5px;"></div>

            <button class="primary-btn" onclick="applyStyle()" style="width:100%; margin-bottom: 10px;">Save Style</button>
            <button class="primary-btn" onclick="document.getElementById('colorModal').style.display='none'" style="width:100%; background:var(--border-color);">Close</button>
        </div>
    </div>

    <!-- Edit Feature Modal -->
    <div id="editFeatureModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 3000; align-items: center; justify-content: center;">
        <div class="modal-content" style="width: 350px;">
            <h3 style="margin-top:0;" id="editFeatureTitle">Edit Marker</h3>
            <input type="hidden" id="editFeatureLayer" />
            <input type="hidden" id="editFeatureId" />

            <div style="text-align: left; margin-bottom: 10px;">
                <label style="display:block; margin-bottom:3px; font-size: 0.85rem;">Name:</label>
                <input type="text" id="editFeatureName" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px; box-sizing: border-box;">
            </div>

            <div style="text-align: left; margin-bottom: 10px;">
                <label style="display:block; margin-bottom:3px; font-size: 0.85rem;">Location (Lat, Lng):</label>
                <div style="display: flex; gap: 5px;">
                    <input type="number" step="any" id="editFeatureLat" style="width: 50%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px; box-sizing: border-box;">
                    <input type="number" step="any" id="editFeatureLng" style="width: 50%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px; box-sizing: border-box;">
                </div>
                <button type="button" class="icon-btn" onclick="window.useClickForLocation()" style="font-size: 0.75rem; background: rgba(255,255,255,0.1); padding: 3px 6px; margin-top: 5px; width: 100%;">📍 Select on Map</button>
            </div>

            <div style="text-align: left; margin-bottom: 10px;">
                <label style="display:block; margin-bottom:3px; font-size: 0.85rem;">Marker Style Override:</label>
                <select id="editFeatureMarkerType" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px; box-sizing: border-box; margin-bottom: 5px;">
                    <option value="">-- Use Layer Default --</option>
                    <option value="circle">Circle</option>
                    <option value="icon">Image URL</option>
                    <option value="emoji">Emoji</option>
                </select>
                <div style="display: flex; gap: 5px; margin-bottom: 5px;">
                    <input type="text" id="editFeatureMarkerIcon" placeholder="URL, filename, or Emoji" style="flex: 1; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px; box-sizing: border-box;">
                    <button type="button" class="icon-btn" onclick="document.getElementById('editFeatureImageUpload').click()" style="background: rgba(255,255,255,0.1); padding: 5px; font-size: 0.8rem;" title="Upload Image">📁</button>
                    <input type="file" id="editFeatureImageUpload" style="display: none;" accept="image/png, image/jpeg, image/gif, image/svg+xml, image/webp" onchange="window.uploadMarkerImage(this)">
                </div>
                <div id="editFeatureImageStatus" style="font-size: 0.75rem; display: none; margin-bottom: 5px;"></div>
            </div>
            <div style="display: flex; gap: 10px; margin-bottom: 15px; text-align: left;">
                <div style="flex: 1;">
                    <label style="display:block; margin-bottom:3px; font-size: 0.85rem;">Color:</label>
                    <input type="color" id="editFeatureMarkerColor" style="width: 100%; height: 30px;">
                </div>
                <div style="flex: 1;">
                    <label style="display:block; margin-bottom:3px; font-size: 0.85rem;">Border:</label>
                    <input type="color" id="editFeatureMarkerBorder" style="width: 100%; height: 30px;">
                </div>
            </div>

            <div style="display: flex; gap: 10px; margin-bottom: 10px;">
                <button class="primary-btn" onclick="window.saveEditedFeature()" style="flex: 2; background: #10b981;">Save</button>
                <button class="primary-btn" onclick="window.deleteEditedFeature()" style="flex: 1; background: #ef4444;">Delete</button>
            </div>
            <button class="primary-btn" onclick="document.getElementById('editFeatureModal').style.display='none'" style="width:100%; background:var(--border-color);">Cancel</button>
        </div>
    </div>
`;
document.body.insertAdjacentHTML('beforeend', adminModalsHTML);

// ... The rest of your map-admin.js functions (openColorPicker, saveSettings, automate update, etc) go below this!

// 1. Inject the Modals into the bottom of the page
const modalsHTML = `

    <!-- Automate Update Modal -->
    <div id="automateModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 2000; align-items: center; justify-content: center;">
        <div class="modal-content" style="width: 350px;">
            <h3 style="margin-top:0;">🤖 Automate Update</h3>
            <p style="font-size:0.85rem; color:#cbd5e1; margin-bottom: 15px;">Run geoprocessing to calculate Ukraine/Russian gains automatically.</p>

            <form id="automateForm">
                <div style="text-align: left; margin-bottom: 15px;">
                    <label style="display:block; margin-bottom:5px; font-weight: bold; color: #a78bfa;">Layer Date</label>
                    <input type="date" id="updateDate" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 8px; border-radius: 4px; box-sizing: border-box; margin-bottom: 10px;">
                </div>

                <div style="text-align: left; margin-bottom: 15px;">
                    <label style="display:block; margin-bottom:5px; font-weight: bold; color: #a78bfa;">AP Maps Process</label>

                    <label style="display:block; margin-bottom:3px; font-size: 0.8rem; color: #94a3b8;">Base AP Layer (Old):</label>
                    <select id="oldApLayerSelect" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 8px; border-radius: 4px; box-sizing: border-box; margin-bottom: 5px;">
                        <option value="">-- Do not process AP Map --</option>
                    </select>

                    <label style="display:block; margin-bottom:3px; font-size: 0.8rem; color: #94a3b8;">New AP URL (.kml or .kmz) OR Upload:</label>
                    <input type="url" id="newApUrl" placeholder="https://www.google.com/maps/d/kml?mid=...&forcekml=1" value="https://www.google.com/maps/d/kml?mid=1gO8X7RC8cUzc-1q7-s4-09X53HNIEJA&forcekml=1" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 8px; border-radius: 4px; box-sizing: border-box; margin-bottom: 5px;">
                    <input type="file" id="newApFile" accept=".kml,.kmz" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 8px; border-radius: 4px; box-sizing: border-box;">
                </div>

                <div style="text-align: left; margin-bottom: 15px;">
                    <label style="display:block; margin-bottom:5px; font-weight: bold; color: #a78bfa;">SM Maps Process</label>

                    <label style="display:block; margin-bottom:3px; font-size: 0.8rem; color: #94a3b8;">Base SM Layer (Old):</label>
                    <select id="oldSmLayerSelect" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 8px; border-radius: 4px; box-sizing: border-box; margin-bottom: 5px;">
                        <option value="">-- Do not process SM Map --</option>
                    </select>

                    <label style="display:block; margin-bottom:3px; font-size: 0.8rem; color: #94a3b8;">New SM URL (.kml or .kmz) OR Upload:</label>
                    <input type="url" id="newSmUrl" placeholder="https://www.google.com/maps/d/kml?mid=...&forcekml=1" value="https://www.google.com/maps/d/kml?mid=1V8NzjQkzMOhpuLhkktbiKgodOQ27X6IV&forcekml=1" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 8px; border-radius: 4px; box-sizing: border-box; margin-bottom: 5px;">
                    <input type="file" id="newSmFile" accept=".kml,.kmz" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 8px; border-radius: 4px; box-sizing: border-box;">
                </div>

                <div id="automateStatus" style="font-size: 0.85rem; margin-bottom: 10px; display: none; text-align: center;"></div>

                <button type="submit" id="automateBtn" class="primary-btn" style="width:100%; margin-bottom:10px;">Run Update</button>
                <button type="button" class="primary-btn" onclick="document.getElementById('automateModal').style.display='none'" style="width:100%; background:var(--border-color);">Cancel</button>
            </form>
        </div>
    </div>



    <!-- Settings Modal -->
    <div id="settingsModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 2000; align-items: center; justify-content: center;">
        <div class="modal-content">
            <h3 style="margin-top:0;">Settings</h3>
            <div style="text-align: left; margin-bottom: 15px;">
                <label style="display:block; margin-bottom:5px;">Default Map Center (Lat, Lng):</label>
                <input type="number" id="defaultLat" step="any" style="width: 45%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px;"> ,
                <input type="number" id="defaultLng" step="any" style="width: 45%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px;">
            </div>
            <div style="text-align: left; margin-bottom: 15px;">
                <label style="display:block; margin-bottom:5px;">Default Zoom:</label>
                <input type="number" id="defaultZoom" step="0.25" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px;">
            </div>
            <div style="text-align: left; margin-bottom: 15px;">
                <label style="display:block; margin-bottom:5px;">Default Basemap:</label>
                <select id="defaultBasemap" style="width: 100%; background: var(--border-color); color: white; border: none; padding: 5px; border-radius: 4px;">
                    <option value="dark">Dark Map</option>
                    <option value="satellite">Satellite</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="firefly">Firefly</option>
                    <option value="fireflyHybrid">Firefly Hybrid</option>
                </select>
            </div>
            <div style="margin-bottom: 15px;">
                <button class="icon-btn" onclick="useCurrentView()" style="font-size: 0.9rem; background: rgba(255,255,255,0.1); padding: 5px 10px; width: 100%;">📍 Use Current Map View</button>
            </div>
            <button class="primary-btn" onclick="saveSettings()" style="width:100%; margin-bottom:10px;">Save Settings</button>
            <button class="primary-btn" onclick="document.getElementById('settingsModal').style.display='none'" style="width:100%; background:var(--border-color);">Close</button>
        </div>
    </div>

`;
document.body.insertAdjacentHTML('beforeend', modalsHTML);

// 2. The rest of your admin functions (openAutomateModal, etc.) go here

        function openAutomateModal() {
            document.getElementById('automateStatus').style.display = 'none';

            // Set default date to today
            const today = new Date();
            const year = today.getFullYear();
            const month = String(today.getMonth() + 1).padStart(2, '0');
            const day = String(today.getDate()).padStart(2, '0');
            document.getElementById('updateDate').value = `${year}-${month}-${day}`;

            // Populate the dropdowns with currently loaded files from `activeLayers`
            const apSelect = document.getElementById('oldApLayerSelect');
            const smSelect = document.getElementById('oldSmLayerSelect');

            // Clear current options except the "Do not process" one
            apSelect.innerHTML = '<option value="">-- Do not process AP Map --</option>';
            smSelect.innerHTML = '<option value="">-- Do not process SM Map --</option>';

            const filenames = Object.keys(activeLayers).sort().reverse();

            for (const filename of filenames) {
                const normalizedName = filename.toLowerCase().replace(/_/g, ' ');
                if (normalizedName.includes('ap map')) {
                    const opt = document.createElement('option');
                    opt.value = filename;
                    opt.textContent = filename;
                    apSelect.appendChild(opt);
                } else if (normalizedName.includes('sm map')) {
                    const opt = document.createElement('option');
                    opt.value = filename;
                    opt.textContent = filename;
                    smSelect.appendChild(opt);
                }
            }

            // Auto-select the first (latest) if available
            if (apSelect.options.length > 1) apSelect.selectedIndex = 1;
            if (smSelect.options.length > 1) smSelect.selectedIndex = 1;

            document.getElementById('automateModal').style.display = 'flex';
        }

        document.getElementById('automateForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const oldAp = document.getElementById('oldApLayerSelect').value;
            const apUrl = document.getElementById('newApUrl').value;
            const apFile = document.getElementById('newApFile').files[0];

            const oldSm = document.getElementById('oldSmLayerSelect').value;
            const smUrl = document.getElementById('newSmUrl').value;
            const smFile = document.getElementById('newSmFile').files[0];

            const updateDate = document.getElementById('updateDate').value;

            if (!apUrl && !smUrl && !apFile && !smFile) {
                alert('Please provide at least one URL or File');
                return;
            }

            const btn = document.getElementById('automateBtn');
            const status = document.getElementById('automateStatus');

            btn.disabled = true;
            btn.textContent = 'Processing (This may take a minute)...';
            status.style.display = 'block';
            status.style.color = '#e2e8f0';
            status.textContent = 'Downloading and running QGIS models...';

            const formData = new FormData();
            formData.append('new_ap_url', apUrl);
            formData.append('new_sm_url', smUrl);
            formData.append('old_ap_filename', oldAp);
            formData.append('old_sm_filename', oldSm);
            formData.append('update_date', updateDate);
            if (apFile) formData.append('new_ap_file', apFile);
            if (smFile) formData.append('new_sm_file', smFile);

            try {
                const response = await fetch('/api/process_updates', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok) {
                    let msg = "Success! Generated:<br>";

                    // Copy existing styles to the newly generated layers locally before loading
                    data.results.forEach(r => {
                        if(r.status === 'success') {
                            msg += r.new_files.join('<br>') + '<br>';

                            // Extract filenames for mapping. new_files[0] = Map, new_files[1] = Pins
                            const newMap = r.new_files[0];
                            const newPins = r.new_files[1];

                            if (r.layer === 'AP Map') {
                                const oldApMap = document.getElementById('oldApLayerSelect').value;
                                const oldApPins = oldApMap.replace('Map', 'Pins');

                                if (layerStyles[oldApMap] && newMap) layerStyles[newMap] = JSON.parse(JSON.stringify(layerStyles[oldApMap]));
                                if (layerStyles[oldApPins] && newPins) layerStyles[newPins] = JSON.parse(JSON.stringify(layerStyles[oldApPins]));
                            } else if (r.layer === 'SM Map') {
                                const oldSmMap = document.getElementById('oldSmLayerSelect').value;
                                const oldSmPins = oldSmMap.replace('Map', 'Pins');

                                if (layerStyles[oldSmMap] && newMap) layerStyles[newMap] = JSON.parse(JSON.stringify(layerStyles[oldSmMap]));
                                if (layerStyles[oldSmPins] && newPins) layerStyles[newPins] = JSON.parse(JSON.stringify(layerStyles[oldSmPins]));
                            }
                        } else {
                            msg += `<span style="color:var(--danger-color)">Error processing ${r.layer || ''}: ${r.message}</span><br>`;
                        }
                    });

                    // Save copied styles to backend
                    await saveStylesToServer();

                    status.innerHTML = msg;
                    status.style.color = 'var(--success-color)';

                    // Reload layers to get the new maps with styles applied
                    await loadLayers();

                    // Find the newly generated date on the timeline and jump to it
                    setTimeout(() => {
                        if (availableDates.length > 0) {
                            const newDateIdx = availableDates.indexOf(updateDate);
                            if (newDateIdx !== -1) {
                                const slider = document.getElementById('timelineSlider');
                                slider.value = newDateIdx;
                                slider.dispatchEvent(new Event('input'));

                                // Make sure the newly added layers are ticked
                                data.results.forEach(r => {
                                    if(r.status === 'success' && r.new_files) {
                                        r.new_files.forEach(fn => {
                                            const chk = document.getElementById('chk_' + fn);
                                            if (chk && !chk.checked) {
                                                chk.checked = true;
                                                chk.dispatchEvent(new Event('change'));
                                            }
                                        });
                                    }
                                });
                            }
                        }
                    }, 500); // small delay to ensure layers loaded

                    setTimeout(() => {
                        document.getElementById('automateModal').style.display = 'none';
                    }, 4000);
                } else {
                    status.textContent = 'Error: ' + (data.detail || 'Unknown error');
                    status.style.color = 'var(--danger-color)';
                }
            } catch (err) {
                status.textContent = 'Network error communicating with server.';
                status.style.color = 'var(--danger-color)';
                console.error(err);
            } finally {
                btn.disabled = false;
                btn.textContent = 'Run Update';
            }
        });

        function saveLayerOrder() {
            const items = document.querySelectorAll('.layer-item');
            const newOrder = [];
            items.forEach(item => newOrder.push(item.dataset.filename));

            appSettings.layerOrder = newOrder;
            saveStylesToServer(); // Persist to backend

            reorderActiveLayers();
        }


        // --- Export KML ---
        function exportKML() {
            const features = [];
            for (const filename in activeLayers) {
                if (activeLayers.hasOwnProperty(filename)) {
                    activeLayers[filename].eachLayer(layer => {
                        if (layer.feature) {
                            features.push(layer.feature);
                        }
                    });
                }
            }

            if (features.length === 0) {
                alert("No data to export.");
                return;
            }

            const geoJsonData = {
                type: "FeatureCollection",
                features: features
            };

            try {
                const kmlStr = tokml(geoJsonData, {
                    documentName: "MyMaps Export",
                    documentDescription: "Exported from MyMaps Clone",
                    name: "name",
                    description: "description"
                });

                const blob = new Blob([kmlStr], { type: "application/vnd.google-earth.kml+xml" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "export.kml";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            } catch (err) {
                console.error("Error exporting KML:", err);
                alert("Failed to export KML.");
            }
        }




        // --- Styling Logic ---
        let currentStylingFeatures = [];

        function openColorPicker(filename) {
            currentStylingLayer = filename;
            document.getElementById('stylingLayerName').textContent = filename;

            // Get features for the current layer to find unique names
            if (activeLayers[filename]) {
                const layer = activeLayers[filename];
                currentStylingFeatures = [];
                layer.eachLayer(l => {
                    if (l.feature) currentStylingFeatures.push(l.feature);
                });
            }

            const existingStyle = layerStyles[filename] || { type: 'single', color: '#3b82f6', opacity: 0.5 };
            document.getElementById('styleTypeSelect').value = existingStyle.type || 'single';

            renderColorPickers(existingStyle);

            document.getElementById('colorModal').style.display = 'flex';
        }

        function renderColorPickers(existingStyle = null) {
            const container = document.getElementById('colorPickerContainer');
            const type = document.getElementById('styleTypeSelect').value;
            container.innerHTML = ''; // Clear existing

            document.getElementById('globalMarkerType').value = existingStyle?.markerType || 'circle';
            document.getElementById('globalMarkerIcon').value = existingStyle?.markerIcon || '';
            document.getElementById('globalMarkerBorder').value = existingStyle?.markerBorder || '#ffffff';

            if (type === 'single') {
                const color = existingStyle?.color || '#3b82f6';
                const opacity = existingStyle?.opacity !== undefined ? existingStyle.opacity : 0.5;

                container.innerHTML = `
                    <div style="margin-bottom: 10px; display: flex; flex-direction: column; gap: 5px;">
                        <label>Color:</label>
                        <input type="color" id="singleColor" value="${color}" style="width: 100%; height: 30px;">
                        <label>Opacity: <span id="singleOpacityVal">${opacity}</span></label>
                        <input type="range" id="singleOpacity" min="0" max="1" step="0.1" value="${opacity}" oninput="document.getElementById('singleOpacityVal').textContent=this.value">
                    </div>
                `;
            } else if (type === 'grouped') {
                const uniqueNames = new Set();
                currentStylingFeatures.forEach(f => {
                    if (f.properties && f.properties.name) {
                        uniqueNames.add(f.properties.name);
                    }
                });

                if (uniqueNames.size === 0) {
                    container.innerHTML = '<p style="font-size: 0.85rem; color: #cbd5e1;">No named features found in this layer.</p>';
                    return;
                }

                Array.from(uniqueNames).sort().forEach((name, index) => {
                    const style = (existingStyle?.styles && existingStyle.styles[name]) || { color: '#3b82f6', opacity: 0.5, markerType: '', markerIcon: '', markerBorder: '' };

                    const row = document.createElement('div');
                    row.style.cssText = "margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid var(--border-color);";

                    row.innerHTML = `
                        <div style="font-size: 0.9rem; font-weight: bold; margin-bottom: 5px; word-break: break-all;">${name}</div>
                        <div style="display: flex; flex-direction: column; gap: 5px;">
                            <div style="display: flex; gap: 10px; align-items: center;">
                                <label style="width: 60px;">Color:</label>
                                <input type="color" class="groupColor" data-name="${name}" value="${style.color || '#3b82f6'}" style="flex-grow: 1; height: 30px;">
                            </div>
                            <div style="display: flex; gap: 10px; align-items: center;">
                                <label style="width: 60px;">Opacity:</label>
                                <input type="range" class="groupOpacity" data-name="${name}" min="0" max="1" step="0.1" value="${style.opacity !== undefined ? style.opacity : 0.5}" style="flex-grow: 1;" oninput="this.nextElementSibling.textContent=this.value">
                                <span style="width: 25px; font-size: 0.85rem;">${style.opacity !== undefined ? style.opacity : 0.5}</span>
                            </div>
                            <div style="display: flex; gap: 10px; align-items: center; margin-top: 5px;">
                                <select class="groupMarkerType" data-name="${name}" style="width: 40%; background: var(--border-color); color: white; border: none; padding: 2px; border-radius: 4px;">
                                    <option value="" ${!style.markerType ? 'selected' : ''}>Inherit</option>
                                    <option value="circle" ${style.markerType==='circle' ? 'selected' : ''}>Circle</option>
                                    <option value="icon" ${style.markerType==='icon' ? 'selected' : ''}>Image URL</option>
                                    <option value="emoji" ${style.markerType==='emoji' ? 'selected' : ''}>Emoji</option>
                                </select>
                                <input type="text" class="groupMarkerIcon" data-name="${name}" value="${style.markerIcon || ''}" placeholder="Icon/Emoji" style="flex-grow: 1; background: var(--border-color); color: white; border: none; padding: 2px; border-radius: 4px;">
                            </div>
                            <div style="display: flex; gap: 10px; align-items: center;">
                                <label style="width: 60px;">Border:</label>
                                <input type="color" class="groupMarkerBorder" data-name="${name}" value="${style.markerBorder || '#ffffff'}" style="flex-grow: 1; height: 30px;">
                            </div>
                        </div>
                    `;
                    container.appendChild(row);
                });
            }
        }

        function applyStyle() {
            if (!currentStylingLayer) return;

            const type = document.getElementById('styleTypeSelect').value;
            let styleConfig = { type: type };

            styleConfig.markerType = document.getElementById('globalMarkerType').value;
            styleConfig.markerIcon = document.getElementById('globalMarkerIcon').value;
            styleConfig.markerBorder = document.getElementById('globalMarkerBorder').value;

            if (type === 'single') {
                const colorInput = document.getElementById('singleColor');
                const opacityInput = document.getElementById('singleOpacity');
                if (!colorInput) return; // Safely handle if empty

                styleConfig.color = colorInput.value;
                styleConfig.opacity = parseFloat(opacityInput.value);
            } else if (type === 'grouped') {
                styleConfig.styles = {};
                const colorInputs = document.querySelectorAll('.groupColor');
                const opacityInputs = document.querySelectorAll('.groupOpacity');
                const markerTypeInputs = document.querySelectorAll('.groupMarkerType');
                const markerIconInputs = document.querySelectorAll('.groupMarkerIcon');
                const markerBorderInputs = document.querySelectorAll('.groupMarkerBorder');

                colorInputs.forEach((input, index) => {
                    const name = input.getAttribute('data-name');
                    const opacity = parseFloat(opacityInputs[index].value);

                    let groupStyle = { color: input.value, opacity: opacity };

                    if (markerTypeInputs[index] && markerTypeInputs[index].value) {
                         groupStyle.markerType = markerTypeInputs[index].value;
                    }
                    if (markerIconInputs[index] && markerIconInputs[index].value) {
                         groupStyle.markerIcon = markerIconInputs[index].value;
                    }
                    if (markerBorderInputs[index] && markerBorderInputs[index].value) {
                         groupStyle.markerBorder = markerBorderInputs[index].value;
                    }

                    styleConfig.styles[name] = groupStyle;
                });
            }

            layerStyles[currentStylingLayer] = styleConfig;
            saveStylesToServer();

            // Reload just this layer to apply style
            fetchAndAddKML(currentStylingLayer).then(() => {
                reorderActiveLayers();
            });
            document.getElementById('colorModal').style.display = 'none';
        }

        // --- Delete Logic ---
        async function deleteLayer(filename) {
            if (!confirm(`Are you sure you want to delete ${filename}?`)) return;

            try {
                // Ensure backend has: @app.delete("/api/layers/{filename}") route
                const res = await fetch(`/api/layers/${filename}`, { method: 'DELETE' });
                if (res.ok || res.status === 404) { // Treat 404 as already gone just in case
                    if (activeLayers[filename]) {
                        map.removeLayer(activeLayers[filename]);
                        delete activeLayers[filename];
                    }
                    loadLayers().then(() => updateTimeline()); // Refresh UI list
                } else {
                    alert("Failed to delete. Have you added the DELETE route to main.py?");
                }
            } catch (err) {
                console.error(err);
                alert("Error communicating with backend.");
            }
        }

        // 4. Handle File Uploads
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById('kmlFile');
            if (fileInput.files.length === 0) return;

            const formData = new FormData();
            for (let i = 0; i < fileInput.files.length; i++) {
                formData.append('files', fileInput.files[i]);
            }

            const btn = document.getElementById('uploadBtn');
            const statusMsg = document.getElementById('statusMsg');

            btn.disabled = true;
            btn.textContent = 'Uploading...';
            statusMsg.style.display = 'none';
            statusMsg.classList.remove('error-msg');

            try {
                const response = await fetch('/api/upload', { method: 'POST', body: formData });
                if (response.ok) {
                    statusMsg.textContent = 'Upload complete!';
                    statusMsg.style.display = 'block';
                    fileInput.value = '';
                    loadLayers();
                } else {
                    throw new Error('Upload failed');
                }
            } catch (err) {
                statusMsg.textContent = 'Error uploading file.';
                statusMsg.classList.add('error-msg');
                statusMsg.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.textContent = 'Upload KML / KMZ';
                setTimeout(() => { if (!statusMsg.classList.contains('error-msg')) statusMsg.style.display = 'none'; }, 3000);
            }
        });

        async function saveSettings() {
            appSettings.defaultLat = parseFloat(document.getElementById('defaultLat').value);
            appSettings.defaultLng = parseFloat(document.getElementById('defaultLng').value);
            appSettings.defaultZoom = parseFloat(document.getElementById('defaultZoom').value);
            appSettings.defaultBasemap = document.getElementById('defaultBasemap').value;
            appSettings.layerStyles = layerStyles;

            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(appSettings)
                });
                if (response.ok) {
                    document.getElementById('settingsModal').style.display = 'none';
                    alert('Settings saved!');
                } else {
                    alert('Failed to save settings.');
                }
            } catch (err) {
                console.error(err);
                alert('Error saving settings.');
            }
        }

        async function saveStylesToServer() {
            appSettings.layerStyles = layerStyles;
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(appSettings)
                });
                updateTimeline();
                reorderActiveLayers();
                // Force dispatch the event so the map actually updates to only show the latest
                const slider = document.getElementById('timelineSlider');
                slider.dispatchEvent(new Event('input'));
            } catch (err) {
                console.error('Error saving styles:', err);
            }
        }


        // 5. Override Geocodes
                        document.getElementById('overrideForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const locationName = document.getElementById('overrideLocationName').value;
            const osmId = document.getElementById('overrideOsmId').value;
            const englishName = document.getElementById('overrideEnglishName').value;
            const suppress = document.getElementById('overrideSuppress').checked;

            const btn = document.getElementById('overrideBtn');
            const statusMsg = document.getElementById('overrideStatusMsg');

            btn.disabled = true;
            statusMsg.style.display = 'none';
            statusMsg.classList.remove('error-msg');

            try {
                const response = await fetch('/api/admin/geocode_override', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ location_name: locationName, osm_id: osmId, english_name: englishName, suppress: suppress })
                });
                const data = await response.json();
                if (response.ok && data.status === 'success') {
                    statusMsg.textContent = 'Override saved! (Map updated)';
                    statusMsg.style.display = 'block';
                    document.getElementById('overrideOsmId').value = '';
                    document.getElementById('overrideEnglishName').value = '';
                    document.getElementById('overrideSuppress').checked = false;

                    // Trigger map update automatically
                    if (window.forceRadarRefresh) {
                        window.forceRadarRefresh();
                    }
                } else {
                    throw new Error(data.message || 'Override failed');
                }
            } catch (err) {
                statusMsg.textContent = 'Error: ' + err.message;
                statusMsg.classList.add('error-msg');
                statusMsg.style.display = 'block';
            } finally {
                btn.disabled = false;
                setTimeout(() => { if (!statusMsg.classList.contains('error-msg')) statusMsg.style.display = 'none'; }, 4000);
            }
        });

        // Settings UI Logic

        window.openSettingsModal = function() {
            document.getElementById('defaultLat').value = appSettings.defaultLat || 49.0;
            document.getElementById('defaultLng').value = appSettings.defaultLng || 31.0;
            document.getElementById('defaultZoom').value = appSettings.defaultZoom || 6;
            document.getElementById('defaultBasemap').value = appSettings.defaultBasemap || 'dark';
            document.getElementById('settingsModal').style.display = 'flex';
        };

        function useCurrentView() {
            const center = map.getCenter();
            document.getElementById('defaultLat').value = center.lat.toFixed(5);
            document.getElementById('defaultLng').value = center.lng.toFixed(5);
            document.getElementById('defaultZoom').value = map.getZoom();
        }
// Shadow Fleet Upload Handler
setTimeout(() => {
    document.getElementById('shadowFleetForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('shadowFile');
        if (fileInput.files.length === 0) return;

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        const btn = document.getElementById('shadowBtn');
        const statusMsg = document.getElementById('shadowStatusMsg');
        btn.textContent = 'Uploading...';
        statusMsg.style.display = 'none';

        try {
            const response = await fetch('/api/admin/upload_shadow_fleet', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Upload failed: ' + response.statusText);

            btn.textContent = 'Upload Shadow Fleet Target List';
            statusMsg.textContent = 'Upload complete!';
            statusMsg.style.color = '#10b981';
            statusMsg.style.display = 'block';
            fileInput.value = '';

            setTimeout(() => {
                statusMsg.style.display = 'none';
            }, 3000);

        } catch (error) {
            console.error('Error uploading shadow fleet:', error);
            btn.textContent = 'Upload Shadow Fleet Target List';
            statusMsg.textContent = 'Upload failed.';
            statusMsg.style.color = '#ef4444';
            statusMsg.style.display = 'block';
        }
    });
}, 1000);

        window.editKmlFeature = function(filename, indexStr) {
            const index = parseInt(indexStr);
            if (index < 0 || !activeKMLGeoJSON[filename] || !activeKMLGeoJSON[filename].features[index]) {
                alert("Feature not found.");
                return;
            }

            const feature = activeKMLGeoJSON[filename].features[index];
            const props = feature.properties || {};

            document.getElementById('editFeatureTitle').textContent = 'Edit Marker';
            document.getElementById('editFeatureLayer').value = filename;
            document.getElementById('editFeatureId').value = index;

            document.getElementById('editFeatureName').value = props.name || '';

            if (feature.geometry && feature.geometry.type === 'Point') {
                document.getElementById('editFeatureLng').value = feature.geometry.coordinates[0];
                document.getElementById('editFeatureLat').value = feature.geometry.coordinates[1];
            } else {
                document.getElementById('editFeatureLng').value = '';
                document.getElementById('editFeatureLat').value = '';
            }

            document.getElementById('editFeatureMarkerType').value = props.markerType || '';
            document.getElementById('editFeatureMarkerIcon').value = props.markerIcon || props.icon || '';
            document.getElementById('editFeatureMarkerColor').value = props.markerColor || '#3b82f6';
            document.getElementById('editFeatureMarkerBorder').value = props.markerBorder || '#ffffff';

            // Close any map popups so it doesn't get in the way
            if (map) map.closePopup();
            document.getElementById('editFeatureModal').style.display = 'flex';
        };

        window.addNewMarker = function() {
            // Find a valid KML layer to add to. Use the first static layer by default.
            const staticItems = document.querySelectorAll('#staticLayerList .layer-item');
            if (staticItems.length === 0) {
                alert("Please upload at least one KML layer first to hold the new marker.");
                return;
            }
            const filename = staticItems[0].dataset.filename;

            if (!activeKMLGeoJSON[filename]) {
                 alert("Layer not loaded yet. Please check the box to load it first.");
                 return;
            }

            document.getElementById('editFeatureTitle').textContent = 'Add New Marker to ' + filename;
            document.getElementById('editFeatureLayer').value = filename;
            document.getElementById('editFeatureId').value = '-1'; // -1 means new

            document.getElementById('editFeatureName').value = 'New Marker';

            const center = map.getCenter();
            document.getElementById('editFeatureLng').value = center.lng.toFixed(5);
            document.getElementById('editFeatureLat').value = center.lat.toFixed(5);

            document.getElementById('editFeatureMarkerType').value = '';
            document.getElementById('editFeatureMarkerIcon').value = '';
            document.getElementById('editFeatureMarkerColor').value = '#3b82f6';
            document.getElementById('editFeatureMarkerBorder').value = '#ffffff';

            if (map) map.closePopup();
            document.getElementById('editFeatureModal').style.display = 'flex';
        };

        window.useClickForLocation = function() {
            document.getElementById('editFeatureModal').style.display = 'none';
            window.isAwaitingLocationClick = true;
            document.body.style.cursor = 'crosshair';

            window.populateLocationFromClick = function(lat, lng) {
                document.getElementById('editFeatureLat').value = lat.toFixed(5);
                document.getElementById('editFeatureLng').value = lng.toFixed(5);

                window.isAwaitingLocationClick = false;
                document.body.style.cursor = '';
                delete window.populateLocationFromClick;

                document.getElementById('editFeatureModal').style.display = 'flex';
            };
        };

        window.saveKmlToServer = async function(filename) {
            if (!activeKMLGeoJSON[filename]) return;

            try {
                // Remove the internal .id properties we added so tokml doesn't encode them uselessly
                const geoJsonClone = JSON.parse(JSON.stringify(activeKMLGeoJSON[filename]));
                geoJsonClone.features.forEach(f => delete f.id);

                const kmlStr = tokml(geoJsonClone, {
                    name: 'name',
                    description: 'description'
                });

                const blob = new Blob([kmlStr], { type: "application/vnd.google-earth.kml+xml" });
                const file = new File([blob], filename, { type: "application/vnd.google-earth.kml+xml" });

                const formData = new FormData();
                formData.append('files', file);

                const response = await fetch('/api/upload', { method: 'POST', body: formData });
                if (!response.ok) throw new Error('Upload failed');

                // Success! Force a re-fetch of this layer to ensure UI sync
                if (map.hasLayer(activeLayers[filename])) {
                   await fetchAndAddKML(filename);
                   reorderActiveLayers();
                }
            } catch(e) {
                console.error("Failed to save KML to server", e);
                alert("Failed to save changes to the server.");
            }
        };

        window.saveEditedFeature = async function() {
            const filename = document.getElementById('editFeatureLayer').value;
            const index = parseInt(document.getElementById('editFeatureId').value);

            if (!activeKMLGeoJSON[filename]) return;

            const lat = parseFloat(document.getElementById('editFeatureLat').value);
            const lng = parseFloat(document.getElementById('editFeatureLng').value);

            if (isNaN(lat) || isNaN(lng)) {
                alert("Invalid coordinates");
                return;
            }

            let feature;
            if (index === -1) {
                feature = {
                    type: "Feature",
                    geometry: { type: "Point", coordinates: [lng, lat] },
                    properties: {},
                    id: filename + '_' + activeKMLGeoJSON[filename].features.length
                };
                activeKMLGeoJSON[filename].features.push(feature);
            } else {
                feature = activeKMLGeoJSON[filename].features[index];
                if (feature.geometry.type === 'Point') {
                    feature.geometry.coordinates = [lng, lat];
                }
            }

            if (!feature.properties) feature.properties = {};

            feature.properties.name = document.getElementById('editFeatureName').value;

            const markerType = document.getElementById('editFeatureMarkerType').value;
            if (markerType) feature.properties.markerType = markerType;
            else delete feature.properties.markerType;

            const markerIcon = document.getElementById('editFeatureMarkerIcon').value;
            if (markerIcon) feature.properties.markerIcon = markerIcon;
            else delete feature.properties.markerIcon;

            const markerColor = document.getElementById('editFeatureMarkerColor').value;
            if (markerColor !== '#3b82f6' && markerColor !== '#000000') feature.properties.markerColor = markerColor;
            else delete feature.properties.markerColor;

            const markerBorder = document.getElementById('editFeatureMarkerBorder').value;
            if (markerBorder !== '#ffffff' && markerBorder !== '#000000') feature.properties.markerBorder = markerBorder;
            else delete feature.properties.markerBorder;

            document.getElementById('editFeatureModal').style.display = 'none';
            await window.saveKmlToServer(filename);
        };

        window.deleteEditedFeature = async function() {
            const filename = document.getElementById('editFeatureLayer').value;
            const index = parseInt(document.getElementById('editFeatureId').value);

            if (index === -1) {
                document.getElementById('editFeatureModal').style.display = 'none';
                return;
            }

            if (confirm("Are you sure you want to delete this marker?")) {
                activeKMLGeoJSON[filename].features.splice(index, 1);

                // Reassign IDs
                activeKMLGeoJSON[filename].features.forEach((f, idx) => {
                    f.id = filename + '_' + idx;
                });

                document.getElementById('editFeatureModal').style.display = 'none';
                await window.saveKmlToServer(filename);
            }
        };

        window.uploadMarkerImage = async function(inputEl) {
            if (!inputEl.files || inputEl.files.length === 0) return;
            const file = inputEl.files[0];
            const formData = new FormData();
            formData.append('file', file);

            const statusEl = document.getElementById('editFeatureImageStatus');
            statusEl.textContent = 'Uploading...';
            statusEl.style.color = '#94a3b8';
            statusEl.style.display = 'block';

            try {
                const response = await fetch('/api/upload_image', { method: 'POST', body: formData });
                const result = await response.json();

                if (response.ok && result.status === 'success') {
                    document.getElementById('editFeatureMarkerIcon').value = result.filename;
                    document.getElementById('editFeatureMarkerType').value = 'icon';
                    statusEl.textContent = 'Uploaded successfully!';
                    statusEl.style.color = '#10b981';
                } else {
                    statusEl.textContent = 'Upload failed: ' + (result.message || '');
                    statusEl.style.color = '#ef4444';
                }
            } catch (err) {
                statusEl.textContent = 'Upload error.';
                statusEl.style.color = '#ef4444';
            }
            setTimeout(() => statusEl.style.display = 'none', 3000);
        };
