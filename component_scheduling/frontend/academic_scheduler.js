// Academic Proposal/PP/Viva scheduling dashboard.
document.addEventListener('DOMContentLoaded', () => {
    const role = localStorage.getItem('ipms_role') || sessionStorage.getItem('ipms_role');
    const canManage = role === 'staff';
    const modal = document.getElementById('academicSchedulerModal');
    const openButton = document.getElementById('btnOpenAcademicScheduler');
    const closeButton = document.getElementById('closeAcademicModal');
    const managementControls = document.getElementById('academicManagementControls');
    const dashboard = document.getElementById('vivaDashboard');
    const eventList = document.getElementById('vivaEventsList');
    const summaryCards = document.getElementById('academicSummaryCards');
    if (!modal || !openButton || !closeButton || !dashboard || !eventList) return;

    if (managementControls && !canManage) managementControls.style.display = 'none';

    const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    })[character]);

    async function requestJson(url, options) {
        const token = localStorage.getItem('ipms_token') || sessionStorage.getItem('ipms_token');
        const requestOptions = { ...(options || {}) };
        requestOptions.headers = { ...(requestOptions.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
        const response = await fetch(url, requestOptions);
        let data;
        try { data = await response.json(); } catch (_) { data = {}; }
        if (response.status === 401) {
            if (typeof clearIpmsSessionAndReturnToLogin === 'function') {
                clearIpmsSessionAndReturnToLogin();
            }
            throw new Error('Your IPMS session is missing or expired. Please sign in again.');
        }
        if (!response.ok) throw new Error(data.detail || data.message || `HTTP ${response.status}`);
        return data;
    }

    function closeModal() { modal.classList.add('hidden'); }
    openButton.addEventListener('click', async () => {
        modal.classList.remove('hidden');
        await loadBatches();
        await Promise.all([loadExistingEvents(), autoFillProjectInfo(), loadResourcePreviews()]);
    });
    closeButton.addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => { if (event.target === modal) closeModal(); });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            const reschedule = document.getElementById('rescheduleModal');
            if (reschedule) reschedule.remove();
            else if (!modal.classList.contains('hidden')) closeModal();
        }
    });

    async function autoFillProjectInfo() {
        try {
            const data = await requestJson('/api/academic/current-project');
            if (!data.found) return;
            const banner = document.getElementById('projectAutofillBanner');
            if (banner) {
                banner.innerHTML = `Latest PostgreSQL project: <strong style="color:#a5b4fc;">${escapeHtml(data.group_id)}</strong> — ${escapeHtml(data.research_topic || 'Topic unavailable')}`;
                banner.style.display = 'block';
            }
        } catch (_) { /* Non-blocking dashboard hint. */ }
    }

    async function uploadWorkbook(inputId, endpoint, statusId, loadedKey, label) {
        const input = document.getElementById(inputId);
        const status = document.getElementById(statusId);
        const file = input?.files?.[0];
        if (!file) {
            status.textContent = 'Select an Excel file first.';
            status.style.color = '#f87171';
            return;
        }
        status.textContent = 'Uploading and validating...';
        status.style.color = '#fbbf24';
        const formData = new FormData();
        formData.append('file', file);
        try {
            const data = await requestJson(endpoint, { method: 'POST', body: formData });
            if (data.status !== 'ok') throw new Error(data.message || 'Upload failed.');
            status.textContent = `Loaded ${data[loadedKey]} ${label}.`;
            status.style.color = '#34d399';
            await loadResourcePreviews();
        } catch (error) {
            status.textContent = error.message;
            status.style.color = '#f87171';
        }
    }

    document.getElementById('btnUploadSupervisors')?.addEventListener('click', () =>
        uploadWorkbook('supervisorFile', '/api/academic/upload-supervisors', 'supervisorUploadStatus', 'supervisors_loaded', 'staff members')
    );
    document.getElementById('btnUploadHalls')?.addEventListener('click', () =>
        uploadWorkbook('hallFile', '/api/academic/upload-halls', 'hallUploadStatus', 'halls_loaded', 'halls')
    );

    async function loadResourcePreviews() {
        try {
            const [supervisors, halls] = await Promise.all([
                requestJson('/api/academic/supervisors'), requestJson('/api/academic/halls')
            ]);
            const supervisorPreview = document.getElementById('supervisorPreview');
            const hallPreview = document.getElementById('hallPreview');
            if (supervisorPreview) supervisorPreview.innerHTML = supervisors.length ? `<table style="width:100%;border-collapse:collapse;"><tbody>${supervisors.map((item) =>
                `<tr><td style="padding:.25rem;color:#e2e8f0;">${escapeHtml(item.name)}</td><td style="padding:.25rem;color:#a5b4fc;">${escapeHtml(item.role)}</td><td style="padding:.25rem;color:var(--text-muted);">${escapeHtml(item.expertise)}</td></tr>`
            ).join('')}</tbody></table>` : '<span style="color:var(--text-muted);">No staff uploaded.</span>';
            if (hallPreview) hallPreview.innerHTML = halls.length ? `<table style="width:100%;border-collapse:collapse;"><tbody>${halls.map((item) =>
                `<tr><td style="padding:.25rem;color:#e2e8f0;">${escapeHtml(item.hall_name)}</td><td style="padding:.25rem;color:var(--text-muted);">Capacity ${escapeHtml(item.capacity)}</td><td style="padding:.25rem;color:var(--text-muted);">${escapeHtml(item.available_times)}</td></tr>`
            ).join('')}</tbody></table>` : '<span style="color:var(--text-muted);">No halls uploaded.</span>';
        } catch (_) { /* Upload status provides actionable errors. */ }
    }

    document.getElementById('btnAutoSchedule')?.addEventListener('click', async () => {
        const button = document.getElementById('btnAutoSchedule');
        const status = document.getElementById('autoScheduleStatus');
        const payload = {
            start_date: document.getElementById('projectStartDate').value,
            proposal_week: Number(document.getElementById('proposalWeek').value),
            pp1_week: Number(document.getElementById('pp1Week').value),
            pp2_week: Number(document.getElementById('pp2Week').value),
            viva_week: Number(document.getElementById('vivaWeek').value),
            duration_minutes: Number(document.getElementById('eventDuration').value),
            default_team_size: Number(document.getElementById('defaultTeamSize').value),
            audience_seats: Number(document.getElementById('academicAudienceSeats').value)
        };
        button.disabled = true;
        status.textContent = 'Loading PostgreSQL groups and checking all panel/hall constraints...';
        status.style.color = '#fbbf24';
        try {
            const data = await requestJson('/api/academic/auto-schedule', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
            });
            selectedBatchId = data.batch_id;
            status.textContent = `Draft version ${data.batch_version} created with ${data.events_created} events for ${data.groups_scheduled} group(s): ${data.scheduled_count} scheduled, ${data.unscheduled_count} requiring staff review.`;
            status.style.color = data.unscheduled_count ? '#fbbf24' : '#34d399';
            await loadBatches();
            await loadExistingEvents();
        } catch (error) {
            status.textContent = error.message;
            status.style.color = '#f87171';
        } finally {
            button.disabled = false;
        }
    });

    async function downloadAcademicExport(path, filename) {
        try {
            const token = localStorage.getItem('ipms_token') || sessionStorage.getItem('ipms_token');
            const query = selectedBatchId ? `?batch_id=${selectedBatchId}` : '';
            const response = await fetch(`${path}${query}`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {}
            });
            if (!response.ok) throw new Error(`Export failed (HTTP ${response.status}).`);
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            link.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            alert(error.message);
        }
    }
    document.getElementById('btnExportExcel')?.addEventListener('click', () =>
        downloadAcademicExport('/api/academic/events/export-excel', 'academic_schedule.xlsx'));
    document.getElementById('btnExportCalendar')?.addEventListener('click', () =>
        downloadAcademicExport('/api/academic/events/export-calendar', 'academic_schedule.ics'));

    const typeMeta = {
        'Proposal Presentation': { accent: '#818cf8', bg: 'rgba(99,102,241,.15)', label: 'Proposal Presentation' },
        PP1: { accent: '#fbbf24', bg: 'rgba(245,158,11,.12)', label: 'Progress Presentation 1 (PP1)' },
        PP2: { accent: '#34d399', bg: 'rgba(16,185,129,.12)', label: 'Progress Presentation 2 (PP2)' },
        Viva: { accent: '#f9a8d4', bg: 'rgba(236,72,153,.12)', label: 'Final Viva' }
    };
    let allEvents = [];
    let activeFilter = 'all';
    let activeStatus = 'all';
    let currentPage = 1;
    let pageSize = 10;
    let visibleGroupIds = [];
    const expandedGroups = new Set();
    let scheduleBatches = [];
    let selectedBatchId = null;
    const vivaProgressCache = new Map();

    function vivaBriefingHtml(summary, eventId) {
        if (!summary?.available) {
            return `<div class="viva-progress-empty">${escapeHtml(summary?.message || 'Progress evidence is not available yet.')}</div>`;
        }
        const mode = summary.snapshot_mode === 'FROZEN' ? 'Frozen evaluation snapshot' : 'Live progress';
        const warnings = (summary.warnings || []).length
            ? `<div class="viva-progress-warning"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(summary.warnings.join(' · '))}</div>`
            : '<div class="viva-progress-ok"><i class="fa-solid fa-circle-check"></i> No overdue or behind-schedule tasks</div>';
        return `<div class="viva-progress-head">
                <span><i class="fa-solid fa-chart-line"></i> Viva panel progress briefing</span>
                <span class="viva-progress-mode">${escapeHtml(mode)}</span>
            </div>
            <div class="viva-progress-grid">
                <div><strong>${summary.overall_progress_pct}%</strong><small>Verified progress</small></div>
                <div><strong>${summary.completed_tasks}/${summary.total_tasks}</strong><small>Tasks completed</small></div>
                <div><strong>${summary.documents.approved}</strong><small>Docs approved</small></div>
                <div><strong>${summary.github.linked}</strong><small>Git evidence linked</small></div>
            </div>
            ${warnings}
            <div class="viva-progress-foot">Read-only evidence summary · ${summary.documents.pending_review} document(s) pending · ${summary.github.flagged} Git item(s) flagged</div>
            ${canManage && summary.snapshot_mode !== 'FROZEN' ? `<button type="button" class="freeze-viva-progress" data-event-id="${eventId}"><i class="fa-solid fa-camera"></i> Freeze for Viva evaluation</button>` : ''}`;
    }

    async function loadVivaBriefings() {
        const containers = [...eventList.querySelectorAll('.viva-progress-briefing')];
        await Promise.all(containers.map(async (container) => {
            const eventId = Number(container.dataset.eventId);
            try {
                let summary = vivaProgressCache.get(eventId);
                // Frozen evaluation evidence is immutable; live progress is
                // refreshed whenever the dashboard renders.
                if (!summary || summary.snapshot_mode !== 'FROZEN') {
                    summary = await requestJson(`/api/progress/viva-summary?event_id=${eventId}`);
                    vivaProgressCache.set(eventId, summary);
                }
                container.innerHTML = vivaBriefingHtml(summary, eventId);
            } catch (error) {
                container.innerHTML = `<div class="viva-progress-empty">${escapeHtml(error.message)}</div>`;
            }
        }));
    }

    function renderBatchControls() {
        const select = document.getElementById('academicBatchSelect');
        const status = document.getElementById('academicBatchStatus');
        const publish = document.getElementById('btnPublishAcademicBatch');
        const remove = document.getElementById('btnDeleteAcademicDraft');
        if (!select || !status || !publish || !remove) return;
        if (!scheduleBatches.length) {
            select.innerHTML = '<option value="">Legacy / no version</option>';
            status.textContent = 'No versioned schedule yet';
            publish.style.display = 'none';
            remove.style.display = 'none';
            return;
        }
        select.innerHTML = scheduleBatches.map((batch) =>
            `<option value="${batch.id}"${Number(batch.id) === Number(selectedBatchId) ? ' selected' : ''}>Version ${batch.version} — ${escapeHtml(batch.status)} (${batch.event_count} events)</option>`
        ).join('');
        const current = scheduleBatches.find((batch) => Number(batch.id) === Number(selectedBatchId));
        status.textContent = current ? `${current.unscheduled_count} need review • by ${current.created_by}` : '';
        publish.style.display = canManage && current && current.status !== 'PUBLISHED' ? '' : 'none';
        publish.textContent = current?.status === 'ARCHIVED' ? 'Restore & Publish' : 'Publish';
        remove.style.display = canManage && current?.status === 'DRAFT' ? '' : 'none';
    }

    async function loadBatches() {
        try {
            scheduleBatches = await requestJson('/api/academic/batches');
            if (!scheduleBatches.some((batch) => Number(batch.id) === Number(selectedBatchId))) {
                const active = scheduleBatches.find((batch) => batch.status === 'PUBLISHED') || scheduleBatches[0];
                selectedBatchId = active?.id || null;
            }
            renderBatchControls();
        } catch (error) {
            scheduleBatches = [];
            renderBatchControls();
        }
    }

    document.getElementById('academicBatchSelect')?.addEventListener('change', async (event) => {
        selectedBatchId = Number(event.target.value) || null;
        renderBatchControls();
        await loadExistingEvents();
    });

    document.getElementById('btnPublishAcademicBatch')?.addEventListener('click', async () => {
        if (!selectedBatchId) return;
        const button = document.getElementById('btnPublishAcademicBatch');
        button.disabled = true;
        try {
            const current = scheduleBatches.find((batch) => Number(batch.id) === Number(selectedBatchId));
            const action = current?.status === 'ARCHIVED' ? 'rollback' : 'publish';
            await requestJson(`/api/academic/batches/${selectedBatchId}/${action}`, { method: 'POST' });
            await loadBatches();
            await loadExistingEvents();
        } catch (error) {
            alert(error.message);
        } finally {
            button.disabled = false;
        }
    });

    document.getElementById('btnDeleteAcademicDraft')?.addEventListener('click', async () => {
        if (!selectedBatchId || !confirm('Delete this draft schedule? Published schedules are never deleted here.')) return;
        try {
            await requestJson(`/api/academic/batches/${selectedBatchId}`, { method: 'DELETE' });
            selectedBatchId = null;
            await loadBatches();
            await loadExistingEvents();
        } catch (error) {
            alert(error.message);
        }
    });

    function displayDate(value) {
        if (!value) return 'TBD';
        const parsed = new Date(`${value}T00:00:00`);
        return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
    }

    function renderSummary() {
        if (!summaryCards) return;
        const scheduled = allEvents.filter((event) => event.status === 'Scheduled').length;
        const unscheduled = allEvents.filter((event) => event.status === 'Unscheduled').length;
        const groups = new Set(allEvents.map((event) => event.group_id)).size;
        const cards = [['Groups', groups, '#93c5fd'], ['All Events', allEvents.length, '#c4b5fd'], ['Scheduled', scheduled, '#86efac'], ['Needs Review', unscheduled, '#fca5a5']];
        summaryCards.innerHTML = cards.map(([label, value, color]) => `<div class="academic-summary-card" style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:9px;padding:.55rem;text-align:center;"><div style="font-size:1.05rem;font-weight:800;color:${color};">${value}</div><div style="font-size:.62rem;color:var(--text-muted);text-transform:uppercase;">${label}</div></div>`).join('');
    }

    function renderEvents() {
        renderSummary();
        const searchInput = document.getElementById('academicGroupSearch');
        const clearSearch = document.getElementById('btnClearAcademicSearch');
        const resultsCount = document.getElementById('academicResultsCount');
        const pagination = document.getElementById('academicPagination');
        const pageInfo = document.getElementById('academicPageInfo');
        const previous = document.getElementById('btnAcademicPrev');
        const next = document.getElementById('btnAcademicNext');
        const expandPage = document.getElementById('btnExpandAcademicPage');
        const searchTerm = (searchInput?.value || '').trim().toLowerCase();

        if (clearSearch) clearSearch.style.display = searchTerm ? 'inline-flex' : 'none';

        const events = allEvents.filter((event) => {
            const matchesType = activeFilter === 'all' || event.event_type === activeFilter;
            const matchesStatus = activeStatus === 'all' || event.status === activeStatus;
            const searchable = `${event.group_id || ''} ${event.group_topic || ''}`.toLowerCase();
            return matchesType && matchesStatus && (!searchTerm || searchable.includes(searchTerm));
        });
        if (!events.length) {
            eventList.innerHTML = `<div class="academic-empty-result" style="padding:1.4rem;text-align:center;color:var(--text-muted);border:1px dashed rgba(255,255,255,.12);border-radius:10px;">
                <i class="fa-solid fa-magnifying-glass" style="display:block;font-size:1.2rem;margin-bottom:.45rem;color:#64748b;"></i>
                No groups match the current search and filters.
            </div>`;
            if (resultsCount) resultsCount.textContent = `0 groups • 0 matching events`;
            if (pagination) pagination.style.display = 'none';
            visibleGroupIds = [];
            return;
        }
        const grouped = events.reduce((result, event) => { (result[event.group_id] ||= []).push(event); return result; }, {});
        const groups = Object.entries(grouped).sort(([left], [right]) =>
            left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' }));
        const totalGroups = groups.length;
        const totalPages = Math.max(1, Math.ceil(totalGroups / pageSize));
        currentPage = Math.min(Math.max(1, currentPage), totalPages);
        const startIndex = (currentPage - 1) * pageSize;
        const pageGroups = groups.slice(startIndex, startIndex + pageSize);
        visibleGroupIds = pageGroups.map(([groupId]) => groupId);

        if (resultsCount) {
            resultsCount.textContent = `Showing ${startIndex + 1}–${startIndex + pageGroups.length} of ${totalGroups} group${totalGroups === 1 ? '' : 's'} • ${events.length} matching event${events.length === 1 ? '' : 's'}`;
        }
        if (pagination && pageInfo && previous && next) {
            pagination.style.display = totalPages > 1 ? 'flex' : 'none';
            pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
            previous.disabled = currentPage === 1;
            next.disabled = currentPage === totalPages;
        }
        if (expandPage) {
            const allVisibleExpanded = visibleGroupIds.length > 0 && visibleGroupIds.every((groupId) => expandedGroups.has(groupId));
            expandPage.innerHTML = allVisibleExpanded
                ? '<i class="fa-solid fa-angles-up"></i> Collapse page'
                : '<i class="fa-solid fa-angles-down"></i> Expand page';
        }

        const eventOrder = { 'Proposal Presentation': 0, PP1: 1, PP2: 2, Viva: 3 };
        eventList.innerHTML = pageGroups.map(([groupId, groupEvents]) => {
            groupEvents.sort((left, right) => (eventOrder[left.event_type] ?? 99) - (eventOrder[right.event_type] ?? 99));
            const isExpanded = expandedGroups.has(groupId);
            const scheduledCount = groupEvents.filter((event) => event.status === 'Scheduled' || event.status === 'Completed').length;
            const reviewCount = groupEvents.filter((event) => event.status === 'Unscheduled').length;
            const cards = groupEvents.map((event) => {
                const meta = typeMeta[event.event_type] || typeMeta.PP1;
                const statusColor = event.status === 'Scheduled' ? '#34d399' : event.status === 'Completed' ? '#60a5fa' : '#f87171';
                const eventClass = event.event_type === 'Proposal Presentation' ? 'proposal' : event.event_type.toLowerCase();
                const statusClass = String(event.status || 'unscheduled').toLowerCase();
                const panel = (event.panel || []).map((member) => `<div class="academic-panel-member" style="background:rgba(255,255,255,.04);border-radius:6px;padding:.35rem .5rem;"><div class="academic-panel-role" style="font-size:.6rem;color:#a5b4fc;font-weight:700;">${escapeHtml(member.role)}</div><div class="academic-panel-name" style="font-size:.73rem;color:#e2e8f0;">${escapeHtml(member.name)}</div></div>`).join('');
                return `<article class="academic-event-card academic-event-${eventClass}" style="background:${meta.bg};border:1px solid ${meta.accent}55;border-radius:12px;padding:1rem;margin-bottom:.7rem;">
                    <div style="display:flex;justify-content:space-between;gap:.5rem;"><strong class="academic-event-title" style="color:${meta.accent};">${meta.label}</strong><span class="academic-event-status status-${statusClass}" style="color:${statusColor};font-size:.7rem;font-weight:700;">${escapeHtml(event.status)}</span></div>
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;margin:.65rem 0;font-size:.72rem;"><div><small>DATE</small><br>${escapeHtml(displayDate(event.scheduled_date))}</div><div><small>TIME</small><br>${escapeHtml(event.scheduled_time || 'TBD')}</div><div><small>HALL</small><br>${escapeHtml(event.hall_name || 'TBD')}</div></div>
                    <div style="font-size:.75rem;display:flex;justify-content:space-between;align-items:center;gap:.5rem;"><span>Primary: <strong>${escapeHtml(event.supervisor_name || 'TBD')}</strong></span>${canManage ? `<button type="button" class="icon-btn reschedule-event" data-event-id="${event.id}" title="Conflict-checked reschedule"><i class="fa-solid fa-calendar-day"></i></button>` : ''}</div>
                    ${event.notes ? `<div style="font-size:.68rem;color:var(--text-muted);margin-top:.4rem;">${escapeHtml(event.notes)}</div>` : ''}<div style="display:grid;grid-template-columns:1fr 1fr;gap:.3rem;margin-top:.55rem;">${panel}</div>
                    ${event.event_type === 'Viva' ? `<div class="viva-progress-briefing" data-event-id="${event.id}"><div class="viva-progress-empty"><i class="fa-solid fa-spinner fa-spin"></i> Loading verified progress...</div></div>` : ''}
                </article>`;
            }).join('');
            return `<section class="academic-group-section">
                <button type="button" class="academic-group-toggle" data-group-id="${escapeHtml(groupId)}" aria-expanded="${isExpanded}">
                    <span class="academic-group-id">${escapeHtml(groupId)}</span>
                    <span class="academic-group-topic" title="${escapeHtml(groupEvents[0].group_topic || 'Topic unavailable')}">${escapeHtml(groupEvents[0].group_topic || 'Topic unavailable')}</span>
                    <span class="academic-group-badges">
                        <span class="academic-group-badge" style="background:rgba(16,185,129,.12);color:#86efac;">${scheduledCount} scheduled</span>
                        ${reviewCount ? `<span class="academic-group-badge" style="background:rgba(239,68,68,.12);color:#fca5a5;">${reviewCount} review</span>` : ''}
                    </span>
                    <i class="fa-solid fa-chevron-${isExpanded ? 'up' : 'down'}" style="color:#64748b;"></i>
                </button>
                ${isExpanded ? `<div class="academic-group-events">${cards}</div>` : ''}
            </section>`;
        }).join('');
        eventList.querySelectorAll('.academic-group-toggle').forEach((button) => button.addEventListener('click', () => {
            const groupId = button.dataset.groupId;
            if (expandedGroups.has(groupId)) expandedGroups.delete(groupId);
            else expandedGroups.add(groupId);
            renderEvents();
        }));
        eventList.querySelectorAll('.reschedule-event').forEach((button) => button.addEventListener('click', () => openRescheduleModal(Number(button.dataset.eventId))));
        loadVivaBriefings().then(() => {
            eventList.querySelectorAll('.freeze-viva-progress').forEach((button) => button.addEventListener('click', async () => {
                const eventId = Number(button.dataset.eventId);
                button.disabled = true;
                try {
                    const summary = await requestJson('/api/progress/viva-snapshot', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ event_id: eventId })
                    });
                    vivaProgressCache.set(eventId, summary);
                    const container = eventList.querySelector(`.viva-progress-briefing[data-event-id="${eventId}"]`);
                    if (container) container.innerHTML = vivaBriefingHtml(summary, eventId);
                } catch (error) { alert(error.message); }
                finally { button.disabled = false; }
            }));
        });
    }

    async function loadExistingEvents() {
        try {
            const query = selectedBatchId ? `?batch_id=${selectedBatchId}` : '';
            allEvents = await requestJson(`/api/academic/events${query}`);
            currentPage = 1;
            expandedGroups.clear();
            const loadedGroups = [...new Set(allEvents.map((event) => event.group_id))];
            if (loadedGroups.length === 1) expandedGroups.add(loadedGroups[0]);
            dashboard.style.display = 'block';
            renderEvents();
            await loadAudit();
        } catch (error) {
            dashboard.style.display = 'block';
            eventList.innerHTML = `<div style="color:#f87171;padding:1rem;">${escapeHtml(error.message)}</div>`;
        }
    }

    async function loadAudit() {
        const container = document.getElementById('academicAuditList');
        if (!container) return;
        if (!selectedBatchId) {
            container.textContent = 'No versioned audit is available.';
            return;
        }
        try {
            const entries = await requestJson(`/api/academic/audit?batch_id=${selectedBatchId}`);
            container.innerHTML = entries.length ? entries.map((entry) => {
                const when = new Date(entry.created_at).toLocaleString();
                return `<div style="padding:.35rem 0;border-bottom:1px solid rgba(255,255,255,.06);"><strong style="color:#e2e8f0;">${escapeHtml(entry.action)}</strong> by ${escapeHtml(entry.actor)} • ${escapeHtml(when)}${entry.reason ? `<br>${escapeHtml(entry.reason)}` : ''}</div>`;
            }).join('') : 'No changes have been recorded for this version.';
        } catch (error) {
            container.textContent = error.message;
        }
    }
    window.refreshAcademicEvents = loadExistingEvents;

    document.getElementById('eventTypeFilter')?.addEventListener('click', (event) => {
        const button = event.target.closest('.evt-filter-btn');
        if (!button) return;
        activeFilter = button.dataset.type;
        currentPage = 1;
        document.querySelectorAll('#eventTypeFilter .evt-filter-btn').forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        renderEvents();
    });

    document.getElementById('academicGroupSearch')?.addEventListener('input', () => {
        currentPage = 1;
        renderEvents();
    });
    document.getElementById('btnClearAcademicSearch')?.addEventListener('click', () => {
        const search = document.getElementById('academicGroupSearch');
        if (search) {
            search.value = '';
            search.focus();
        }
        currentPage = 1;
        renderEvents();
    });
    document.getElementById('academicStatusFilter')?.addEventListener('change', (event) => {
        activeStatus = event.target.value;
        currentPage = 1;
        renderEvents();
    });
    document.getElementById('academicPageSize')?.addEventListener('change', (event) => {
        pageSize = Number(event.target.value) || 10;
        currentPage = 1;
        renderEvents();
    });
    document.getElementById('btnAcademicPrev')?.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage -= 1;
            renderEvents();
        }
    });
    document.getElementById('btnAcademicNext')?.addEventListener('click', () => {
        currentPage += 1;
        renderEvents();
    });
    document.getElementById('btnExpandAcademicPage')?.addEventListener('click', () => {
        const shouldCollapse = visibleGroupIds.length > 0 && visibleGroupIds.every((groupId) => expandedGroups.has(groupId));
        visibleGroupIds.forEach((groupId) => {
            if (shouldCollapse) expandedGroups.delete(groupId);
            else expandedGroups.add(groupId);
        });
        renderEvents();
    });

    async function openRescheduleModal(eventId) {
        const event = allEvents.find((item) => item.id === eventId);
        if (!event) return;
        document.getElementById('rescheduleModal')?.remove();
        let halls = [];
        try { halls = await requestJson('/api/academic/halls'); } catch (_) { /* Backend validates hall. */ }
        document.body.insertAdjacentHTML('beforeend', `<div id="rescheduleModal" class="modal-overlay" style="z-index:1500;"><div class="modal-box glass-panel" style="max-width:430px;"><div class="modal-header"><h3>Reschedule ${escapeHtml(event.event_type)}</h3><button type="button" id="closeRescheduleModal" class="icon-btn"><i class="fa-solid fa-xmark"></i></button></div><div style="display:grid;gap:.7rem;"><label>Date<input type="date" id="rsDate" value="${escapeHtml(event.scheduled_date || '')}"></label><label>Time range<input type="text" id="rsTime" value="${escapeHtml(event.scheduled_time || '09:00 - 10:00')}" placeholder="09:00 - 10:00"></label><label>Hall<input type="text" id="rsHall" list="academicHallOptions" value="${escapeHtml(event.hall_name === 'TBD' ? '' : event.hall_name)}"><datalist id="academicHallOptions">${halls.map((hall) => `<option value="${escapeHtml(hall.hall_name)}"></option>`).join('')}</datalist></label><div id="rsError" style="display:none;color:#f87171;font-size:.78rem;"></div><button type="button" id="btnSubmitReschedule" class="primary-btn">Check &amp; Reschedule</button></div></div></div>`);
        const rescheduleModal = document.getElementById('rescheduleModal');
        const remove = () => rescheduleModal.remove();
        document.getElementById('closeRescheduleModal').addEventListener('click', remove);
        rescheduleModal.addEventListener('click', (clickEvent) => { if (clickEvent.target === rescheduleModal) remove(); });
        document.getElementById('btnSubmitReschedule').addEventListener('click', async () => {
            const submit = document.getElementById('btnSubmitReschedule');
            const errorBox = document.getElementById('rsError');
            submit.disabled = true;
            try {
                const data = await requestJson(`/api/academic/events/${eventId}/reschedule`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ new_date: document.getElementById('rsDate').value, new_time: document.getElementById('rsTime').value, new_hall: document.getElementById('rsHall').value }) });
                if (data.status === 'conflict') {
                    const conflictLines = (data.conflicts || []).map((conflict) => `<li>${escapeHtml(conflict.message)}</li>`).join('');
                    errorBox.innerHTML = conflictLines ? `<strong>Cannot reschedule:</strong><ul style="margin:.35rem 0 0 1rem;">${conflictLines}</ul>` : escapeHtml(data.message);
                    errorBox.style.display = 'block';
                    return;
                }
                remove();
                await loadExistingEvents();
            } catch (error) {
                errorBox.textContent = error.message;
                errorBox.style.display = 'block';
            } finally {
                if (document.body.contains(submit)) submit.disabled = false;
            }
        });
    }
});
