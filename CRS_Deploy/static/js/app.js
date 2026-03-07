/* ══════════════════════════════════════════════════════════════
   Criminal Recognition System — App Logic
   ══════════════════════════════════════════════════════════════ */

// ── State ──────────────────────────────────────────────────────
let authToken = localStorage.getItem('crs_token') || null;
let currentUser = JSON.parse(localStorage.getItem('crs_user') || 'null');
let currentPage = 'dashboard';
let selectedFile = null;
let selectedPersonId = null;
let personSearchTimeout = null;

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    if (authToken && currentUser) {
        showApp();
        loadDashboard();
    } else {
        showLogin();
    }
});

// ── API Client ─────────────────────────────────────────────────
async function api(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    if (!(options.body instanceof FormData) && options.body) {
        headers['Content-Type'] = 'application/json';
    }

    try {
        const res = await fetch(url, { ...options, headers });
        if (res.status === 401) {
            handleLogout();
            throw new Error('Session expired');
        }
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(err.detail || 'Request failed');
        }
        return await res.json();
    } catch (e) {
        if (e.message !== 'Session expired') showToast(e.message, 'error');
        throw e;
    }
}

// ── Auth ───────────────────────────────────────────────────────
async function handleLogin() {
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const btn = document.getElementById('loginBtn');
    const errorEl = document.getElementById('loginError');

    btn.disabled = true;
    btn.textContent = '⏳ Signing in...';
    errorEl.style.display = 'none';

    try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Login failed');
        }

        const data = await res.json();
        authToken = data.access_token;
        currentUser = data.officer;
        localStorage.setItem('crs_token', authToken);
        localStorage.setItem('crs_user', JSON.stringify(currentUser));

        showApp();
        loadDashboard();
        showToast(`Welcome, ${currentUser.full_name}!`, 'success');
    } catch (e) {
        errorEl.textContent = e.message;
        errorEl.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.textContent = '🔐 Sign In';
    }
}

function handleLogout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('crs_token');
    localStorage.removeItem('crs_user');
    showLogin();
}

function showLogin() {
    document.getElementById('loginPage').style.display = 'flex';
    document.getElementById('appShell').style.display = 'none';
}

function showApp() {
    document.getElementById('loginPage').style.display = 'none';
    document.getElementById('appShell').style.display = 'flex';
    updateUserInfo();
}

function updateUserInfo() {
    if (!currentUser) return;
    document.getElementById('userName').textContent = currentUser.full_name;
    document.getElementById('userRole').textContent = currentUser.role;
    document.getElementById('userAvatar').textContent = currentUser.full_name.charAt(0).toUpperCase();
}

// ── Navigation ─────────────────────────────────────────────────
function navigate(page) {
    currentPage = page;
    document.querySelectorAll('.page-section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const pageEl = document.getElementById(`page-${page}`);
    if (pageEl) pageEl.classList.add('active');

    const navEl = document.querySelector(`.nav-item[data-page="${page}"]`);
    if (navEl) navEl.classList.add('active');

    // Load page data
    switch (page) {
        case 'dashboard': loadDashboard(); break;
        case 'persons': loadPersons(); break;
        case 'audit': loadAuditLogs(); break;
        case 'bias': loadBiasData(); break;
    }
}

// ── Dashboard ──────────────────────────────────────────────────
async function loadDashboard() {
    try {
        const data = await api('/api/dashboard/stats');
        document.getElementById('statPersons').textContent = data.total_persons;
        document.getElementById('statRecords').textContent = data.total_records;
        document.getElementById('statSearches').textContent = data.total_searches;
        document.getElementById('statOfficers').textContent = data.total_officers;

        renderBarChart('riskChart', data.risk_distribution, {
            'High': 'var(--accent-red)',
            'Medium': 'var(--accent-amber)',
            'Low': 'var(--accent-emerald)',
        });

        renderBarChart('statusChart', data.status_distribution, {
            'Convicted': 'var(--accent-red)',
            'Under Investigation': 'var(--accent-amber)',
            'Clean': 'var(--accent-emerald)',
            'Released': 'var(--accent-blue)',
        });

        renderRecentActivity(data.recent_activity);
    } catch (e) { /* handled by api() */ }
}

function renderBarChart(containerId, data, colors) {
    const container = document.getElementById(containerId);
    if (!container || !data) return;
    const maxVal = Math.max(...Object.values(data), 1);

    container.innerHTML = Object.entries(data).map(([label, value]) => {
        const pct = Math.round((value / maxVal) * 100);
        const color = colors[label] || 'var(--accent-blue)';
        return `
            <div class="chart-bar-row">
                <div class="chart-bar-label">${label}</div>
                <div class="chart-bar-track">
                    <div class="chart-bar-fill" style="width:${pct}%;background:${color};">${value}</div>
                </div>
            </div>
        `;
    }).join('');
}

function renderRecentActivity(activities) {
    const tbody = document.getElementById('recentActivityTable');
    if (!activities || !activities.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state"><div class="empty-text">No recent activity</div></td></tr>';
        return;
    }

    tbody.innerHTML = activities.map(a => {
        const time = a.timestamp ? new Date(a.timestamp).toLocaleString() : '—';
        const badgeClass = `badge-action-${a.action_type.toLowerCase()}`;
        return `
            <tr>
                <td style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-muted);">${time}</td>
                <td>${a.officer_name}</td>
                <td><span class="badge ${badgeClass}">${a.action_type}</span></td>
                <td style="color:var(--text-secondary);font-size:12px;">${a.details || '—'}</td>
            </tr>
        `;
    }).join('');
}

// ── Face Search ────────────────────────────────────────────────
function switchSearchTab(tab) {
    document.querySelectorAll('#searchTabs .tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');

    if (tab === 'upload') {
        document.getElementById('uploadTab').style.display = 'block';
        document.getElementById('cameraTab').style.display = 'none';
        stopWebcam();
    } else {
        document.getElementById('uploadTab').style.display = 'none';
        document.getElementById('cameraTab').style.display = 'block';
        startWebcam();
    }
}

function handleDragOver(e) {
    e.preventDefault();
    document.getElementById('uploadZone').classList.add('drag-over');
}

function handleDragLeave(e) {
    document.getElementById('uploadZone').classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    document.getElementById('uploadZone').classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
        processFile(e.dataTransfer.files[0]);
    }
}

function handleFileSelect(e) {
    if (e.target.files.length > 0) {
        processFile(e.target.files[0]);
    }
}

function processFile(file) {
    if (!file.type.match(/^image\/(jpeg|png|webp)$/)) {
        showToast('Please upload a JPG, PNG, or WebP image', 'error');
        return;
    }
    selectedFile = file;
    const preview = document.getElementById('uploadPreview');
    const reader = new FileReader();
    reader.onload = (e) => {
        preview.src = e.target.result;
        preview.style.display = 'block';
        document.querySelector('#uploadZone .upload-icon').style.display = 'none';
        document.querySelector('#uploadZone .upload-text').style.display = 'none';
        document.querySelector('#uploadZone .upload-subtext').style.display = 'none';
    };
    reader.readAsDataURL(file);
    document.getElementById('searchBtn').disabled = false;
}

// Webcam
let webcamStream = null;

async function startWebcam() {
    try {
        webcamStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        const video = document.getElementById('webcamVideo');
        video.srcObject = webcamStream;
        video.style.display = 'block';
        // Hide capture preview if shown from previous capture
        document.getElementById('capturePreview').style.display = 'none';
        document.getElementById('captureOverlay').style.display = 'none';
    } catch (e) {
        showToast('Camera access denied or unavailable', 'error');
    }
}

function stopWebcam() {
    if (webcamStream) {
        webcamStream.getTracks().forEach(t => t.stop());
        webcamStream = null;
    }
}

function captureWebcam() {
    const video = document.getElementById('webcamVideo');
    const canvas = document.getElementById('webcamCanvas');
    const capturePreview = document.getElementById('capturePreview');
    const captureOverlay = document.getElementById('captureOverlay');

    if (!webcamStream) {
        showToast('Camera not active', 'error');
        return;
    }

    // Draw current frame to canvas
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext('2d').drawImage(video, 0, 0);

    // FREEZE: Stop the webcam stream immediately
    stopWebcam();
    video.style.display = 'none';

    // Show the captured frame as a frozen preview
    const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
    capturePreview.src = dataUrl;
    capturePreview.style.display = 'block';
    captureOverlay.style.display = 'flex';

    // Create file for search
    canvas.toBlob((blob) => {
        selectedFile = new File([blob], 'capture.jpg', { type: 'image/jpeg' });
        document.getElementById('searchBtn').disabled = false;
    }, 'image/jpeg', 0.95);

    showToast('📸 Photo captured! Click "Search Database" or "Retake" for a new photo.', 'success');
}

function retakePhoto() {
    document.getElementById('capturePreview').style.display = 'none';
    document.getElementById('captureOverlay').style.display = 'none';
    selectedFile = null;
    document.getElementById('searchBtn').disabled = true;
    startWebcam();
}

async function performSearch() {
    if (!selectedFile) return;

    const btn = document.getElementById('searchBtn');
    const resultsDiv = document.getElementById('searchResults');
    btn.disabled = true;
    btn.textContent = '⏳ Analyzing...';
    resultsDiv.innerHTML = '<div class="loading-overlay"><div class="spinner"></div><span>Detecting faces and searching database...</span></div>';

    try {
        const formData = new FormData();
        formData.append('image', selectedFile);
        formData.append('threshold', document.getElementById('searchThreshold').value);
        formData.append('max_results', document.getElementById('searchMaxResults').value);

        const data = await api('/api/search/face', { method: 'POST', body: formData });

        // Liveness check display
        renderLivenessCheck(data.liveness_check);

        // Results
        if (data.matches.length === 0) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">✅</div>
                    <div class="empty-text">No Matches Found</div>
                    <div class="empty-subtext">No persons in the database matched the uploaded face above the confidence threshold (${(data.threshold_used * 100).toFixed(0)}%).</div>
                </div>
            `;
            document.getElementById('resultCount').style.display = 'none';
        } else {
            document.getElementById('resultCount').style.display = 'inline-flex';
            document.getElementById('resultCount').textContent = `${data.total_matches} match${data.total_matches > 1 ? 'es' : ''}`;
            document.getElementById('resultCount').className = 'badge badge-action-search';

            resultsDiv.innerHTML = data.matches.map(m => {
                const confClass = m.confidence > 70 ? 'confidence-high' : m.confidence > 40 ? 'confidence-medium' : 'confidence-low';
                const confColor = m.confidence > 70 ? 'var(--accent-red)' : m.confidence > 40 ? 'var(--accent-amber)' : 'var(--accent-emerald)';
                const riskClass = m.risk_level ? m.risk_level.toLowerCase() : 'low';
                const statusBadge = getStatusBadge(m.record_status);

                return `
                    <div class="match-result" onclick="viewPersonDetail(${m.person_id}, ${m.confidence})">
                        <div class="match-header">
                            <div class="match-name">${m.full_name}</div>
                            <div class="match-confidence ${confClass}">${m.confidence.toFixed(1)}%</div>
                        </div>
                        <div class="match-meta">
                            ${statusBadge}
                            <div class="risk-indicator">
                                <div class="risk-dot ${riskClass}"></div>
                                <span style="font-size:12px;color:var(--text-secondary);">${m.risk_level || 'N/A'} Risk</span>
                            </div>
                            <span class="match-meta-item">📅 ${m.date_of_birth || 'N/A'}</span>
                            <span class="match-meta-item">🌍 ${m.nationality || 'N/A'}</span>
                        </div>
                        <div class="confidence-bar">
                            <div class="confidence-fill" style="width:${m.confidence}%;background:${confColor};"></div>
                        </div>
                    </div>
                `;
            }).join('');
        }
    } catch (e) {
        resultsDiv.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">❌</div>
                <div class="empty-text">Search Failed</div>
                <div class="empty-subtext">${e.message}</div>
            </div>
        `;
    } finally {
        btn.disabled = false;
        btn.textContent = '🔍 Search Database';
    }
}

function renderLivenessCheck(liveness) {
    if (!liveness) return;
    const card = document.getElementById('livenessCard');
    card.style.display = 'block';

    const statusEl = document.getElementById('livenessStatus');
    statusEl.textContent = liveness.passed ? '✅ Passed' : '⚠️ Warning';
    statusEl.className = `badge ${liveness.passed ? 'badge-risk-low' : 'badge-risk-medium'}`;

    const checksEl = document.getElementById('livenessChecks');
    checksEl.innerHTML = liveness.checks.map(c => `
        <div class="liveness-check-item ${c.passed ? 'passed' : 'failed'}">
            <div class="liveness-status">
                ${c.passed ? '✅' : '❌'} ${c.name}
            </div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">${c.detail}</div>
            <div style="font-size:11px;color:var(--text-secondary);margin-top:2px;">Score: ${c.score}</div>
        </div>
    `).join('');
}

// ── Person Detail ──────────────────────────────────────────────
async function viewPersonDetail(personId, confidence) {
    selectedPersonId = personId;
    navigate('person-detail');
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const content = document.getElementById('personDetailContent');
    content.innerHTML = '<div class="loading-overlay"><div class="spinner"></div><span>Loading person details...</span></div>';

    try {
        const person = await api(`/api/persons/${personId}`);
        const riskClass = (person.risk_level || 'low').toLowerCase();
        const confClass = confidence > 70 ? 'confidence-high' : confidence > 40 ? 'confidence-medium' : 'confidence-low';
        const initials = person.full_name.split(' ').map(n => n[0]).join('').toUpperCase();

        content.innerHTML = `
            <!-- Left Panel -->
            <div class="person-photo-section">
                <div class="card">
                    <div class="person-photo">${initials}</div>
                    ${confidence ? `
                        <div class="person-confidence ${confClass}">${confidence.toFixed(1)}%</div>
                        <div class="person-confidence-label">Match Confidence</div>
                    ` : ''}
                    <div style="display:flex;flex-direction:column;gap:8px;align-items:center;">
                        <div class="risk-indicator" style="justify-content:center;">
                            <div class="risk-dot ${riskClass}"></div>
                            <span style="font-weight:600;">${person.risk_level || 'N/A'} Risk</span>
                        </div>
                        ${getStatusBadge(person.record_status)}
                    </div>
                    <div style="margin-top:20px;">
                        <button class="btn btn-primary" style="width:100%" onclick="openAddRecordModal()">
                            ➕ Add Record
                        </button>
                    </div>
                </div>

                <div class="card" style="margin-top:16px;">
                    <div class="card-title" style="margin-bottom:12px;">📋 Identity</div>
                    <div style="display:flex;flex-direction:column;gap:8px;">
                        <div class="info-item">
                            <div class="info-label">Full Name</div>
                            <div class="info-value">${person.full_name}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Date of Birth</div>
                            <div class="info-value">${person.date_of_birth || 'N/A'}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Gender</div>
                            <div class="info-value">${person.gender || 'N/A'}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Nationality</div>
                            <div class="info-value">${person.nationality || 'N/A'}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Address</div>
                            <div class="info-value">${person.address || 'N/A'}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Government ID</div>
                            <div class="info-value">${person.government_id_number || 'N/A'}</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right Panel -->
            <div>
                <div class="card" style="margin-bottom:20px;">
                    <div class="card-header">
                        <div class="card-title">📜 Criminal History</div>
                        <span class="badge badge-action-search">${(person.criminal_records || []).length} record${(person.criminal_records || []).length !== 1 ? 's' : ''}</span>
                    </div>
                    ${person.criminal_records && person.criminal_records.length > 0 ? `
                        <div class="timeline">
                            ${person.criminal_records.map(r => `
                                <div class="timeline-item">
                                    <div class="timeline-crime-type">
                                        ⚖️ ${r.crime_type}
                                        ${r.conviction_status ? `<span class="badge ${getConvictionBadgeClass(r.conviction_status)}">${r.conviction_status}</span>` : ''}
                                    </div>
                                    ${r.crime_description ? `<p style="font-size:13px;color:var(--text-secondary);margin-bottom:10px;">${r.crime_description}</p>` : ''}
                                    <div class="timeline-details">
                                        <div class="timeline-detail-item">
                                            <div class="timeline-detail-label">Case Number</div>
                                            <div>${r.case_number || 'N/A'}</div>
                                        </div>
                                        <div class="timeline-detail-item">
                                            <div class="timeline-detail-label">Date of Offense</div>
                                            <div>${r.date_of_offense || 'N/A'}</div>
                                        </div>
                                        <div class="timeline-detail-item">
                                            <div class="timeline-detail-label">Arrest Date</div>
                                            <div>${r.arrest_date || 'N/A'}</div>
                                        </div>
                                        <div class="timeline-detail-item">
                                            <div class="timeline-detail-label">Sentence</div>
                                            <div>${r.sentence_details || 'N/A'}</div>
                                        </div>
                                        <div class="timeline-detail-item">
                                            <div class="timeline-detail-label">Agency</div>
                                            <div>${r.law_enforcement_agency || 'N/A'}</div>
                                        </div>
                                        <div class="timeline-detail-item">
                                            <div class="timeline-detail-label">Court</div>
                                            <div>${r.court_name || 'N/A'}</div>
                                        </div>
                                    </div>
                                    ${r.officer_notes ? `
                                        <div style="margin-top:10px;padding:10px;background:var(--bg-input);border-radius:var(--radius-sm);font-size:12px;color:var(--text-muted);">
                                            📝 ${r.officer_notes}
                                        </div>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : `
                        <div class="empty-state" style="padding:30px;">
                            <div class="empty-icon">📋</div>
                            <div class="empty-text">No Criminal Records</div>
                            <div class="empty-subtext">This person has no criminal records on file.</div>
                        </div>
                    `}
                </div>
            </div>
        `;
    } catch (e) {
        content.innerHTML = `<div class="empty-state"><div class="empty-icon">❌</div><div class="empty-text">Failed to Load</div><div class="empty-subtext">${e.message}</div></div>`;
    }
}

// ── Persons Database ───────────────────────────────────────────
let selectedPersonIds = new Set();
let deleteMode = false;
let loadedPersonIds = [];  // track all loaded person IDs for Select All

function toggleDeleteMode() {
    deleteMode = !deleteMode;
    const modeBtn = document.getElementById('deleteModeBtn');
    const actionBar = document.getElementById('deleteActionBar');

    if (deleteMode) {
        modeBtn.style.opacity = '1';
        modeBtn.style.boxShadow = '0 0 20px rgba(239, 68, 68, 0.5)';
        actionBar.style.display = 'flex';
        showToast('🗑️ Delete Mode ON — click on person cards to select them', 'warning');
    } else {
        modeBtn.style.opacity = '0.7';
        modeBtn.style.boxShadow = '';
        actionBar.style.display = 'none';
        selectedPersonIds.clear();
        // Remove all selected styles
        document.querySelectorAll('.person-card.selected').forEach(c => c.classList.remove('selected'));
    }
    updateDeleteUI();
}

function updateDeleteUI() {
    const countEl = document.getElementById('selectedCount');
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    const barText = document.getElementById('deleteBarText');

    countEl.textContent = selectedPersonIds.size;

    if (selectedPersonIds.size > 0) {
        confirmBtn.style.display = 'inline-flex';
        barText.textContent = `${selectedPersonIds.size} person(s) selected for deletion`;
    } else {
        confirmBtn.style.display = 'none';
        barText.textContent = 'Select persons to delete by clicking on their cards';
    }
}

function handlePersonCardClick(personId) {
    if (deleteMode) {
        // In delete mode: toggle selection
        if (selectedPersonIds.has(personId)) {
            selectedPersonIds.delete(personId);
        } else {
            selectedPersonIds.add(personId);
        }
        const card = document.getElementById(`person-card-${personId}`);
        if (card) card.classList.toggle('selected', selectedPersonIds.has(personId));
        updateDeleteUI();
    } else {
        // Normal mode: view person detail
        viewPersonDetail(personId);
    }
}

function selectAllPersons() {
    loadedPersonIds.forEach(id => {
        selectedPersonIds.add(id);
        const card = document.getElementById(`person-card-${id}`);
        if (card) card.classList.add('selected');
    });
    updateDeleteUI();
}

function deselectAllPersons() {
    selectedPersonIds.clear();
    document.querySelectorAll('.person-card.selected').forEach(c => c.classList.remove('selected'));
    updateDeleteUI();
}

async function deleteSelectedPersons() {
    if (selectedPersonIds.size === 0) return;

    const count = selectedPersonIds.size;
    const confirmed = confirm(
        `⚠️ DELETE ${count} PERSON(S)?\n\n` +
        `This will permanently delete:\n` +
        `• ${count} person record(s)\n` +
        `• All associated criminal records\n` +
        `• All associated photos & face data\n\n` +
        `This action CANNOT be undone. Continue?`
    );

    if (!confirmed) return;

    try {
        const result = await api('/api/persons/bulk-delete', {
            method: 'POST',
            body: JSON.stringify({ person_ids: Array.from(selectedPersonIds) }),
        });
        showToast(`✅ ${result.deleted_count} person(s) deleted: ${result.deleted_names.join(', ')}`, 'success');
        selectedPersonIds.clear();
        updateDeleteUI();
        toggleDeleteMode(); // Exit delete mode
        loadPersons();
        loadDashboard();
    } catch (e) { /* handled by api() */ }
}

async function loadPersons() {
    const grid = document.getElementById('personsGrid');
    grid.innerHTML = '<div class="loading-overlay"><div class="spinner"></div><span>Loading persons...</span></div>';

    try {
        const search = document.getElementById('personSearchInput').value;
        const status = document.getElementById('personStatusFilter').value;
        const risk = document.getElementById('personRiskFilter').value;
        let url = '/api/persons?limit=50';
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        if (risk) url += `&risk=${encodeURIComponent(risk)}`;

        const data = await api(url);
        if (data.persons.length === 0) {
            grid.innerHTML = '<div class="empty-state"><div class="empty-icon">👤</div><div class="empty-text">No Persons Found</div><div class="empty-subtext">Try adjusting your filters.</div></div>';
            loadedPersonIds = [];
            return;
        }

        loadedPersonIds = data.persons.map(p => p.id);

        grid.innerHTML = data.persons.map(p => {
            const initials = p.full_name.split(' ').map(n => n[0]).join('').toUpperCase();
            const riskClass = (p.risk_level || 'low').toLowerCase();
            const isSelected = selectedPersonIds.has(p.id);
            return `
                <div class="person-card ${isSelected ? 'selected' : ''}" id="person-card-${p.id}" onclick="handlePersonCardClick(${p.id})">
                    <div class="person-card-header">
                        <div class="person-card-avatar">${initials}</div>
                        <div>
                            <div class="person-card-name">${p.full_name}</div>
                            <div class="person-card-id">ID: ${p.id} · ${p.date_of_birth || 'DOB N/A'}</div>
                        </div>
                    </div>
                    <div class="person-card-meta">
                        ${getStatusBadge(p.record_status)}
                        <div class="risk-indicator">
                            <div class="risk-dot ${riskClass}"></div>
                            <span style="font-size:11px;">${p.risk_level || 'N/A'}</span>
                        </div>
                        <span class="badge" style="background:rgba(59,130,246,0.1);color:#60a5fa;font-size:10px;">${p.nationality || 'N/A'}</span>
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) { /* handled */ }
}

function debouncePersonSearch() {
    clearTimeout(personSearchTimeout);
    personSearchTimeout = setTimeout(() => loadPersons(), 300);
}

// ── Audit Log ──────────────────────────────────────────────────
async function loadAuditLogs() {
    const tbody = document.getElementById('auditTableBody');
    tbody.innerHTML = '<tr><td colspan="6"><div class="loading-overlay"><div class="spinner"></div><span>Loading...</span></div></td></tr>';

    try {
        const actionFilter = document.getElementById('auditActionFilter').value;
        let url = '/api/audit?limit=100';
        if (actionFilter) url += `&action_type=${encodeURIComponent(actionFilter)}`;

        const data = await api(url);
        if (data.logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="empty-text">No audit entries</div></div></td></tr>';
            return;
        }

        tbody.innerHTML = data.logs.map(log => {
            const time = log.timestamp ? new Date(log.timestamp).toLocaleString() : '—';
            const badgeClass = `badge-action-${log.action_type.toLowerCase()}`;
            return `
                <tr>
                    <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-muted);white-space:nowrap;">${time}</td>
                    <td>${log.officer_name}</td>
                    <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-muted);">${log.officer_badge || '—'}</td>
                    <td><span class="badge ${badgeClass}">${log.action_type}</span></td>
                    <td>${log.person_name ? `<a style="color:var(--accent-blue);cursor:pointer;" onclick="viewPersonDetail(${log.person_id})">${log.person_name}</a>` : '—'}</td>
                    <td style="color:var(--text-secondary);font-size:12px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${log.details || '—'}</td>
                </tr>
            `;
        }).join('');
    } catch (e) { /* handled */ }
}

// ── Bias Monitor ───────────────────────────────────────────────
async function loadBiasData() {
    try {
        const data = await api('/api/persons?limit=1000');
        const persons = data.persons;

        // Count distributions
        const genders = {}, nationalities = {}, risks = {}, statuses = {};
        persons.forEach(p => {
            const g = p.gender || 'Unknown'; genders[g] = (genders[g] || 0) + 1;
            const n = p.nationality || 'Unknown'; nationalities[n] = (nationalities[n] || 0) + 1;
            const r = p.risk_level || 'Unknown'; risks[r] = (risks[r] || 0) + 1;
            const s = p.record_status || 'Unknown'; statuses[s] = (statuses[s] || 0) + 1;
        });

        renderBarChart('biasGenderChart', genders, { 'Male': 'var(--accent-blue)', 'Female': 'var(--accent-violet)', 'Other': 'var(--accent-cyan)', 'Unknown': 'var(--text-muted)' });
        renderBarChart('biasNationalityChart', nationalities, {});
        renderBarChart('biasRiskChart', risks, { 'High': 'var(--accent-red)', 'Medium': 'var(--accent-amber)', 'Low': 'var(--accent-emerald)' });
        renderBarChart('biasStatusChart', statuses, { 'Convicted': 'var(--accent-red)', 'Under Investigation': 'var(--accent-amber)', 'Clean': 'var(--accent-emerald)', 'Released': 'var(--accent-blue)' });
    } catch (e) { /* handled */ }
}

// ── Modals ─────────────────────────────────────────────────────
function openAddRecordModal() {
    if (!selectedPersonId) {
        showToast('No person selected', 'error');
        return;
    }
    document.getElementById('recordPersonId').value = selectedPersonId;
    document.getElementById('addRecordForm').reset();
    document.getElementById('recordPersonId').value = selectedPersonId;
    openModal('addRecordModal');
}

function openAddPersonModal() {
    document.getElementById('addPersonForm').reset();
    openModal('addPersonModal');
}

function openModal(id) {
    document.getElementById(id).classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

async function submitAddRecord() {
    const personId = document.getElementById('recordPersonId').value;
    if (!personId) return;

    const body = {
        person_id: parseInt(personId),
        crime_type: document.getElementById('recordCrimeType').value,
        crime_description: document.getElementById('recordCrimeDescription').value,
        case_number: document.getElementById('recordCaseNumber').value,
        date_of_offense: document.getElementById('recordDateOfOffense').value,
        arrest_date: document.getElementById('recordArrestDate').value,
        conviction_status: document.getElementById('recordConvictionStatus').value,
        sentence_details: document.getElementById('recordSentenceDetails').value,
        law_enforcement_agency: document.getElementById('recordAgency').value,
        court_name: document.getElementById('recordCourtName').value,
        officer_notes: document.getElementById('recordOfficerNotes').value,
        update_record_status: document.getElementById('recordUpdateStatus').value || null,
        update_risk_level: document.getElementById('recordUpdateRisk').value || null,
    };

    if (!body.crime_type) {
        showToast('Crime type is required', 'error');
        return;
    }

    try {
        await api('/api/records', { method: 'POST', body: JSON.stringify(body) });
        closeModal('addRecordModal');
        showToast('✅ Criminal record added successfully', 'success');
        viewPersonDetail(parseInt(personId));
    } catch (e) { /* handled */ }
}

async function submitAddPerson() {
    const fullName = document.getElementById('personFullName').value;
    if (!fullName) {
        showToast('Full name is required', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('full_name', fullName);
    formData.append('date_of_birth', document.getElementById('personDob').value);
    formData.append('gender', document.getElementById('personGender').value);
    formData.append('nationality', document.getElementById('personNationality').value);
    formData.append('address', document.getElementById('personAddress').value);
    formData.append('government_id_number', document.getElementById('personGovId').value);
    formData.append('record_status', document.getElementById('personRecordStatus').value);
    formData.append('risk_level', document.getElementById('personRiskLevel').value);

    // Append ALL selected photos (multi-photo for robust face recognition)
    const photoInput = document.getElementById('personPhoto');
    const photoCount = photoInput.files.length;
    if (photoCount > 0) {
        for (let i = 0; i < photoCount; i++) {
            formData.append('photos', photoInput.files[i]);
        }
        showToast(`🧠 Processing ${photoCount} photo(s) for face recognition... This may take a few seconds.`, 'info');
    }

    try {
        await api('/api/persons', { method: 'POST', body: formData });
        closeModal('addPersonModal');
        showToast(`✅ Person "${fullName}" added with ${photoCount} photo(s) for face recognition`, 'success');
        loadPersons();
        loadDashboard();
    } catch (e) { /* handled */ }
}

// ── Helpers ────────────────────────────────────────────────────
function getStatusBadge(status) {
    const map = {
        'Convicted': 'badge-status-convicted',
        'Under Investigation': 'badge-status-investigation',
        'Clean': 'badge-status-clean',
        'Released': 'badge-status-released',
    };
    const cls = map[status] || 'badge-status-clean';
    return `<span class="badge ${cls}">${status || 'Unknown'}</span>`;
}

function getConvictionBadgeClass(status) {
    if (status === 'Convicted') return 'badge-risk-high';
    if (status === 'Pending Trial' || status === 'On Appeal') return 'badge-risk-medium';
    if (status === 'Acquitted' || status === 'Dismissed') return 'badge-risk-low';
    return '';
}

// ── Excel Export ───────────────────────────────────────────────
async function exportExcel() {
    showToast('Generating Excel file...', 'info');
    try {
        const res = await fetch('/api/export/excel', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Export failed' }));
            throw new Error(err.detail || 'Export failed');
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const disposition = res.headers.get('content-disposition') || '';
        const match = disposition.match(/filename=(.+)/);
        a.download = match ? match[1] : 'criminal_records.xlsx';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        showToast('Excel file downloaded!', 'success');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ── Toast Notifications ────────────────────────────────────────
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' }[type] || 'ℹ️';
    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Close modals on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.classList.remove('active');
    });
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    }
});
