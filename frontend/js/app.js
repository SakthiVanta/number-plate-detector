console.log(">>> [VERSION] app.js v2.2.2 Loaded - Active");
document.addEventListener('DOMContentLoaded', async () => {
    // Check Auth
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = 'auth.html';
        return;
    }
    // const api = new APIClient(); // REMOVED: Using global 'api' from api.js
    let trafficChart = null;

    // State
    let isPolling = false;
    let pollInterval = null;
    let currentDetectionsPage = 0;
    const detectionsLimit = 10;
    let totalDetections = 0;

    // Elements
    const views = {
        dashboard: document.getElementById('dashboard-view'),
        videos: document.getElementById('videos-view'),
        detections: document.getElementById('detections-view'),
        monitor: document.getElementById('monitor-view'),
        agents: document.getElementById('agents-view')
    };

    const navButtons = {
        dashboard: document.getElementById('nav-dashboard'),
        videos: document.getElementById('nav-videos'),
        detections: document.getElementById('nav-detections'),
        monitor: document.getElementById('nav-monitor'),
        agents: document.getElementById('nav-agents')
    };

    const contentArea = document.getElementById('content-area');
    const pageTitle = document.getElementById('page-title');
    const userEmail = document.getElementById('user-email');
    const logoutBtn = document.getElementById('logout-btn');

    // Stats
    const statVideos = document.getElementById('stat-videos');
    const statDetections = document.getElementById('stat-detections');

    // Upload
    const dropZone = document.getElementById('drop-zone');
    const videoInput = document.getElementById('video-input');
    const uploadProgress = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');

    // Lists
    const tasksList = document.getElementById('tasks-list');
    const videosGrid = document.getElementById('videos-grid');
    const detectionsList = document.getElementById('detections-list');

    // Initialization
    try {
        user = await api.get('/auth/me');
        userEmail.innerText = user.email;
        loadDashboardStats();
        fetchSystemHealth();
        startPolling();
    } catch (err) {
        console.error(err);
    }

    // Navigation Logic
    function switchView(viewName) {
        currentView = viewName;
        // Hide all views
        Object.values(views).forEach(v => v.classList.add('hidden'));
        // Show target view
        views[viewName].classList.remove('hidden');

        // Update Nav UI
        Object.keys(navButtons).forEach(key => {
            if (key === viewName) {
                navButtons[key].classList.add('bg-blue-600/10', 'text-white', 'border', 'border-blue-500/20');
            } else {
                navButtons[key].classList.remove('bg-blue-600/10', 'text-white', 'border', 'border-blue-500/20');
            }
        });

        // Update Header
        pageTitle.innerText = viewName === 'monitor' ? 'System Hardware Monitor' : viewName.charAt(0).toUpperCase() + viewName.slice(1);

        if (viewName === 'videos') loadVideos();
        if (viewName === 'detections') loadDetections();
        if (viewName === 'monitor') fetchSystemHealth();
        if (viewName === 'agents') loadAgentSettings();
    }

    navButtons.dashboard.onclick = () => switchView('dashboard');
    navButtons.videos.onclick = () => switchView('videos');
    navButtons.detections.onclick = () => switchView('detections');
    navButtons.monitor.onclick = () => switchView('monitor');
    navButtons.agents.onclick = () => switchView('agents');

    logoutBtn.onclick = () => {
        localStorage.removeItem('token');
        window.location.href = 'auth.html';
    };

    // Upload Logic
    dropZone.onclick = () => videoInput.click();
    videoInput.onchange = (e) => handleUpload(e.target.files[0]);

    // Drag and Drop (v2.3.4)
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-blue-500', 'bg-blue-500/10');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-blue-500', 'bg-blue-500/10');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-blue-500', 'bg-blue-500/10');
        if (e.dataTransfer.files.length > 0) {
            handleUpload(e.dataTransfer.files[0]);
        }
    });

    async function handleUpload(file) {
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        uploadProgress.classList.remove('hidden');
        progressBar.style.width = '30%';

        try {
            await api.upload('/videos/upload', formData);
            progressBar.style.width = '100%';
            setTimeout(() => {
                uploadProgress.classList.add('hidden');
                progressBar.style.width = '0%';
                loadDashboardStats();
            }, 1000);
        } catch (err) {
            alert(err.message);
            uploadProgress.classList.add('hidden');
        }
    }

    // Data Loading Functions
    async function loadDashboardStats() {
        try {
            const videos = await api.get('/videos/');
            statVideos.innerText = videos.length;

            // Load tasks (processing videos)
            const tasks = videos.filter(v => v.status === 'processing' || v.status === 'pending');
            tasksList.innerHTML = tasks.length > 0
                ? tasks.map(t => `<div class="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/5 hover:border-blue-500/30 transition-all">
                    <div class="flex flex-col">
                        <span class="text-sm font-medium"><i class="fas fa-spinner fa-spin mr-2 text-blue-400"></i> ${t.filename}</span>
                        <span class="text-[9px] uppercase text-slate-500 mt-1">${t.status}</span>
                    </div>
                    <button onclick="showLogs(${t.id}, '${t.filename}')" class="text-[10px] px-3 py-1.5 bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 rounded-lg border border-blue-500/20 transition-all font-bold">
                        <i class="fas fa-terminal mr-1"></i> VIEW LOGS
                    </button>
                </div>`).join('')
                : `<p class="text-slate-500 text-sm italic">No active background tasks</p>`;
        } catch (err) { console.error("Error loading videos stats:", err); }

        try {
            const detections = await api.get('/detections/');
            statDetections.innerText = detections.total || 0;
            const stats = await api.get('/stats');
            document.getElementById('stats-failed').innerText = stats.total_failed;

            // v2.3.2: Load Analytics for Latest Video
            const videos = await api.get('/videos/');
            const lastVid = videos[0];
            if (lastVid && lastVid.analytics_data) {
                renderTrafficChart(JSON.parse(lastVid.analytics_data));
            }
        } catch (err) { console.error("Error loading detections stats:", err); }
    }

    async function loadVideos() {
        try {
            const videos = await api.get('/videos/');
            videosGrid.innerHTML = videos.map(v => {
                const statusColor = v.status === 'completed' ? 'emerald' : v.status === 'failed' ? 'red' : 'blue';
                const dateStr = new Date(v.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
                const timeStr = new Date(v.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                return `
                <div class="relative group card p-0 rounded-3xl border border-white/5 bg-slate-800/20 overflow-hidden hover:border-blue-500/30 transition-all duration-500 hover:shadow-2xl hover:shadow-blue-500/10">
                    <!-- Delete Overlay (Premium Style) -->
                    <button onclick="deleteVideo(${v.id})" class="absolute top-4 right-4 w-8 h-8 rounded-full bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white border border-red-500/20 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all z-10">
                        <i class="fas fa-trash-alt text-xs"></i>
                    </button>

                    <div class="p-5 flex flex-col h-full">
                        <div class="flex items-center gap-4 mb-4">
                            <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                                <i class="fas fa-video text-white text-lg"></i>
                            </div>
                            <div class="flex-1 min-w-0">
                                <h4 class="text-sm font-black text-white truncate uppercase tracking-wider">${v.filename}</h4>
                                <p class="text-[10px] font-bold text-slate-500">${dateStr} • ${timeStr}</p>
                            </div>
                        </div>

                        <div class="grid grid-cols-2 gap-3 mb-4">
                            <div class="p-2.5 rounded-2xl bg-slate-900 border border-white/5">
                                <p class="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-1">Status</p>
                                <div class="flex items-center gap-1.5">
                                    <span class="w-1.5 h-1.5 rounded-full bg-${statusColor}-500 animate-pulse"></span>
                                    <span class="text-[9px] font-black text-${statusColor}-400 uppercase">${v.status}</span>
                                </div>
                            </div>
                            <div class="p-2.5 rounded-2xl bg-slate-900 border border-white/5">
                                <p class="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-1">ID Ref</p>
                                <p class="text-[10px] font-black text-white">#V-${v.id}</p>
                            </div>
                        </div>

                        <div class="mt-auto flex gap-2 pt-2">
                             <button onclick="showLogs(${v.id}, '${v.filename}')" class="flex-[1.5] py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all flex items-center justify-center gap-2">
                                <i class="fas fa-terminal opacity-50"></i> Logs
                            </button>
                            <button onclick="showAnalysisReport(${v.id})" class="flex-[2] py-2 bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 rounded-xl text-[10px] font-black uppercase tracking-widest border border-blue-500/20 transition-all flex items-center justify-center gap-2">
                                <i class="fas fa-file-medical-alt"></i> Report
                            </button>
                        </div>
                    </div>
                </div>
                `;
            }).join('');
        } catch (err) { console.error(err); }
    }

    async function loadDetections(page = 0) {
        currentDetectionsPage = page;
        const plateFilter = document.getElementById('filter-plate').value;
        const minConf = document.getElementById('filter-conf').value;
        const statusFilter = document.getElementById('filter-status').value;

        let params = new URLSearchParams();
        params.append('skip', page * detectionsLimit);
        params.append('limit', detectionsLimit);

        if (plateFilter) {
            if (plateFilter.length > 4 || plateFilter.includes(' ')) {
                params.append('vehicle_query', plateFilter);
            } else {
                params.append('plate', plateFilter);
            }
        }
        if (minConf > 0) params.append('min_confidence', minConf / 100);
        if (statusFilter) params.append('recheck_status', statusFilter);

        const url = `/detections/?${params.toString()}`;
        detectionsList.innerHTML = '<div class="text-center py-20 opacity-50"><i class="fas fa-spinner fa-spin text-3xl mb-4"></i><p>Scanning datasets...</p></div>';

        try {
            const data = await api.get(url);
            const detections = data.items;
            totalDetections = data.total;

            if (detections.length === 0) {
                detectionsList.innerHTML = '<div class="text-center py-20 opacity-20"><i class="fas fa-search text-6xl mb-4"></i><p>No matches found in forensic database</p></div>';
                updatePaginationUI();
                return;
            }

            detectionsList.innerHTML = detections.map(d => renderRichDetection(d)).join('');
            updatePaginationUI();
        } catch (err) { console.error(err); }
    }

    function updatePaginationUI() {
        const totalPages = Math.ceil(totalDetections / detectionsLimit);
        const container = document.getElementById('detections-pagination');
        if (!container) return;

        if (totalDetections <= detectionsLimit) {
            container.classList.add('hidden');
            return;
        }

        container.classList.remove('hidden');
        container.innerHTML = `
            <div class="flex items-center justify-between w-full">
                <p class="text-[10px] font-black text-slate-500 uppercase">Showing ${currentDetectionsPage * detectionsLimit + 1} - ${Math.min((currentDetectionsPage + 1) * detectionsLimit, totalDetections)} of ${totalDetections}</p>
                <div class="flex gap-2">
                    <button onclick="changePage(${currentDetectionsPage - 1})" ${currentDetectionsPage === 0 ? 'disabled' : ''} 
                        class="px-4 py-2 rounded-xl bg-slate-800 border border-white/5 text-[10px] font-black uppercase text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-all">
                        <i class="fas fa-chevron-left mr-2"></i> Prev
                    </button>
                    <button onclick="changePage(${currentDetectionsPage + 1})" ${currentDetectionsPage >= totalPages - 1 ? 'disabled' : ''} 
                        class="px-4 py-2 rounded-xl bg-slate-800 border border-white/5 text-[10px] font-black uppercase text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-all">
                        Next <i class="fas fa-chevron-right ml-2"></i>
                    </button>
                </div>
            </div>
        `;
    }

    window.changePage = (page) => {
        loadDetections(page);
        window.scrollTo({ top: detectionsList.offsetTop - 100, behavior: 'smooth' });
    };

    function renderRichDetection(d) {
        const statusConfig = {
            'success': { label: 'VERIFIED', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', icon: 'fa-robot' },
            'failed': { label: 'FB FAILED', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20', icon: 'fa-triangle-exclamation' },
            'none': { label: 'LOCAL ONLY', color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-500/20', icon: 'fa-camera' },
            'skipped': { label: 'SKIPPED', color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20', icon: 'fa-forward' }
        };
        const typeIcons = {
            'CAR': 'fa-car', 'MOTORCYCLE': 'fa-motorcycle', 'BIKE': 'fa-motorcycle',
            'SCOOTER': 'fa-moped', 'BICYCLE': 'fa-bicycle', 'CYCLE': 'fa-bicycle',
            'BUS': 'fa-bus', 'TRUCK': 'fa-truck', 'AUTO': 'fa-taxi'
        };

        const s = statusConfig[d.recheck_status] || statusConfig['none'];
        const plate = d.plate_number || 'UNKNOWN';
        const vidRef = d.video_id ? `#${d.video_id}` : 'N/A';
        const time = formatSeconds(d.timestamp);
        const date = new Date(d.created_at).toLocaleString();
        const tIcon = typeIcons[d.vehicle_type] || 'fa-car-side';

        // Safety Badges
        let safetyHtml = '';
        if (d.vehicle_type.includes('BIKE') || d.vehicle_type.includes('MOTORCYCLE') || d.vehicle_type.includes('SCOOTER')) {
            const hColor = d.helmet_status === 'HELMET' ? 'text-emerald-400 bg-emerald-500/10' : 'text-red-400 bg-red-500/10 animate-pulse';
            const hIcon = d.helmet_status === 'HELMET' ? 'fa-user-shield' : 'fa-user-minus';
            safetyHtml = `
                <div class="flex items-center gap-2 mt-2">
                    <span class="${hColor} px-2 py-0.5 rounded text-[8px] font-black border border-white/5 flex items-center gap-1">
                        <i class="fas ${hIcon}"></i> ${d.helmet_status}
                    </span>
                    <span class="bg-slate-500/10 text-slate-300 px-2 py-0.5 rounded text-[8px] font-black border border-white/5 flex items-center gap-1">
                        <i class="fas fa-users"></i> ${d.passenger_count} PASS
                    </span>
                </div>
            `;
        }

        return `
            <div class="card rounded-2xl border border-white/5 bg-slate-800/20 overflow-hidden transition-all group hover:border-blue-500/30" id="det-card-${d.id}">
                <div class="p-4 flex items-center justify-between cursor-pointer" onclick="toggleDetectionExpansion(${d.id})">
                    <div class="flex items-center gap-6">
                        <div class="w-12 h-12 rounded-xl bg-slate-900 border border-white/5 flex items-center justify-center text-slate-500 group-hover:text-blue-400 transition-colors">
                            <i class="fas ${tIcon} text-xl"></i>
                        </div>
                        <div class="flex flex-col">
                            <span class="text-[10px] font-black text-slate-500 uppercase tracking-tighter mb-1">Vehicle Match</span>
                            <span class="text-lg font-mono font-bold text-white tracking-widest">${plate}</span>
                            ${safetyHtml}
                        </div>
                        <div class="h-8 w-[1px] bg-white/5"></div>
                        <div class="flex flex-col">
                            <span class="text-[10px] font-black text-slate-500 uppercase tracking-tighter mb-1">AI Trust</span>
                            <div class="flex items-center gap-2">
                                <div class="w-16 h-1 bg-slate-700 rounded-full overflow-hidden">
                                     <div class="h-full bg-blue-500" style="width: ${(d.confidence || 0) * 100}%"></div>
                                </div>
                                <span class="text-[10px] font-bold text-slate-400 font-mono">${((d.confidence || 0) * 100).toFixed(0)}%</span>
                            </div>
                        </div>
                        <div class="h-8 w-[1px] bg-white/5"></div>
                        <div class="flex flex-col">
                            <span class="text-[10px] font-black text-slate-500 uppercase tracking-tighter mb-1">Audit Mode</span>
                            <span class="${s.bg} ${s.color} ${s.border} px-2 py-0.5 rounded text-[9px] font-black border flex items-center gap-1">
                                <i class="fas ${s.icon}"></i> ${s.label}
                            </span>
                        </div>
                    </div>
                    <div class="flex items-center gap-4">
                        <div class="text-right hidden md:block">
                            <p class="text-[9px] font-bold text-slate-500 uppercase">${vidRef} @ ${time}</p>
                            <p class="text-[10px] text-slate-600">${date}</p>
                        </div>
                        <i class="fas fa-chevron-down text-slate-600 transition-transform group-hover:text-blue-400" id="det-chevron-${d.id}"></i>
                    </div>
                </div>

                <!-- Expanded Panels -->
                <div id="det-expand-${d.id}" class="hidden p-6 bg-slate-900/50 border-t border-white/5 space-y-6">
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                        <!-- Forensic Collage -->
                        <div class="space-y-4">
                            <div class="flex items-center justify-between">
                                <h5 class="text-[10px] font-black text-blue-400 uppercase tracking-widest">Forensic Collage (v2.3)</h5>
                                <button class="text-[9px] font-bold text-slate-500 hover:text-white transition-all uppercase"><i class="fas fa-expand mr-1"></i> Fullscreen</button>
                            </div>
                            <div class="aspect-video bg-black rounded-xl border border-white/5 overflow-hidden flex items-center justify-center relative">
                                ${d.batch ? `<img src="/api/raw_files/${d.batch.collage_path}" class="w-full h-full object-cover">` : `<div class="text-center opacity-20"><i class="fas fa-camera text-4xl mb-2"></i><p class="text-[10px]">No collage stored for this batch</p></div>`}
                                <div class="absolute bottom-4 left-4 text-[9px] font-mono bg-black/60 px-2 py-1 rounded text-white/50 border border-white/10">TRACK_ID: ${d.track_id}</div>
                            </div>
                        </div>

                        <!-- Analysis Workspace -->
                        <div class="flex flex-col h-full">
                            <h5 class="text-[10px] font-black text-emerald-400 uppercase tracking-widest mb-4">AI Audit & Verification</h5>
                            <div class="flex-1 bg-slate-900 rounded-xl border border-white/5 p-4 overflow-hidden flex flex-col">
                                <div class="flex items-center gap-2 mb-4">
                                    <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                                    <span class="text-[10px] font-bold text-slate-400 uppercase">Gemini 1.5 Flash Analysis</span>
                                </div>
                                <div class="flex-1 overflow-y-auto pr-2 space-y-4">
                                    ${d.vehicle_info ? `<p class="text-xs text-white leading-relaxed font-medium bg-white/5 p-3 rounded-lg border border-white/5">${d.vehicle_info}</p>` : `<p class="text-xs text-slate-600 italic">No deep-analysis metadata available.</p>`}
                                </div>
                                <div class="mt-4 pt-4 border-t border-white/5 flex gap-2">
                                    <button onclick="editDetection(${d.id}, '${d.plate_number}')" class="flex-1 py-2 text-[10px] font-black uppercase bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 rounded-lg border border-blue-500/20 transition-all">Manual Correct</button>
                                    <button onclick="deleteDetection(${d.id})" class="flex-1 py-2 text-[10px] font-black uppercase bg-red-600/10 hover:bg-red-600/20 text-red-400 rounded-lg border border-red-500/20 transition-all">Invalidate</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    let reportVehicleMixChart = null;
    let reportDensityChart = null;

    window.showAnalysisReport = async (videoId) => {
        try {
            const v = await api.get(`/videos/${videoId}`);
            if (!v || !v.analytics_data) {
                if (v.status === 'completed') alert("Analysis data is temporarily unavailable. Please refresh.");
                else if (v.status === 'failed') alert("Analysis failed for this video. Check logs.");
                else alert("Deep analysis is still in progress for this video.");
                return;
            }

            const data = JSON.parse(v.analytics_data);
            const counts = data.counts || {};
            const meta = data.metadata || {};
            const cap = data.capture_metrics || {};

            // 1. Header & Registry metadata
            document.getElementById('analysis-video-name').innerText = v.filename.toUpperCase();
            document.getElementById('analysis-processed-at').innerText = `AUDITED AT: ${data.processed_at || 'STABLE'}`;
            document.getElementById('stat-resolution').innerText = meta.resolution || 'N/A';
            document.getElementById('stat-total-frames').innerText = meta.total_frames || 0;

            // 2. Executive Summary
            document.getElementById('stat-total-vehicles').innerText = data.total_vehicles_seen || 0;
            document.getElementById('stat-total-snaps').innerText = cap.total_captured_images || 0;
            document.getElementById('stat-batch-count').innerText = `${cap.total_batches || 0} GRID COLLAGES`;
            document.getElementById('stat-avg-fps').innerText = (meta.avg_fps || 0).toFixed(1);
            document.getElementById('stat-total-duration').innerText = `${(meta.processing_duration_sec || 0).toFixed(1)}s TOTAL DURATION`;

            const successRate = cap.total_batches > 0 ? (cap.successful_batches / cap.total_batches * 100).toFixed(0) : 0;
            document.getElementById('stat-batch-success').innerText = `${successRate}%`;

            // 3. Safety Compliance
            const helmetCount = counts.HELMET || 0;
            const noHelmetCount = counts.NO_HELMET || 0;
            const overloadCount = counts.OVERLOADED_BIKES || 0;
            const totalBikerAudit = helmetCount + noHelmetCount;
            const helmetRate = totalBikerAudit > 0 ? (helmetCount / totalBikerAudit * 100) : 100;

            document.getElementById('stat-helmet-count').innerText = helmetCount;
            document.getElementById('stat-no-helmet-count').innerText = noHelmetCount;
            document.getElementById('stat-overload-count').innerText = overloadCount;
            document.getElementById('stat-helmet-bar').style.width = `${helmetRate}%`;
            document.getElementById('stat-no-helmet-bar').style.width = `${totalBikerAudit > 0 ? (noHelmetCount / totalBikerAudit * 100) : 0}%`;

            // 4. Vehicle Mix Grid
            const grid = document.getElementById('analysis-stats-grid');
            const types = ['CAR', 'MOTORCYCLE', 'SCOOTER', 'BICYCLE', 'BUS', 'TRUCK', 'AUTO'];
            grid.innerHTML = types.map(t => `
                <div class="p-3 rounded-xl bg-slate-800/40 border border-white/5 flex items-center justify-between">
                    <span class="text-[9px] font-black text-slate-500 uppercase">${t}</span>
                    <span class="text-xs font-bold text-white">${counts[t] || 0}</span>
                </div>
            `).join('');

            // 5. Initialize Charts
            if (reportVehicleMixChart) reportVehicleMixChart.destroy();
            if (reportDensityChart) reportDensityChart.destroy();

            const mixCtx = document.getElementById('reportVehicleMixChart').getContext('2d');
            reportVehicleMixChart = new Chart(mixCtx, {
                type: 'doughnut',
                data: {
                    labels: types,
                    datasets: [{
                        data: types.map(t => counts[t] || 0),
                        backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#6366f1', '#ec4899'],
                        borderWidth: 0,
                        hoverOffset: 10
                    }]
                },
                options: {
                    cutout: '75%',
                    plugins: { legend: { display: false } },
                    maintainAspectRatio: false
                }
            });

            const denseCtx = document.getElementById('reportDensityChart').getContext('2d');
            const labels = Object.keys(data.frame_series || {}).map(f => `F${f}`);
            const values = Object.values(data.frame_series || {});

            reportDensityChart = new Chart(denseCtx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Vehicle Density',
                        data: values,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0
                    }]
                },
                options: {
                    plugins: { legend: { display: false } },
                    maintainAspectRatio: false,
                    scales: {
                        x: { display: false },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: { color: '#64748b', font: { size: 10 } }
                        }
                    }
                }
            });

            // 6. Fetch Forensic Logs
            const logsContainer = document.getElementById('analysis-logs-container');
            logsContainer.innerHTML = '<div class="text-slate-600 animate-pulse">Scanning forensic registry...</div>';

            try {
                const logs = await api.get(`/v2/process/video/${videoId}/logs`);
                document.getElementById('stat-total-events').innerText = `${logs.length} EVENTS CAPTURED`;

                if (logs.length === 0) {
                    logsContainer.innerHTML = '<div class="text-slate-600 italic uppercase tracking-widest text-[10px]">No agent telemetry found in audit chain</div>';
                } else {
                    logsContainer.innerHTML = logs.map(log => {
                        const timeStr = new Date(log.created_at).toLocaleTimeString([], { hour12: false });
                        let colorClass = "text-blue-400";
                        if (log.event_type === "GEMINI") colorClass = "text-purple-400";
                        if (log.event_type === "CAPTURER") colorClass = "text-emerald-400";
                        if (log.is_error) colorClass = "text-red-400 font-bold";

                        return `
                            <div class="flex gap-4 group hover:bg-white/5 p-1 rounded transition-all">
                                <span class="text-slate-600 w-16 shrink-0">${timeStr}</span>
                                <span class="font-black w-20 shrink-0 uppercase ${colorClass}">[${log.event_type}]</span>
                                <span class="text-slate-300 flex-1">${log.message}</span>
                            </div>
                        `;
                    }).join('');
                }
            } catch (err) { logsContainer.innerHTML = `<div class="text-red-500">Log Retrieval Failure: ${err.message}</div>`; }

            document.getElementById('analysis-modal').classList.remove('hidden');
        } catch (err) { console.error(err); }
    };

    window.closeAnalysisModal = () => {
        document.getElementById('analysis-modal').classList.add('hidden');
    };

    window.toggleDetectionExpansion = (id) => {
        const panel = document.getElementById(`det-expand-${id}`);
        const chevron = document.getElementById(`det-chevron-${id}`);
        const card = document.getElementById(`det-card-${id}`);

        if (panel.classList.contains('hidden')) {
            panel.classList.remove('hidden');
            chevron.classList.add('rotate-180');
            card.classList.add('border-blue-500/50', 'bg-slate-800/40');
        } else {
            panel.classList.add('hidden');
            chevron.classList.remove('rotate-180');
            card.classList.remove('border-blue-500/50', 'bg-slate-800/40');
        }
    };

    document.getElementById('apply-filter').onclick = () => loadDetections();
    document.getElementById('filter-conf').oninput = (e) => {
        document.getElementById('filter-conf-val').innerText = `${e.target.value}%`;
    };

    // Polling Utility
    function startPolling() {
        setInterval(() => {
            if (currentView === 'dashboard') {
                loadDashboardStats();
                fetchSystemHealth();
            }
            if (currentView === 'agents') {
                updateAgentStatusRealtime();
            }
        }, 8000);
    }

    async function updateAgentStatusRealtime() {
        // Find last processed video to show status for
        const videos = await api.get('/videos/');
        const lastVid = videos.find(v => v.status === 'processing') || videos[0];
        if (!lastVid) return;

        try {
            const status = await api.get(`/v2/process/video/${lastVid.id}/agent-status`);
            const grid = document.getElementById('agents-grid');
            if (!status.agents) return;

            grid.innerHTML = Object.entries(status.agents).map(([agentKey, data]) => {
                const isActive = data.status !== 'Idle' && data.status !== 'Standby';
                const pulseClass = isActive ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600';

                return `
                <div class="card p-6 rounded-2xl flex flex-col gap-4 border-l-4 ${isActive ? 'border-blue-500' : 'border-slate-700'}">
                    <div class="flex items-center justify-between">
                        <h4 class="font-bold text-white text-[10px] uppercase">${agentKey}</h4>
                        <span class="text-[9px] ${isActive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-500/20 text-slate-500'} px-2 py-0.5 rounded font-bold uppercase">${data.status}</span>
                    </div>
                    <div class="space-y-1">
                        <p class="text-[12px] text-white font-mono">${data.telemetry || '-'}</p>
                        <p class="text-[9px] text-slate-500 font-bold uppercase">Work Items: ${data.count || 0}</p>
                    </div>
                    <div class="flex items-center justify-between mt-auto">
                        <div class="flex items-center gap-2">
                            <div class="w-1.5 h-1.5 rounded-full ${pulseClass}"></div>
                            <span class="text-[10px] text-slate-500 font-bold uppercase">${isActive ? 'Running' : 'Standby'}</span>
                        </div>
                        <button onclick="showLogs(${lastVid.id}, '${lastVid.filename}', '${agentKey}')" class="text-[10px] font-bold text-blue-400 hover:text-blue-300 transition-all uppercase flex items-center gap-1">
                            <i class="fas fa-terminal"></i> Agent Logs
                        </button>
                    </div>
                </div>`;
            }).join('');

            // Also update analytics if present
            if (status.analytics) renderTrafficChart(status.analytics);
        } catch (e) { console.error("Agent status update error:", e); }
    }

    async function loadAgentSettings() {
        try {
            const settings = await api.get('/v2/agent-settings');
            document.getElementById('setting-batch-size').value = settings.collage_size;
            document.getElementById('batch-size-val').innerText = `${settings.collage_size} CROPS / CALL`;
            document.getElementById('setting-persistence').value = settings.track_persistence;
            window.currentSensitivity = settings.sensitivity;
            updateSensitivityUI(settings.sensitivity);
        } catch (err) { console.error(err); }
    }

    function updateSensitivityUI(sens) {
        ['LOW', 'BALANCED', 'HIGH'].forEach(s => {
            const btn = document.getElementById(`sens-${s}`);
            if (s === sens) {
                btn.className = "flex-1 py-2 text-xs font-bold rounded-lg bg-blue-600 text-white shadow-lg shadow-blue-500/20";
            } else {
                btn.className = "flex-1 py-2 text-xs font-bold rounded-lg hover:bg-white/5 transition-all text-slate-500";
            }
        });
    }

    window.setSensitivity = (sens) => {
        window.currentSensitivity = sens;
        updateSensitivityUI(sens);
    };

    window.saveAgentSettings = async () => {
        const batchSize = document.getElementById('setting-batch-size').value;
        const persistence = document.getElementById('setting-persistence').value;

        try {
            await api.post('/v2/agent-settings', {
                collage_size: batchSize,
                sensitivity: window.currentSensitivity,
                track_persistence: persistence
            });
            alert("Agents synchronized and deployed!");
        } catch (err) { alert("Deployment failed: " + err.message); }
    };

    document.getElementById('setting-batch-size').oninput = (e) => {
        document.getElementById('batch-size-val').innerText = `${e.target.value} CROPS / CALL`;
    };

    async function fetchSystemHealth() {
        try {
            const health = await api.get('/health');
            const diskEl = document.getElementById('health-disk');
            const gpuEl = document.getElementById('health-gpu');
            const roiEl = document.getElementById('health-roi');

            if (diskEl) diskEl.innerText = health.disk_name;
            if (gpuEl) {
                gpuEl.innerText = health.gpu_name;
                gpuEl.className = health.gpu_name.includes('NOT DETECTED') ? 'text-red-400' : 'text-emerald-400';
            }
            if (roiEl) {
                roiEl.innerText = health.roi_status;
                roiEl.className = health.roi_status === 'ACTIVE' ? 'text-blue-400' : 'text-yellow-400';
            }

            // If we are on monitor view, update those too
            if (currentView === 'monitor') updateMonitorUI(health);
        } catch (err) {
            console.error("Health check failed:", err);
        }
    }

    function renderTrafficChart(data) {
        const ctx = document.getElementById('trafficChart').getContext('2d');
        const labels = Object.keys(data.frame_series).map(f => `F:${f}`);
        const values = Object.values(data.frame_series);

        document.getElementById('peak-density').innerText = data.peak_vehicle_density || 0;
        document.getElementById('unique-vehicles').innerText = data.total_vehicles_seen || 0;
        document.getElementById('analytics-updated').innerText = `Last Refreshed: ${data.processed_at}`;

        if (trafficChart) trafficChart.destroy();

        trafficChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Vehicles per Frame',
                    data: values,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8', font: { size: 10 } }
                    }
                }
            }
        });
    }

    async function fetchDetailedSystemInfo() {
        await fetchSystemHealth();
    }

    function updateMonitorUI(h) {
        document.getElementById('mon-cpu-name').innerText = h.cpu_name;
        document.getElementById('mon-cpu-usage').innerText = `${h.cpu_usage}%`;
        document.getElementById('mon-cpu-bar').style.width = `${h.cpu_usage}%`;

        document.getElementById('mon-gpu-name').innerText = h.gpu_name;
        const caps = document.getElementById('mon-gpu-caps');
        caps.innerText = h.gpu_caps;
        caps.className = h.gpu_caps === 'AI-ACCELERATED' ? 'px-3 py-1 bg-emerald-500/10 text-emerald-400 text-[10px] font-black rounded-full border border-emerald-500/20' : 'px-3 py-1 bg-yellow-500/10 text-yellow-400 text-[10px] font-black rounded-full border border-yellow-500/20';

        document.getElementById('mon-os').innerText = h.os;
        document.getElementById('mon-mem-total').innerText = h.memory_total;
        document.getElementById('mon-mem-bar').style.width = `${h.mem_usage}%`;

        document.getElementById('mon-disk-name').innerText = h.disk_name;
        document.getElementById('mon-disk-bar').style.width = `${h.disk_usage}%`;

        // Status Badges
        const redisStat = document.getElementById('stat-redis');
        redisStat.innerText = h.redis_status;
        redisStat.className = `text-[9px] font-black px-2 py-0.5 rounded ${h.redis_status === 'RUNNING' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`;

        const geminiStat = document.getElementById('stat-gemini');
        geminiStat.innerText = h.gemini_status;
        geminiStat.className = `text-[9px] font-black px-2 py-0.5 rounded ${h.gemini_status === 'CONFIGURED' ? 'bg-blue-500/10 text-blue-400' : 'bg-yellow-500/10 text-yellow-400'}`;

        const roiStat = document.getElementById('stat-roi');
        roiStat.innerText = h.roi_status;
        roiStat.className = `text-[9px] font-black px-2 py-0.5 rounded ${h.roi_status === 'ACTIVE' ? 'bg-blue-500/10 text-blue-400' : 'bg-red-500/10 text-red-400'}`;
    }

    function formatSeconds(seconds) {
        if (!seconds) return "00:00:00";
        const date = new Date(null);
        date.setSeconds(seconds);
        return date.toISOString().substr(11, 8);
    }
    window.formatSeconds = formatSeconds;
});

// Global functions for inline EventHandlers
window.deleteVideo = async (id) => {
    if (!confirm('Are you sure you want to delete this video and all its detections?')) return;
    try {
        await api.delete(`/videos/${id}`);
        loadVideos();
        showNotification("Video deleted successfully", "success");
    } catch (err) {
        console.error(err);
        showNotification("Failed to delete video", "error");
    }
};

window.deleteDetection = async (id) => {
    if (!confirm('Permanently remove this detection result?')) return;
    try {
        await api.delete(`/detections/${id}`);
        location.reload();
    } catch (err) { alert(err.message); }
};

function showNotification(msg, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-8 right-8 px-6 py-3 rounded-2xl border backdrop-blur-xl animate-in fade-in slide-in-from-right-10 duration-300 z-[200] flex items-center gap-3 shadow-2xl`;
    if (type === 'success') {
        toast.classList.add('bg-emerald-500/10', 'border-emerald-500/20', 'text-emerald-400');
        toast.innerHTML = `<i class="fas fa-check-circle"></i> <span class="text-xs font-black uppercase tracking-widest">${msg}</span>`;
    } else {
        toast.classList.add('bg-red-500/10', 'border-red-500/20', 'text-red-400');
        toast.innerHTML = `<i class="fas fa-exclamation-triangle"></i> <span class="text-xs font-black uppercase tracking-widest">${msg}</span>`;
    }
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('animate-out', 'fade-out', 'slide-out-to-right-10');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

window.editDetection = async (id, currentPlate) => {
    const newPlate = prompt('Enter corrected plate number:', currentPlate);
    if (!newPlate || newPlate === currentPlate) return;
    try {
        await api.patch(`/detections/${id}?plate_number=${newPlate}`);
        location.reload();
    } catch (err) { alert(err.message); }
};

window.playVideo = async (id, filename) => {
    console.log(`>>> [PLAY] Initializing player for ID: ${id}`);
    const video = await api.get(`/videos/${id}`);
    if (video.status !== 'completed' && video.status !== 'processing') {
        alert('Video not ready.');
        return;
    }

    const modal = document.getElementById('video-modal');
    const player = document.getElementById('player');
    const title = document.getElementById('modal-video-title');
    const jumpList = document.getElementById('jump-list');

    // Load original video stream with token in query for browser compatibility
    const token = localStorage.getItem('token');
    if (!token) {
        alert("Authentication error. Please re-login.");
        return;
    }

    // Explicitly construct URL with token and cache buster using the NEW BYPASS route
    const streamUrl = `${API_BASE}/raw_vids/${id}?token=${token}&_t=${Date.now()}`;
    console.log(`>>> [STREAM] Requesting via BYPASS route: ${streamUrl}`);

    player.onerror = () => {
        console.error(">>> [PLAYER ERROR] Detailed Error:", player.error);
        alert(`Streaming failed. Error Code: ${player.error ? player.error.code : 'unknown'}`);
    };

    player.src = streamUrl;
    title.innerText = filename;

    // Clear and Load Detections for Jump List
    jumpList.innerHTML = '<div class="text-center py-10 opacity-50"><i class="fas fa-spinner fa-spin mb-2"></i><p class="text-xs">Loading detections...</p></div>';

    try {
        const detections = await api.get(`/detections/`);
        const videoDetections = detections.filter(d => d.video_id === id).sort((a, b) => a.timestamp - b.timestamp);

        if (videoDetections.length === 0) {
            jumpList.innerHTML = '<div class="text-center py-10 opacity-20"><i class="fas fa-list text-3xl mb-2"></i><p class="text-xs">No detections found</p></div>';
        } else {
            jumpList.innerHTML = videoDetections.map(d => `
                <button onclick="seekTo(${d.timestamp})" class="w-full text-left p-3 rounded-xl bg-white/5 hover:bg-blue-600/20 border border-white/5 hover:border-blue-500/30 transition-all group">
                    <div class="flex items-center justify-between mb-1">
                        <span class="text-xs font-bold text-white group-hover:text-blue-400 font-mono">${d.plate_number}</span>
                        <span class="text-[9px] text-slate-500 font-mono">${formatSeconds(d.timestamp)}</span>
                    </div>
                    <div class="flex items-center gap-2">
                         <div class="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
                             <div class="h-full bg-blue-500" style="width: ${d.confidence * 100}%"></div>
                         </div>
                         <span class="text-[8px] text-slate-600 uppercase font-black">${(d.confidence * 100).toFixed(0)}%</span>
                    </div>
                </button>
            `).join('');
        }
    } catch (err) {
        console.error(err);
        jumpList.innerHTML = '<p class="text-xs text-red-400 p-4">Failed to load timeline</p>';
    }

    modal.classList.remove('hidden');
    window.currentVideoId = id;
};

window.seekTo = (seconds) => {
    const player = document.getElementById('player');
    player.currentTime = seconds;
    player.play();
};

window.downloadReport = () => {
    if (!window.currentVideoId) return;
    window.open(`${API_BASE}/videos/${window.currentVideoId}/report`);
};


window.runSystemCheck = async () => {
    const btn = event.currentTarget;
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Scanning HW...';
    btn.disabled = true;

    try {
        const h = await api.get('/system/health');

        document.getElementById('health-disk').innerText = h.disk_name || 'HDD/SSD';
        document.getElementById('health-gpu').innerText = h.gpu_name || 'CPU-Mode';
        document.getElementById('health-roi').innerText = h.roi_status || 'MISSING';

        alert(`Hardware Intelligence Report:\n------------------\nCPU: ${h.cpu_name}\nGPU: ${h.gpu_name}\nRAM: ${h.memory_total}\nDisk: ${h.disk_name}\nRedis: ${h.redis_status}`);
    } catch (err) {
        alert('Health scan failed. Backend might be offline.');
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
};

window.closeVideoModal = () => {
    const modal = document.getElementById('video-modal');
    const player = document.getElementById('player');
    player.pause();
    modal.classList.add('hidden');
};

window.showLogs = async (videoId, filename, agentFilter = '') => {
    const modal = document.getElementById('logs-modal');
    const container = document.getElementById('logs-container');
    const title = document.getElementById('logs-title');
    const countEl = document.getElementById('logs-count');
    const filterSelect = document.getElementById('logs-agent-filter');

    window.currentLogVideoId = videoId;
    window.currentLogFilename = filename;
    if (agentFilter) filterSelect.value = agentFilter;

    title.innerText = agentFilter ? `${agentFilter} Agent Logs: ${filename}` : `Master Audit Logs: ${filename}`;
    modal.classList.remove('hidden');
    container.innerHTML = '<div class="text-blue-400 animate-pulse">Establishing forensic link...</div>';

    // Polling interval for logs
    if (window.logInterval) clearInterval(window.logInterval);

    const fetchLogs = async () => {
        const filter = document.getElementById('logs-agent-filter').value;
        try {
            const endpoint = filter ? `/v2/process/video/${videoId}/logs?agent=${filter}` : `/videos/${videoId}/logs`;
            const logs = await api.get(endpoint);
            countEl.innerText = `${logs.length} Events`;

            if (logs.length === 0) {
                container.innerHTML = '<div class="text-slate-600 italic">No logs generated yet. Processing starting...</div>';
                return;
            }

            container.innerHTML = logs.map(l => {
                const time = new Date(l.created_at).toLocaleTimeString();
                const colorMap = {
                    'AI_RECHECK': 'text-blue-400',
                    'GEMINI': 'text-blue-400',
                    'BATCH': 'text-purple-400',
                    'CAPTURER': 'text-purple-400',
                    'RECOVERED': 'text-emerald-400',
                    'QC': 'text-emerald-400',
                    'DETECTION': 'text-slate-200',
                    'DETECTOR': 'text-slate-200',
                    'SYSTEM': 'text-slate-400'
                };
                const iconMap = {
                    'AI_RECHECK': 'fa-robot',
                    'GEMINI': 'fa-robot',
                    'BATCH': 'fa-camera',
                    'CAPTURER': 'fa-camera',
                    'RECOVERED': 'fa-shield-halved',
                    'QC': 'fa-shield-halved',
                    'DETECTION': 'fa-crosshairs',
                    'DETECTOR': 'fa-crosshairs',
                    'SYSTEM': 'fa-info-circle'
                };

                const colorClass = l.is_error ? 'text-red-400' : (colorMap[l.event_type] || 'text-slate-400');
                const icon = l.is_error ? 'fa-circle-xmark' : (iconMap[l.event_type] || 'fa-circle-info');
                const hasExtra = l.event_type === 'AI_RECHECK' || l.event_type === 'GEMINI' || l.event_type === 'BATCH' || l.event_type === 'CAPTURER' || l.event_type === 'DETECTION' || l.event_type === 'DETECTOR' || l.extra_data;

                return `<div class="border-b border-white/5 pb-1">
                    <div class="flex gap-3 hover:bg-white/5 p-1 rounded transition-all ${hasExtra ? 'cursor-pointer' : ''} ${colorClass}" 
                         ${hasExtra ? `onclick="toggleLogDetails(${l.id})"` : ''}>
                        <span class="opacity-30 flex-shrink-0 font-mono">${time}</span>
                        <span class="w-20 font-bold uppercase text-[9px] flex-shrink-0 flex items-center gap-1">
                            <i class="fas ${icon}"></i>${l.event_type}
                        </span>
                        <span class="flex-1">${l.message}</span>
                        ${hasExtra ? '<i class="fas fa-chevron-down text-[8px] opacity-30 mt-1"></i>' : ''}
                    </div>
                    <div id="log-details-${l.id}" class="hidden mt-2 ml-10 p-3 bg-black/40 rounded-lg border border-white/5 text-[10px] overflow-x-auto">
                        <div class="animate-pulse text-blue-400">Fetching forensic data...</div>
                    </div>
                </div>`;
            }).join('');

            // Auto scroll
            container.scrollTop = container.scrollHeight;
        } catch (err) {
            console.error(err);
        }
    };

    fetchLogs();
    window.logInterval = setInterval(fetchLogs, 3000);
};

window.toggleLogDetails = async (logId) => {
    const details = document.getElementById(`log-details-${logId}`);
    if (!details) return;

    details.classList.toggle('hidden');
    if (details.classList.contains('hidden')) return;

    // Fetch details if not already loaded
    if (details.dataset.loaded) return;

    try {
        const data = await api.get(`/v2/logs/${logId}/details`);
        details.dataset.loaded = "true";

        if (!data.extra_data) {
            details.innerHTML = '<span class="text-slate-500 italic">No additional metadata available for this event.</span>';
            return;
        }

        // Check if it's JSON
        try {
            const trimmed = data.extra_data.trim();
            if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
                const json = JSON.parse(trimmed);
                details.innerHTML = `<pre class="text-emerald-400 font-mono text-[9px] bg-black/20 p-2 rounded border border-white/5">${JSON.stringify(json, null, 2)}</pre>`;
            } else {
                throw new Error("Not JSON");
            }
        } catch {
            // Check if it's an image path (contains .jpg or .png)
            if (data.extra_data.match(/\.(jpg|jpeg|png)$/i)) {
                // Robust filename extraction for Windows/Linux paths
                const filename = data.extra_data.replace(/\\/g, '/').split('/').pop();
                const url = data.extra_data.includes('collages')
                    ? `/api/v2/debug/collage_file/${filename}`
                    : data.extra_data;
                details.innerHTML = `
                    <div class="space-y-2">
                        <div class="text-[8px] opacity-40 font-mono">${data.extra_data}</div>
                        <img src="${url}" class="max-w-full rounded border border-white/10 shadow-2xl hover:scale-[1.02] transition-transform" 
                             onclick="window.open('${url}', '_blank')"
                             onerror="this.src='https://via.placeholder.com/400x300?text=Image+Not+Found'">
                    </div>`;
            } else {
                details.innerHTML = `<div class="text-slate-300 leading-relaxed">${data.extra_data}</div>`;
            }
        }
    } catch (err) {
        details.innerHTML = `<span class="text-red-400">Error: ${err.message}</span>`;
    }
};

window.refreshCurrentLogs = () => {
    if (window.currentLogVideoId) {
        showLogs(window.currentLogVideoId, window.currentLogFilename, document.getElementById('logs-agent-filter').value);
    }
};

window.clearLogs = () => {
    document.getElementById('logs-container').innerHTML = '<div class="text-slate-600 italic">Logs cleared for current session.</div>';
};

window.copyLogs = () => {
    const text = document.getElementById('logs-container').innerText;
    navigator.clipboard.writeText(text);
    alert('Logs copied to clipboard');
};

window.closeLogsModal = () => {
    document.getElementById('logs-modal').classList.add('hidden');
    if (window.logInterval) clearInterval(window.logInterval);
};
