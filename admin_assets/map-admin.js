
// --- map-admin.js ---

// --- 1. Inject Admin HTML & Modals ---

// Add the Settings Button to the Admin Panel
document.getElementById('admin-panel-container').innerHTML = `
    <div class="section-header collapsed" onclick="toggleSection(this)">
        Map Admin <span class="toggle-icon">▼</span>
    </div>
    <div class="section-content collapsed upload-section" style="border-top: none; padding-top: 10px;">
        <form id="uploadForm">
            <input type="file" id="kmlFile" accept=".kml,.kmz" multiple required />
            <button type="submit" id="uploadBtn" class="primary-btn">Upload KML / KMZ</button>
            <div id="statusMsg" class="status-msg">Upload complete!</div>
        </form>
        <button class="primary-btn" onclick="openAutomateModal()" style="width: 100%; margin-top: 10px; background: #8b5cf6;">🤖 Automate Map Update</button>
        <button class="primary-btn" onclick="document.getElementById('settingsModal').style.display='flex'" style="width: 100%; margin-top: 10px; background: #0ea5e9;">⚙️ Map Settings</button>
        <button class="primary-btn" onclick="exportKML()" style="width: 100%; margin-top: 10px; background: var(--border-color);">⬇️ Export Displayed Data</button>
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

            <div id="colorPickerContainer" style="max-height: 300px; overflow-y: auto; margin-bottom: 15px; padding-right: 5px;"></div>

            <button class="primary-btn" onclick="applyStyle()" style="width:100%; margin-bottom: 10px;">Save Style</button>
            <button class="primary-btn" onclick="document.getElementById('colorModal').style.display='none'" style="width:100%; background:var(--border-color);">Close</button>
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
                    const style = (existingStyle?.styles && existingStyle.styles[name]) || { color: '#3b82f6', opacity: 0.5 };

                    const row = document.createElement('div');
                    row.style.cssText = "margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid var(--border-color);";

                    row.innerHTML = `
                        <div style="font-size: 0.9rem; font-weight: bold; margin-bottom: 5px; word-break: break-all;">${name}</div>
                        <div style="display: flex; flex-direction: column; gap: 5px;">
                            <div style="display: flex; gap: 10px; align-items: center;">
                                <label style="width: 60px;">Color:</label>
                                <input type="color" class="groupColor" data-name="${name}" value="${style.color}" style="flex-grow: 1; height: 30px;">
                            </div>
                            <div style="display: flex; gap: 10px; align-items: center;">
                                <label style="width: 60px;">Opacity:</label>
                                <input type="range" class="groupOpacity" data-name="${name}" min="0" max="1" step="0.1" value="${style.opacity}" style="flex-grow: 1;" oninput="this.nextElementSibling.textContent=this.value">
                                <span style="width: 25px; font-size: 0.85rem;">${style.opacity}</span>
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

                colorInputs.forEach((input, index) => {
                    const name = input.getAttribute('data-name');
                    const opacity = parseFloat(opacityInputs[index].value);
                    styleConfig.styles[name] = { color: input.value, opacity: opacity };
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

        // Settings UI Logic
        document.getElementById('settingsBtn').addEventListener('click', () => {
            document.getElementById('defaultLat').value = appSettings.defaultLat || 49.0;
            document.getElementById('defaultLng').value = appSettings.defaultLng || 31.0;
            document.getElementById('defaultZoom').value = appSettings.defaultZoom || 6;
            document.getElementById('defaultBasemap').value = appSettings.defaultBasemap || 'dark';
            document.getElementById('settingsModal').style.display = 'flex';
        });

        function useCurrentView() {
            const center = map.getCenter();
            document.getElementById('defaultLat').value = center.lat.toFixed(5);
            document.getElementById('defaultLng').value = center.lng.toFixed(5);
            document.getElementById('defaultZoom').value = map.getZoom();
        }        