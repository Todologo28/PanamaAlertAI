// PanamaAlert Enterprise — Interactive Map with AI Agents Integration
document.addEventListener('DOMContentLoaded', () => {
    const REFRESH_MS = 10000;
    const canReport = !window.publicView;
    let refreshTimer = null;
    let notificationTimer = null;
    let categories = [];
    let allIncidents = [];
    let lastIncidentsSignature = '';
    let sortedSidebarCache = [];
    const incidentDetailCache = new Map();
    let pendingLatLng = null;
    let selectedSev = 3;
    let userGpsMarker = null;
    let userGpsAccuracy = null;
    let userPreferences = {
        push_enabled: true,
        browser_notifications: false,
        min_alert_level: 'medium',
        incident_types: []
    };

    if (typeof L === 'undefined') { console.error('Leaflet not loaded'); return; }

    // ---- Map ----------------------------------------------------------------
    const map = L.map('map', { zoomControl: false, doubleClickZoom: false }).setView([8.983333, -79.516667], 13);
    map.createPane('labels');
    map.getPane('labels').style.zIndex = 620;
    map.getPane('labels').style.pointerEvents = 'none';

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://osm.org/copyright">OSM</a>'
    }).addTo(map);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        pane: 'labels'
    }).addTo(map);

    L.control.zoom({ position: 'topright' }).addTo(map);

    // Geofences - Leaflet.Draw
    if (L.Control && L.Control.Draw) {
        const drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);
        const drawControl = new L.Control.Draw({
            draw: { polygon: false, polyline: false, rectangle: false, marker: false, circlemarker: false },
            edit: false
        });
        map.addControl(drawControl);
        map.on('draw:created', (e) => {
            const layer = e.layer;
            if (layer instanceof L.Circle) {
                saveGeofence(layer.getLatLng().lat, layer.getLatLng().lng, layer.getRadius() / 1000);
            }
        });
        function saveGeofence(lat, lng, radius_km) {
            apiSend('POST', '/api/alert-subscriptions', { center_lat: lat, center_lng: lng, radius_km })
                .then(() => { showToast('Geofence creado exitosamente', 'success'); drawnItems.clearLayers(); })
                .catch(e => showToast('Error: ' + e.message, 'error'));
        }
    }

    window.map = map;
    window.markers = new Map();
    window.markerLayer = (typeof L.markerClusterGroup === 'function')
        ? L.markerClusterGroup({
            chunkedLoading: true,
            chunkInterval: 120,
            removeOutsideVisibleBounds: true,
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            maxClusterRadius: 42
        }).addTo(map)
        : map;

    // ---- Init ---------------------------------------------------------------
    const boot = canReport ? Promise.all([loadCategories(), loadUserPreferences()]) : Promise.all([loadCategories()]);
    boot.then(() => {
        buildLegend();
        buildCategorySelect();
        loadIncidents();
        startAutoRefresh();
    });

    if (canReport) {
        document.getElementById('gpsLocateBtn')?.addEventListener('click', () => {
            useBrowserGpsForReport();
        });
    }
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            loadIncidents();
            checkNotifications();
        }
    });

    if (canReport) {
        map.on('click', (e) => {
            if (!categories.length) { showToast('Categorias no cargadas', 'error'); return; }
            pendingLatLng = e.latlng;
            openModal(e.latlng.lat, e.latlng.lng);
        });
    }
    map.on('moveend zoomend', () => updateMapBrief());

    const mapActionState = { resolver: null };
    function closeMapActionModal(result = null) {
        const modal = document.getElementById('mapActionModal');
        if (modal) modal.style.display = 'none';
        if (mapActionState.resolver) {
            mapActionState.resolver(result);
            mapActionState.resolver = null;
        }
    }

    function openMapActionModal(config = {}) {
        const modal = document.getElementById('mapActionModal');
        const title = document.getElementById('mapActionTitle');
        const copy = document.getElementById('mapActionCopy');
        const fields = document.getElementById('mapActionFields');
        const confirmBtn = document.getElementById('mapActionConfirm');
        title.textContent = config.title || 'Confirmar accion';
        copy.textContent = config.message || '';
        confirmBtn.textContent = config.confirmLabel || 'Continuar';
        confirmBtn.style.background = config.danger ? 'linear-gradient(135deg,#ef4444,#dc2626)' : 'linear-gradient(135deg,#0ea5e4,#0284c7)';
        fields.innerHTML = '';
        const inputs = [];
        (config.fields || []).forEach(field => {
            const wrap = document.createElement('div');
            const label = document.createElement('label');
            label.textContent = field.label || '';
            const input = document.createElement(field.multiline ? 'textarea' : 'input');
            if (!field.multiline) input.type = field.type || 'text';
            if (field.multiline) input.rows = field.rows || 4;
            input.value = field.value || '';
            input.placeholder = field.placeholder || '';
            input.dataset.fieldId = field.id || '';
            wrap.appendChild(label);
            wrap.appendChild(input);
            fields.appendChild(wrap);
            inputs.push({ meta: field, input });
        });
        modal.style.display = 'flex';
        return new Promise(resolve => {
            mapActionState.resolver = resolve;
            confirmBtn.onclick = () => {
                const values = {};
                for (const item of inputs) {
                    const value = item.input.value.trim();
                    if (item.meta.required && !value) {
                        item.input.focus();
                        item.input.style.borderColor = '#ef4444';
                        return;
                    }
                    values[item.meta.id] = value;
                }
                closeMapActionModal(values);
            };
            document.getElementById('mapActionCancel').onclick = () => closeMapActionModal(null);
            document.getElementById('mapActionClose').onclick = () => closeMapActionModal(null);
        });
    }
    document.getElementById('mapActionModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'mapActionModal') closeMapActionModal(null);
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && document.getElementById('mapActionModal')?.style.display === 'flex') {
            closeMapActionModal(null);
        }
    });

    // ---- Toast notification system ------------------------------------------
    function showToast(message, type = 'info') {
        const colors = {
            success: { bg: '#d1fae5', border: '#10b981', text: '#065f46' },
            error:   { bg: '#fee2e2', border: '#ef4444', text: '#991b1b' },
            warning: { bg: '#fef3c7', border: '#f59e0b', text: '#92400e' },
            info:    { bg: '#e0f2fe', border: '#0ea5e4', text: '#0369a1' }
        };
        const c = colors[type] || colors.info;
        const toast = document.createElement('div');
        toast.style.cssText = `
            position:fixed;top:74px;right:20px;z-index:9999;
            background:${c.bg};color:${c.text};border:1px solid ${c.border};
            padding:12px 18px;border-radius:10px;font-size:13px;font-weight:600;
            max-width:340px;box-shadow:0 4px 16px rgba(0,0,0,0.1);
            animation:slideIn 0.3s ease;font-family:Inter,sans-serif;
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.3s'; setTimeout(() => toast.remove(), 300); }, 4000);
    }

    function buildGoogleMapsUrl(lat, lng, label = '') {
        const coords = `${Number(lat || 0)},${Number(lng || 0)}`;
        const query = label ? `${label} (${coords})` : coords;
        return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
    }

    function setGpsButtonState(loading, label) {
        const btn = document.getElementById('gpsLocateBtn');
        const text = document.getElementById('gpsLocateLabel');
        if (!btn || !text) return;
        btn.classList.toggle('is-loading', !!loading);
        text.textContent = label || 'Usar mi GPS';
    }

    function renderUserGpsMarker(lat, lng, accuracyMeters) {
        const latLng = [lat, lng];
        if (!userGpsMarker) {
            userGpsMarker = L.circleMarker(latLng, {
                radius: 8,
                color: '#0284c7',
                weight: 3,
                fillColor: '#38bdf8',
                fillOpacity: 0.92
            }).addTo(map);
        } else {
            userGpsMarker.setLatLng(latLng);
        }

        if (!userGpsAccuracy) {
            userGpsAccuracy = L.circle(latLng, {
                radius: Math.max(accuracyMeters || 0, 18),
                color: '#38bdf8',
                weight: 1.5,
                fillColor: '#38bdf8',
                fillOpacity: 0.12
            }).addTo(map);
        } else {
            userGpsAccuracy.setLatLng(latLng);
            userGpsAccuracy.setRadius(Math.max(accuracyMeters || 0, 18));
        }

        userGpsMarker.bindPopup(`<div style="font-size:12px;font-weight:700;">Tu ubicacion GPS</div><div style="font-size:11px;color:#475569;margin-top:4px;">Precision aproximada: ${Math.round(accuracyMeters || 0)} m</div>`);
    }

    async function useBrowserGpsForReport() {
        if (!navigator.geolocation) {
            showToast('Este navegador no soporta GPS/geolocalizacion.', 'error');
            return;
        }
        if (!window.isSecureContext) {
            showToast('Para usar tu ubicacion, abre PanamaAlert con HTTPS o desde localhost.', 'error');
            return;
        }
        if (navigator.permissions?.query) {
            try {
                const permission = await navigator.permissions.query({ name: 'geolocation' });
                if (permission.state === 'denied') {
                    showToast('Tu navegador tiene bloqueada la ubicacion. Habilitala en permisos del sitio e intenta otra vez.', 'error');
                    return;
                }
                if (permission.state === 'prompt') {
                    showToast('Tu navegador te pedira permiso para usar la ubicacion.', 'info');
                }
            } catch (error) {
                console.debug('Permissions API no disponible para geolocalizacion', error);
            }
        }
        setGpsButtonState(true, 'Tomando GPS...');
        navigator.geolocation.getCurrentPosition((position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            const accuracy = position.coords.accuracy || 0;
            renderUserGpsMarker(lat, lng, accuracy);
            map.flyTo([lat, lng], Math.max(map.getZoom(), 16), { duration: 0.8 });
            pendingLatLng = L.latLng(lat, lng);
            openModal(lat, lng);
            showToast('Ubicacion GPS tomada. Ya puedes reportar con esas coordenadas.', 'success');
            setGpsButtonState(false, 'Usar mi GPS');
        }, (error) => {
            let message = 'No pude obtener tu ubicacion.';
            if (error.code === error.PERMISSION_DENIED) message = 'Debes permitir acceso a la ubicacion para usar el GPS.';
            else if (error.code === error.POSITION_UNAVAILABLE) message = 'Tu ubicacion no esta disponible en este momento.';
            else if (error.code === error.TIMEOUT) message = 'El GPS tardo demasiado. Intenta otra vez.';
            showToast(message, 'error');
            setGpsButtonState(false, 'Usar mi GPS');
        }, {
            enableHighAccuracy: true,
            timeout: 12000,
            maximumAge: 30000
        });
    }

    // ---- HTTP helpers -------------------------------------------------------
    async function apiGet(path) {
        const r = await fetch(path, { credentials: 'same-origin' });
        if (r.status === 401) {
            if (canReport) {
                window.location.href = '/login';
                return null;
            }
            throw new Error(`GET ${path} -> 401`);
        }
        if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`);
        return r.json();
    }

    async function apiSend(method, path, body) {
        const r = await fetch(path, {
            method, credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.csrfToken || '' },
            body: body ? JSON.stringify(body) : undefined
        });
        if (r.status === 401) {
            if (canReport) {
                window.location.href = '/login';
                return null;
            }
            throw new Error(`${method} ${path} -> 401`);
        }
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || `${method} ${path} -> ${r.status}`);
        return data;
    }

    async function loadUserPreferences() {
        try {
            const prefs = await apiGet('/api/user/preferences');
            if (prefs) userPreferences = { ...userPreferences, ...prefs };
        } catch (e) {
            console.debug('No pude cargar preferencias de notificacion', e);
        }
    }

    async function uploadIncidentEvidenceFiles(incidentId, files) {
        const selected = Array.from(files || []).slice(0, 4);
        for (const file of selected) {
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch(`/api/incidents/${incidentId}/media`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRF-Token': window.csrfToken || '' },
                body: formData
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.error || 'No se pudo subir la evidencia');
        }
    }

    function maybeShowBrowserNotification(message) {
        if (!userPreferences.push_enabled || !userPreferences.browser_notifications) return;
        if (!('Notification' in window) || Notification.permission !== 'granted') return;
        try {
            new Notification('PanamaAlert', { body: message });
        } catch (e) {
            console.debug('Browser notification skipped', e);
        }
    }

    // ---- Categories ---------------------------------------------------------
    async function loadCategories() {
        try { categories = (await apiGet('/api/categories')) || []; }
        catch (e) { console.error(e); categories = []; }
    }

    function catById(id) { return categories.find(c => c.id === id) || {}; }

    function buildLegend() {
        const el = document.getElementById('legendList');
        if (!el) return;
        el.innerHTML = categories.map(c => {
            const icon = CAT_ICONS[c.name] || '&#128205;';
            const color = c.color || '#94a3b8';
            return `<span class="legend-chip" style="display:flex;align-items:center;gap:6px;font-size:11px;font-weight:600;padding:4px 8px;">
                <span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:${color}18;border:2px solid ${color};font-size:10px;">${icon}</span>
                ${esc(c.name)}
            </span>`;
        }).join('');
    }

    function buildCategorySelect() {
        const sel = document.getElementById('modalCategory');
        if (!sel) return;
        sel.innerHTML = categories.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
    }

    function buildIncidentsSignature(items) {
        return JSON.stringify((items || []).map(inc => [
            inc.incident_id || inc.id,
            inc.updated_at || inc.created_at || '',
            inc.status || '',
            inc.severity || 0,
            inc.lat || 0,
            inc.lng || 0,
            (inc.comments || []).length,
            inc.up_votes || 0,
            inc.down_votes || 0
        ]));
    }

    function normalizeIncidentText(value) {
        return String(value || '')
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-z0-9 ]+/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function extractNewsSource(inc) {
        const description = String(inc.description || '');
        const sourceMatch = description.match(/\[Fuente externa:\s*([^\]]+)\]/i);
        if (sourceMatch) return sourceMatch[1].trim();
        return String(inc.reporter_username || inc.username || '');
    }

    function extractZoneTarget(inc) {
        const description = String(inc.description || '');
        const match = description.match(/Zona objetivo:\s*([^\n]+)/i);
        return match ? match[1].trim() : '';
    }

    function isExternalNewsIncident(inc) {
        const reporter = String(inc.reporter_username || inc.username || '').toLowerCase();
        const description = String(inc.description || '').toLowerCase();
        return reporter === 'newsbot' || description.includes('[fuente externa:');
    }

    function getRenderableIncidents() {
        const seen = new Map();
        const sorted = [...allIncidents].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
        const deduped = [];
        for (const inc of sorted) {
            if (!isExternalNewsIncident(inc)) {
                deduped.push(inc);
                continue;
            }
            const zone = normalizeIncidentText(extractZoneTarget(inc) || `${Number(inc.lat || 0).toFixed(3)},${Number(inc.lng || 0).toFixed(3)}`);
            const key = [
                normalizeIncidentText(extractNewsSource(inc)),
                normalizeIncidentText(inc.title),
                normalizeIncidentText(inc.category_name || ''),
                zone,
            ].join('|');
            if (seen.has(key)) continue;
            seen.set(key, true);
            deduped.push(inc);
        }
        return deduped;
    }

    // ---- Incidents ----------------------------------------------------------
    async function loadIncidents() {
        try {
            const data = await apiGet('/api/incidents?limit=500');
            if (!data) return;
            const incoming = Array.isArray(data) ? data : (data.data || []);
            const nextSignature = buildIncidentsSignature(incoming);
            allIncidents = incoming;
            if (nextSignature === lastIncidentsSignature) {
                updateMapBrief();
                return;
            }
            lastIncidentsSignature = nextSignature;
            sortedSidebarCache = getRenderableIncidents();
            renderMarkers();
            renderSidebar();
            updateKPIs();
            updateMapBrief();
        } catch (e) {
            console.error('loadIncidents', e);
            const el = document.getElementById('alertList');
            if (el) {
                el.innerHTML = '<div class="alert-empty">No se pudieron cargar las alertas en este momento.</div>';
            }
            updateKPIs();
            updateMapBrief();
        }
    }

    async function loadIncidentDetail(id) {
        const key = String(id);
        const cached = incidentDetailCache.get(key);
        if (cached?.data) return cached.data;
        if (cached?.promise) return cached.promise;

        const promise = apiGet(`/api/incidents/${id}`).then(detail => {
            incidentDetailCache.set(key, { data: detail });
            const targetIndex = allIncidents.findIndex(inc => String(inc.incident_id || inc.id) === key);
            if (targetIndex >= 0) {
                allIncidents[targetIndex] = { ...allIncidents[targetIndex], ...detail, _detailLoaded: true };
                const marker = window.markers?.get(key);
                if (marker) marker._data = allIncidents[targetIndex];
            }
            return detail;
        }).catch(err => {
            incidentDetailCache.delete(key);
            throw err;
        });

        incidentDetailCache.set(key, { promise });
        return promise;
    }

    // ---- Category Icons & Severity ------------------------------------------
    const CAT_ICONS = {
        'Robo': '&#128176;', 'Accidente': '&#128663;',
        'Incendio': '&#128293;', 'Inundacion': '&#127754;', 'Inundación': '&#127754;',
        'Sospechoso': '&#128065;', 'Vandalismo': '&#129521;',
        'Emergencia medica': '&#128657;', 'Emergencia médica': '&#128657;',
        'Corte de luz': '&#9889;'
    };
    const CAT_EMOJI = {
        'Robo': '\uD83D\uDCB0', 'Accidente': '\uD83D\uDE97',
        'Incendio': '\uD83D\uDD25', 'Inundacion': '\uD83C\uDF0A', 'Inundación': '\uD83C\uDF0A',
        'Sospechoso': '\uD83D\uDC41', 'Vandalismo': '\uD83E\uDDF1',
        'Emergencia medica': '\uD83D\uDE91', 'Emergencia médica': '\uD83D\uDE91',
        'Corte de luz': '\u26A1'
    };
    const SEV_SIZES = { 1: 26, 2: 30, 3: 36, 4: 42, 5: 48 };
    const SEV_COLORS = { 1: '#10b981', 2: '#f59e0b', 3: '#f97316', 4: '#ef4444', 5: '#dc2626' };

    function createMarkerIcon(catName, colorHex, severity) {
        const sev = Math.min(5, Math.max(1, severity || 3));
        const size = SEV_SIZES[sev] || 36;
        const color = colorHex || SEV_COLORS[sev] || '#94a3b8';
        const icon = CAT_EMOJI[catName] || '\uD83D\uDCCD';
        const borderColor = SEV_COLORS[sev] || color;
        return L.divIcon({
            className: 'pa-marker',
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
            popupAnchor: [0, -size / 2],
            html: `<div style="
                width:${size}px;height:${size}px;
                display:flex;align-items:center;justify-content:center;
                background:${color}15;
                border:2.5px solid ${borderColor};
                border-radius:50%;
                font-size:${Math.round(size * 0.42)}px;
                box-shadow:0 2px 8px ${color}44;
                cursor:pointer;
                transition:transform 0.2s;
            " title="${esc(catName)} — SEV ${sev}">${icon}</div>`
        });
    }

    function renderMarkers() {
        const markers = window.markers;
        const markerLayer = window.markerLayer;
        const seen = new Set();
        const coordUsage = new Map();
        getRenderableIncidents().forEach(inc => {
            const id = String(inc.incident_id || inc.id);
            seen.add(id);
            const cat = catById(inc.category_id);
            const color = cat.color || inc.category_color || '#94a3b8';
            const catName = cat.name || inc.category_name || '';
            const icon = createMarkerIcon(catName, color, inc.severity);
            const lat = Number(inc.lat || 0);
            const lng = Number(inc.lng || 0);
            const coordKey = `${lat.toFixed(5)},${lng.toFixed(5)}`;
            const overlapIndex = coordUsage.get(coordKey) || 0;
            coordUsage.set(coordKey, overlapIndex + 1);
            const angle = overlapIndex * (Math.PI / 3);
            const offset = overlapIndex === 0 ? 0 : 0.00018 * Math.ceil(overlapIndex / 6);
            const markerLat = lat + (Math.sin(angle) * offset);
            const markerLng = lng + (Math.cos(angle) * offset);
            const popupSignature = JSON.stringify([
                inc.updated_at || inc.created_at || '',
                inc.status || '',
                (inc.comments || []).length,
                inc.up_votes || 0,
                inc.down_votes || 0
            ]);
            if (markers.has(id)) {
                const m = markers.get(id);
                m.setLatLng([markerLat, markerLng]);
                m.setIcon(icon);
                m._data = inc;
                m._cat = cat;
                m._popupSignature = popupSignature;
            } else {
                const m = L.marker([markerLat, markerLng], { icon }).bindPopup('<div style="font-size:12px;color:#475569;">Cargando detalles...</div>');
                m._data = inc;
                m._cat = cat;
                m._popupSignature = popupSignature;
                m.on('popupopen', async () => {
                    const content = buildPopup(m._data || {}, m._cat || {});
                    if (m.getPopup()) m.getPopup().setContent(content);
                    const incidentId = m._data?.incident_id || m._data?.id;
                    if (!incidentId || m._data?._detailLoaded) return;
                    try {
                        const detail = await loadIncidentDetail(incidentId);
                        m._data = { ...m._data, ...detail, _detailLoaded: true };
                        if (m.getPopup()?.isOpen()) {
                            m.getPopup().setContent(buildPopup(m._data || {}, m._cat || {}));
                        }
                    } catch (err) {
                        console.debug('No pude cargar detalle del incidente', err);
                    }
                });
                markers.set(id, m);
                if (markerLayer && markerLayer !== map && typeof markerLayer.addLayer === 'function') markerLayer.addLayer(m);
                else m.addTo(map);
            }
        });
        markers.forEach((m, id) => {
            if (!seen.has(id)) {
                if (markerLayer && markerLayer !== map && typeof markerLayer.removeLayer === 'function') markerLayer.removeLayer(m);
                else map.removeLayer(m);
                markers.delete(id);
            }
        });
    }

    function openMarkerPopup(marker, delay = 0) {
        if (!marker) return;
        const trigger = () => {
            const markerLayer = window.markerLayer;
            if (markerLayer && markerLayer !== map && typeof markerLayer.zoomToShowLayer === 'function') {
                markerLayer.zoomToShowLayer(marker, () => marker.openPopup());
            } else {
                marker.openPopup();
            }
        };
        if (delay > 0) setTimeout(trigger, delay);
        else trigger();
    }

    function buildPopup(inc, cat) {
        const id = inc.incident_id || inc.id;
        const color = cat.color || inc.category_color || '#94a3b8';
        const mine = canReport && String(inc.reporter_id || inc.user_id) === String(window.currentUserId);
        const sevClass = `sev-bg-${Math.min(5, Math.max(1, inc.severity || 3))}`;
        const comments = inc.comments || [];
        const reporterProfile = canReport ? (inc.reporter_profile || {}) : {};
        const explainability = inc.analysis_explainability || {};
        const evidence = inc.evidence || [];
        const sourceLabel = canReport
            ? (explainability.source_label || (inc.ai_analysis ? 'Respuesta por IA' : 'Respuesta por reglas'))
            : (isExternalNewsIncident(inc) ? extractNewsSource(inc) : 'Reporte ciudadano');
        const reporterLabel = canReport
            ? (inc.reporter_username || inc.username || 'Usuario')
            : (isExternalNewsIncident(inc) ? extractNewsSource(inc) : 'Reporte ciudadano');
        const detailLoadingHint = inc._detailLoaded ? '' : `
            <div style="margin-top:8px;font-size:10px;color:#64748b;padding:6px 8px;border-radius:8px;background:#f8fafc;">
                Cargando comentarios, evidencia y explicacion detallada...
            </div>`;
        const mapsUrl = buildGoogleMapsUrl(inc.lat, inc.lng, inc.location_label || inc.title || '');

        // AI Analysis badge — detailed and explainable
        let aiBadge = '';
        if (inc.ai_analysis) {
            const ai = inc.ai_analysis;
            const aiStyles = {
                approved: { bg: '#d1fae5', color: '#065f46', label: 'Validado por IA', icon: '&#10003;' },
                review:   { bg: '#fef3c7', color: '#92400e', label: 'Requiere revision', icon: '&#9888;' },
                rejected: { bg: '#fee2e2', color: '#991b1b', label: 'Rechazado por IA', icon: '&#10007;' }
            };
            const s = aiStyles[ai.decision] || aiStyles.review;
            const conf = ai.confidence ? Math.round(ai.confidence * 100) : 0;
            const alertLabels = { low: 'Bajo', medium: 'Medio', high: 'Alto', critical: 'Critico' };

            aiBadge = `<div style="margin-top:6px;padding:8px 10px;background:${s.bg};border:1px solid ${s.color}22;border-radius:8px;">
                <div style="display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;color:${s.color};margin-bottom:4px;">
                    <span style="font-size:13px;">${s.icon}</span> ${s.label}
                    <span style="margin-left:auto;font-size:10px;font-weight:600;opacity:0.8;">Confianza: ${conf}%</span>
                </div>`;

            if (ai.reason) {
                aiBadge += `<div style="font-size:10px;color:${s.color};opacity:0.85;line-height:1.4;margin-bottom:3px;">${esc(ai.reason)}</div>`;
            }

            // Show detected signals/flags
            if (ai.flags && ai.flags.length) {
                const flagLabels = {
                    'low_quality': 'Baja calidad de contenido',
                    'spam': 'Patron de spam detectado',
                    'velocity': 'Demasiados reportes recientes',
                    'velocity_burst': 'Rafaga de reportes',
                    'geographic_impossible': 'Ubicacion geografica imposible',
                    'out_of_bounds': 'Fuera del territorio',
                    'duplicate': 'Posible duplicado',
                    'temporal': 'Anomalia temporal',
                    'severity_mismatch': 'Severidad no coincide con descripcion'
                };
                aiBadge += `<div style="display:flex;flex-wrap:wrap;gap:3px;margin-top:3px;">`;
                ai.flags.forEach(f => {
                    const flagType = typeof f === 'string' ? f : (f.type || f);
                    const label = flagLabels[flagType] || flagType;
                    aiBadge += `<span style="font-size:9px;padding:2px 6px;border-radius:4px;background:${s.color}15;color:${s.color};font-weight:600;">${esc(label)}</span>`;
                });
                aiBadge += `</div>`;
            }

            if (ai.alert_level && ai.alert_level !== 'none') {
                aiBadge += `<div style="font-size:9px;margin-top:3px;font-weight:600;color:${s.color};opacity:0.7;">Nivel de alerta: ${alertLabels[ai.alert_level] || ai.alert_level}</div>`;
            }
            aiBadge += `</div>`;
        }

        const reporterBadgeColor = reporterProfile.credibility_band === 'high'
            ? '#16a34a'
            : reporterProfile.credibility_band === 'medium' ? '#d97706' : '#dc2626';
        const evidenceHtml = evidence.length
            ? `<div style="margin-top:10px;border-top:1px solid #e2e8f0;padding-top:8px;">
                <div style="font-size:10px;font-weight:700;color:#475569;margin-bottom:6px;">Evidencia adjunta</div>
                <div style="display:flex;gap:6px;flex-wrap:wrap;">
                    ${evidence.map(item => `<a href="${item.url}" target="_blank" rel="noopener" style="font-size:10px;padding:4px 8px;border-radius:999px;background:#eff6ff;color:#1d4ed8;text-decoration:none;">${item.kind === 'video' ? 'Video' : 'Imagen'}: ${esc(item.filename)}</a>`).join('')}
                </div>
            </div>`
            : '';

        return `<div class="popup-inner">
            <div class="popup-header">
                <span class="popup-cat-badge" style="background:${color}18;color:${color}">${esc(cat.name || inc.category_name || '')}</span>
                <span class="popup-sev ${sevClass}" style="padding:2px 6px;border-radius:5px;font-size:10px;">SEV ${inc.severity}</span>
            </div>
            <div class="popup-title">${esc(inc.title || '')}</div>
            <div class="popup-desc">${esc(inc.description || '')}</div>
            ${aiBadge}
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
                ${canReport ? `<span style="font-size:10px;font-weight:700;padding:3px 8px;border-radius:999px;background:${reporterBadgeColor}15;color:${reporterBadgeColor};">${esc(reporterProfile.credibility_label || 'Credibilidad sin historial')}</span>` : ''}
                <span style="font-size:10px;font-weight:600;padding:3px 8px;border-radius:999px;background:#f8fafc;color:#475569;">${esc(sourceLabel)}</span>
            </div>
            ${canReport && explainability.signals_used && explainability.signals_used.length ? `
                <div style="margin-top:8px;font-size:10px;color:#475569;line-height:1.5;">
                    <strong>Senales usadas:</strong> ${esc(explainability.signals_used.join(' • '))}
                </div>` : ''}
            <div class="popup-meta">
                ${esc(reporterLabel)} &middot;
                ${inc.status || 'pending'} &middot;
                ${fmtTime(inc.created_at)}
                ${(inc.up_votes || inc.down_votes) ? ` &middot; +${inc.up_votes||0} -${inc.down_votes||0}` : ''}
            </div>
            <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
                <a href="${mapsUrl}" target="_blank" rel="noopener"
                    style="font-size:10px;font-weight:700;padding:6px 10px;border-radius:999px;background:#eff6ff;color:#1d4ed8;text-decoration:none;">
                    Abrir en Google Maps
                </a>
                ${inc.location_label ? `<span style="font-size:10px;padding:6px 10px;border-radius:999px;background:#f8fafc;color:#475569;">${esc(inc.location_label)}</span>` : ''}
            </div>
            ${detailLoadingHint}
            ${evidenceHtml}
            ${canReport ? `<div class="popup-actions">
                <button class="vote-btn" data-action="vote" data-id="${id}" data-vote="1">&#128077; Confirmo</button>
                <button class="vote-btn" data-action="vote" data-id="${id}" data-vote="-1">&#128078;</button>
                ${mine ? `<button class="edit-btn" data-action="edit" data-id="${id}">Editar</button>` : ''}
                ${mine ? `<button class="del-btn" data-action="delete" data-id="${id}">Eliminar</button>` : ''}
            </div>` : ''}
            <div class="popup-comments">
                <div class="comments-list">
                    ${comments.length ? comments.map(c => `
                        <div class="comment">
                            <strong>${esc(canReport ? (c.username || 'Usuario') : 'Usuario anonimo')}</strong>
                            <span class="comment-time">${fmtTime(c.created_at)}</span>
                            <div class="comment-text">${esc(c.text || c.body || '')}</div>
                        </div>
                    `).join('') : '<div class="no-comments">Sin comentarios</div>'}
                </div>
                ${canReport ? `<div class="comment-form">
                    <input type="text" class="comment-input" placeholder="Agregar comentario..." data-incident-id="${id}">
                </div>` : ''}
            </div>
        </div>`;
    }

    // ---- Sidebar list -------------------------------------------------------
    const SEV_BADGE_COLORS = {
        1: { bg: '#d1fae5', color: '#065f46' },
        2: { bg: '#fef3c7', color: '#92400e' },
        3: { bg: '#fed7aa', color: '#c2410c' },
        4: { bg: '#fee2e2', color: '#991b1b' },
        5: { bg: '#fecdd3', color: '#881337' }
    };

    function timeAgo(iso) {
        if (!iso) return '';
        const diff = Math.max(0, Date.now() - new Date(iso).getTime());
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'ahora';
        if (mins < 60) return `hace ${mins}m`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `hace ${hrs}h`;
        const days = Math.floor(hrs / 24);
        if (days === 1) return 'ayer';
        if (days < 7) return `hace ${days}d`;
        return fmtTime(iso);
    }

    function renderSidebar() {
        const el = document.getElementById('alertList');
        if (!el) return;
        if (!allIncidents.length) {
            el.innerHTML = '<div class="alert-empty">No hay incidentes reportados.</div>';
            return;
        }
        el.innerHTML = sortedSidebarCache.slice(0, 12).map(inc => {
            const cat = catById(inc.category_id);
            const color = cat.color || inc.category_color || '#94a3b8';
            const sev = Math.min(5, Math.max(1, inc.severity || 3));
            const sevC = SEV_BADGE_COLORS[sev] || SEV_BADGE_COLORS[3];
            const icon = CAT_EMOJI[cat.name || inc.category_name] || '\uD83D\uDCCD';
            const reporterProfile = canReport ? (inc.reporter_profile || {}) : {};
            const locationMatch = (inc.description || '').match(/Zona objetivo:\s*([^\n]+)/i);
            const audienceMatch = (inc.description || '').match(/Audiencia:\s*([^\n]+)/i);
            const zoneLabel = locationMatch ? locationMatch[1].trim() : '';
            const audienceLabel = audienceMatch ? audienceMatch[1].trim() : '';
            const mapsUrl = buildGoogleMapsUrl(inc.lat, inc.lng, zoneLabel || inc.location_label || inc.title || '');

            // AI status indicator with label
            let aiDot = '';
            if (inc.ai_analysis) {
                const aiInfo = {
                    approved: { color: '#10b981', bg: '#d1fae5', label: 'Validado IA' },
                    review:   { color: '#f59e0b', bg: '#fef3c7', label: 'En revision' },
                    rejected: { color: '#ef4444', bg: '#fee2e2', label: 'Rechazado' }
                };
                const ai = aiInfo[inc.ai_analysis.decision] || aiInfo.review;
                const conf = inc.ai_analysis.confidence ? Math.round(inc.ai_analysis.confidence * 100) : 0;
                aiDot = `<span style="font-size:8px;font-weight:700;padding:1px 5px;border-radius:3px;background:${ai.bg};color:${ai.color};white-space:nowrap;" title="${ai.label} (${conf}% confianza)">${ai.label}</span>`;
            }

            return `<div class="alert-item" data-lat="${inc.lat}" data-lng="${inc.lng}" data-id="${inc.incident_id||inc.id}"
                style="border-left:3px solid ${color};">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;">
                    <span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:700;color:${color};">
                        ${icon} ${esc(cat.name || inc.category_name || '')}
                    </span>
                    <div style="display:flex;align-items:center;gap:4px;">
                        ${aiDot}
                        <span style="font-size:9px;font-weight:700;padding:2px 5px;border-radius:4px;background:${sevC.bg};color:${sevC.color};">S${sev}</span>
                    </div>
                </div>
                <div style="font-size:12px;font-weight:700;color:#0f172a;margin-bottom:2px;line-height:1.3;">${esc(inc.title || '')}</div>
                ${zoneLabel ? `<div style="font-size:10px;color:#334155;font-weight:600;margin-bottom:3px;">${esc(zoneLabel)}</div>` : ''}
                <div style="font-size:10px;color:#94a3b8;display:flex;justify-content:space-between;">
                    <span>${esc(canReport ? (inc.reporter_username||inc.username||'') : (isExternalNewsIncident(inc) ? extractNewsSource(inc) : 'Reporte ciudadano'))}</span>
                    <span>${timeAgo(inc.created_at)}</span>
                </div>
                ${canReport ? `<div style="font-size:10px;color:#475569;margin-top:4px;">
                    ${esc(reporterProfile.credibility_label || 'Sin historial de confianza')}
                </div>` : ''}
                ${audienceLabel ? `<div style="font-size:10px;color:#64748b;margin-top:2px;">${esc(audienceLabel)}</div>` : ''}
                <div style="margin-top:6px;">
                    <a href="${mapsUrl}" target="_blank" rel="noopener" onclick="event.stopPropagation()"
                        style="font-size:10px;font-weight:700;color:#1d4ed8;text-decoration:none;">Ver en Google Maps</a>
                </div>
            </div>`;
        }).join('');
    }

    // ---- KPIs ---------------------------------------------------------------
    function updateKPIs() {
        const el = (id) => document.getElementById(id);
        const renderable = getRenderableIncidents();
        if (el('kpiTotal'))    el('kpiTotal').textContent = renderable.length;
        if (el('kpiActive'))   el('kpiActive').textContent = renderable.filter(i => i.status === 'pending' || i.status === 'verified').length;
        if (el('kpiVerified')) el('kpiVerified').textContent = renderable.filter(i => i.status === 'verified').length;
    }

    function updateMapBrief() {
        const copyEl = document.getElementById('mapBriefCopy');
        const visibleEl = document.getElementById('mapBriefVisible');
        const totalEl = document.getElementById('mapBriefTotal');
        if (!copyEl || !visibleEl || !totalEl) return;

        const active = getRenderableIncidents().filter(inc => String(inc.status || '') !== 'dismissed');
        const bounds = map.getBounds();
        const visible = active.filter(inc => bounds.contains([Number(inc.lat || 0), Number(inc.lng || 0)]));
        const severeVisible = visible.filter(inc => Number(inc.severity || 0) >= 4).length;

        visibleEl.textContent = `${visible.length} en vista`;
        totalEl.textContent = `${active.length} activas`;

        if (!visible.length) {
            copyEl.textContent = 'No hay alertas en la vista actual. Puedes moverte o usar tu GPS para revisar tu zona.';
        } else if (severeVisible) {
            copyEl.textContent = `Hay ${severeVisible} alerta${severeVisible === 1 ? '' : 's'} severa${severeVisible === 1 ? '' : 's'} en la vista actual.`;
        } else {
            copyEl.textContent = `La vista actual muestra ${visible.length} alerta${visible.length === 1 ? '' : 's'} con actividad reciente.`;
        }
    }

    // ---- Modal: Create incident with Fake Detection -------------------------
    function updatePendingLocation(lat, lng, placeName = '') {
        pendingLatLng = L.latLng(lat, lng);
        const label = placeName ? `${placeName} · ` : '';
        document.getElementById('modalCoords').textContent = `${label}Lat: ${lat.toFixed(5)}, Lng: ${lng.toFixed(5)}`;
        map.flyTo([lat, lng], Math.max(map.getZoom(), 16), { duration: 0.6 });
    }

    function renderPlaceResults(results) {
        const holder = document.getElementById('modalPlaceResults');
        if (!holder) return;
        if (!results.length) {
            holder.style.display = 'none';
            holder.innerHTML = '';
            holder.dataset.results = '[]';
            return;
        }
        holder.style.display = 'grid';
        holder.style.gap = '8px';
        holder.dataset.results = JSON.stringify(results.slice(0, 4));
        holder.innerHTML = results.slice(0, 4).map((item, index) => `
            <button type="button" class="btn-secondary" data-place-index="${index}" style="text-align:left;padding:10px 12px;">
                <div style="font-size:12px;font-weight:700;color:#0f172a;">${esc(item.name || 'Ubicacion encontrada')}</div>
                <div style="font-size:11px;color:#64748b;margin-top:3px;">Lat ${Number(item.lat).toFixed(5)} · Lng ${Number(item.lng).toFixed(5)}</div>
            </button>
        `).join('');
    }

    async function searchPlaceForIncident() {
        const input = document.getElementById('modalPlaceQuery');
        if (!input) return;
        const query = input.value.trim();
        if (!query) {
            showToast('Escribe un lugar para buscarlo.', 'warning');
            return;
        }
        const btn = document.getElementById('modalPlaceSearch');
        btn.disabled = true;
        btn.textContent = 'Buscando...';
        try {
            const result = await apiSend('POST', '/api/geo/search', { query });
            const matches = result?.results || [];
            if (!matches.length) {
                renderPlaceResults([]);
                showToast('No encontre coincidencias para ese lugar.', 'warning');
                return;
            }
            renderPlaceResults(matches);
            const best = result.best_match || matches[0];
            updatePendingLocation(Number(best.lat), Number(best.lng), best.name || query);
            showToast('Ubicacion ajustada con la mejor coincidencia encontrada.', 'success');
        } catch (error) {
            showToast(`No pude ubicar ese lugar: ${error.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Buscar';
        }
    }

    function openModal(lat, lng) {
        document.getElementById('modalCoords').textContent = `Lat: ${lat.toFixed(5)}, Lng: ${lng.toFixed(5)}`;
        document.getElementById('modalTitle').value = '';
        document.getElementById('modalDesc').value = '';
        document.getElementById('modalEvidence').value = '';
        document.getElementById('modalPlaceQuery').value = '';
        renderPlaceResults([]);
        document.getElementById('fakeCheckResult').style.display = 'none';
        selectedSev = 3;
        document.querySelectorAll('#sevPicker .sev').forEach(b => b.classList.toggle('active', b.dataset.sev === '3'));
        document.getElementById('modalOverlay').classList.add('active');
    }

    document.getElementById('modalCancel')?.addEventListener('click', () => {
        document.getElementById('modalOverlay').classList.remove('active');
        pendingLatLng = null;
    });

    document.querySelectorAll('#sevPicker .sev').forEach(btn => {
        btn.onclick = () => {
            selectedSev = parseInt(btn.dataset.sev);
            document.querySelectorAll('#sevPicker .sev').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        };
    });

    document.getElementById('modalPlaceSearch')?.addEventListener('click', searchPlaceForIncident);
    document.getElementById('modalPlaceQuery')?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            searchPlaceForIncident();
        }
    });
    document.getElementById('modalPlaceResults')?.addEventListener('click', (event) => {
        const option = event.target.closest('[data-place-index]');
        if (!option) return;
        try {
            const results = JSON.parse(document.getElementById('modalPlaceResults').dataset.results || '[]');
            const selected = results[Number(option.dataset.placeIndex)];
            if (!selected) return;
            updatePendingLocation(Number(selected.lat), Number(selected.lng), selected.name || '');
            showToast('Pin ajustado al lugar seleccionado.', 'success');
        } catch (error) {
            console.debug('No pude aplicar la ubicacion elegida', error);
        }
    });

    // Pre-check with Fake Detection Agent before submitting
    async function runFakeCheck(title, desc, catId, lat, lng) {
        const fakeEl = document.getElementById('fakeCheckResult');
        try {
            const result = await apiSend('POST', '/api/ai/fake-check', {
                title, description: desc,
                category_id: catId,
                category: categories.find(c => c.id === catId)?.name || '',
                lat, lng, severity: selectedSev
            });

            if (result && result.risk_score !== undefined) {
                const riskScore = result.risk_score;
                let bgColor, textColor, icon, title;
                if (riskScore >= 75) {
                    bgColor = '#fee2e2'; textColor = '#991b1b'; icon = '&#10007;';
                    title = 'Reporte con alto riesgo de fraude';
                } else if (riskScore >= 40) {
                    bgColor = '#fef3c7'; textColor = '#92400e'; icon = '&#9888;';
                    title = 'Riesgo moderado detectado';
                } else {
                    bgColor = '#d1fae5'; textColor = '#065f46'; icon = '&#10003;';
                    title = 'Reporte parece legitimo';
                }

                let signalsHtml = '';
                if (result.signals && result.signals.length) {
                    const signalLabels = {
                        'low_quality': 'La descripcion es demasiado ambigua',
                        'spam': 'Patron de spam detectado',
                        'velocity': 'Demasiados reportes en poco tiempo',
                        'velocity_burst': 'Rafaga inusual de reportes',
                        'geographic_impossible': 'Ubicacion geograficamente imposible',
                        'out_of_bounds': 'Fuera del territorio de Panama',
                        'duplicate': 'La IA detecto posible duplicado',
                        'temporal': 'Anomalia temporal en el reporte',
                        'severity_mismatch': 'La severidad no coincide con la descripcion'
                    };
                    signalsHtml = '<div style="margin-top:6px;border-top:1px solid ' + textColor + '22;padding-top:6px;">';
                    result.signals.forEach(s => {
                        const label = signalLabels[s.type] || s.detail || s.type;
                        const sevIcon = { low: '~', medium: '!', high: '!!', critical: '!!!' };
                        signalsHtml += `<div style="font-size:11px;padding:2px 0;display:flex;align-items:center;gap:4px;">
                            <span style="font-weight:800;font-size:10px;">${sevIcon[s.severity] || '!'}</span>
                            <span>${esc(typeof label === 'string' ? label : s.detail || '')}</span>
                        </div>`;
                    });
                    signalsHtml += '</div>';
                }

                let recoHtml = '';
                if (result.recommendation) {
                    const recoLabels = {
                        approve: 'La IA recomienda aprobar este reporte',
                        review: 'El reporte sera enviado a revision manual',
                        reject: 'La IA recomienda rechazar este reporte'
                    };
                    recoHtml = `<div style="margin-top:4px;font-size:11px;font-weight:600;font-style:italic;">${recoLabels[result.recommendation] || ''}</div>`;
                }

                fakeEl.style.display = 'block';
                fakeEl.style.background = bgColor;
                fakeEl.style.color = textColor;
                fakeEl.style.borderRadius = '10px';
                fakeEl.style.padding = '12px';
                fakeEl.innerHTML = `
                    <div style="display:flex;align-items:center;gap:6px;font-weight:700;margin-bottom:4px;font-size:13px;">
                        <span style="font-size:16px;">${icon}</span> Agente Detector de Fraude
                        <span style="margin-left:auto;font-size:11px;font-weight:600;">Riesgo: ${riskScore.toFixed(0)}%</span>
                    </div>
                    <div style="font-size:12px;font-weight:600;">${esc(title)}</div>
                    ${recoHtml}
                    ${signalsHtml}`;
                return result;
            }
        } catch (e) {
            // Silently continue if fake check fails
        }
        return null;
    }

    document.getElementById('modalSubmit')?.addEventListener('click', async () => {
        if (!pendingLatLng) return;
        const title = document.getElementById('modalTitle').value.trim();
        const desc = document.getElementById('modalDesc').value.trim();
        const catId = parseInt(document.getElementById('modalCategory').value);
        const evidenceFiles = document.getElementById('modalEvidence').files;
        if (!title) { showToast('Titulo requerido', 'warning'); return; }
        if (!desc) { showToast('Descripcion requerida', 'warning'); return; }

        const submitBtn = document.getElementById('modalSubmit');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Analizando...';

        // Run fake detection
        const fakeResult = await runFakeCheck(title, desc, catId, pendingLatLng.lat, pendingLatLng.lng);

        // Block if clearly fake
        if (fakeResult && fakeResult.is_fake && fakeResult.risk_score >= 80) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Reportar';
            showToast('Reporte bloqueado por el agente detector de fraude', 'error');
            return;
        }

        submitBtn.textContent = 'Enviando...';

        try {
            const created = await apiSend('POST', '/api/incidents', {
                category_id: catId, title, description: desc,
                lat: pendingLatLng.lat, lng: pendingLatLng.lng, severity: selectedSev
            });
            if (evidenceFiles && evidenceFiles.length) {
                submitBtn.textContent = 'Subiendo evidencia...';
                await uploadIncidentEvidenceFiles(created.id, evidenceFiles);
            }
            document.getElementById('modalOverlay').classList.remove('active');
            pendingLatLng = null;
            showToast('Incidente reportado exitosamente', 'success');
            await loadIncidents();
        } catch (e) {
            showToast('Error: ' + e.message, 'error');
        }

        submitBtn.disabled = false;
        submitBtn.textContent = 'Reportar';
    });

    // ---- Actions with event delegation --------------------------------------
    document.addEventListener('click', async (e) => {
        if (!canReport) {
            const item = e.target.closest('.alert-item');
            if (item) {
                const lat = parseFloat(item.dataset.lat);
                const lng = parseFloat(item.dataset.lng);
                const id = parseInt(item.dataset.id);
                map.flyTo([lat, lng], 16, { duration: 0.8 });
                setTimeout(() => {
                    const m = window.markers.get(String(id));
                    if (m) openMarkerPopup(m);
                }, 900);
            }
            return;
        }
        const btn = e.target.closest('[data-action]');
        if (btn) {
            const action = btn.dataset.action;
            const id = parseInt(btn.dataset.id);
            try {
                if (action === 'vote') {
                    await apiSend('POST', `/api/incidents/${id}/vote`, { vote: parseInt(btn.dataset.vote) });
                    showToast('Voto registrado', 'success');
                    await loadIncidents();
                } else if (action === 'delete') {
                    const confirmed = await openMapActionModal({
                        title: 'Eliminar incidente',
                        message: 'Este reporte dejara de estar visible en el mapa y en los paneles relacionados.',
                        confirmLabel: 'Eliminar incidente',
                        danger: true
                    });
                    if (!confirmed) return;
                    await apiSend('DELETE', `/api/incidents/${id}`);
                    showToast('Incidente eliminado', 'info');
                    await loadIncidents();
                } else if (action === 'edit') {
                    const m = window.markers.get(String(id));
                    if (!m) return;
                    const edits = await openMapActionModal({
                        title: 'Editar incidente',
                        message: 'Actualiza el titulo y la descripcion para que el reporte sea mas claro y util.',
                        confirmLabel: 'Guardar cambios',
                        fields: [
                            { id: 'title', label: 'Titulo', value: m._data.title || '', required: true },
                            { id: 'description', label: 'Descripcion', value: m._data.description || '', required: true, multiline: true, rows: 4 }
                        ]
                    });
                    if (!edits) return;
                    await apiSend('PUT', `/api/incidents/${id}`, { title: edits.title, description: edits.description });
                    showToast('Incidente actualizado', 'success');
                    await loadIncidents();
                }
            } catch (e) { showToast(e.message, 'error'); }
            return;
        }

        // Sidebar item click
        const item = e.target.closest('.alert-item');
        if (item) {
            const lat = parseFloat(item.dataset.lat);
            const lng = parseFloat(item.dataset.lng);
            const id = parseInt(item.dataset.id);
            map.flyTo([lat, lng], 16, { duration: 0.8 });
            setTimeout(() => {
                const m = window.markers.get(String(id));
                if (m) openMarkerPopup(m);
            }, 900);
        }
    });

    // Comments - Enter to submit
    document.addEventListener('keydown', async (e) => {
        if (!canReport) return;
        if (e.key !== 'Enter') return;
        const inp = e.target.closest('.comment-input');
        if (!inp) return;
        const text = inp.value.trim();
        if (!text) return;
        const incId = parseInt(inp.dataset.incidentId);
        try {
            await apiSend('POST', `/api/incidents/${incId}/comments`, { text });
            inp.value = '';
            showToast('Comentario agregado', 'success');
            await loadIncidents();
            // Reopen popup so user sees the new comment
            setTimeout(() => {
                const m = window.markers.get(String(incId));
                if (m) openMarkerPopup(m);
            }, 300);
        } catch (e) { showToast('Error: ' + e.message, 'error'); }
    });

    window.flyTo = (lat, lng, id) => {
        map.flyTo([lat, lng], 16, { duration: 0.8 });
        const m = window.markers.get(String(id));
        if (m) openMarkerPopup(m, 900);
    };

    // ---- Auto-refresh -------------------------------------------------------
    let lastNotifCheck = Date.now();
    async function checkNotifications() {
        if (!canReport) return;
        try {
            const notifs = await apiGet('/api/notifications');
            if (!notifs || !Array.isArray(notifs) || !notifs.length) return;
            notifs.forEach(n => {
                showToast(n.message || 'Nueva alerta', n.type === 'geofence' ? 'warning' : 'info');
                maybeShowBrowserNotification(n.message || 'Nueva alerta en PanamaAlert');
                apiSend('POST', `/api/notifications/${n.id}/read`, {}).catch(() => {});
            });
        } catch (e) { /* silent */ }
    }

    function startAutoRefresh() {
        let remaining = REFRESH_MS / 1000;
        const el = document.getElementById('refreshCountdown');
        if (refreshTimer) clearInterval(refreshTimer);
        if (notificationTimer) clearInterval(notificationTimer);
        if (canReport) {
            notificationTimer = setInterval(() => {
                if (!document.hidden) checkNotifications();
            }, 5000);
        }
        refreshTimer = setInterval(() => {
            if (document.hidden) {
                if (el) el.textContent = 'pausa';
                return;
            }
            remaining--;
            if (remaining <= 0) { loadIncidents(); remaining = REFRESH_MS / 1000; }
            if (el) el.textContent = remaining;
        }, 1000);
    }

    // ---- Utils --------------------------------------------------------------
    function fmtTime(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        return isNaN(d) ? '' : d.toLocaleString('es-PA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }
    function esc(v) {
        return String(v || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
});
