/**
 * IPMS Global Theme Toggle v2
 * ─────────────────────────────────────────────────────────────────────────────
 * Strategy: Injects a <style> element via JS (AFTER all inline <style> blocks)
 * so light-mode rules always win the cascade — even against !important in HTML.
 * Button uses 100% inline styles so page CSS can never override them.
 * Persists theme to localStorage key 'ipms-theme'.
 * ─────────────────────────────────────────────────────────────────────────────
 */
(function () {

    /* ── 1. Comprehensive Light-Mode CSS ────────────────────────────────────── */
    const LIGHT_CSS = `
        :root[data-theme="light"] {
            color-scheme: light;
            --bg-dark: #eef3f8;
            --panel-bg: rgba(255,255,255,.94);
            --panel-border: rgba(15,23,42,.13);
            --text-main: #172033;
            --text-muted: #5f6f85;
            --brand-primary: #2563eb;
            --brand-hover: #1d4ed8;
            --brand-glow: rgba(37,99,235,.18);
            --success: #047857;
            --success-bg: rgba(5,150,105,.12);
            --danger: #dc2626;
            --danger-bg: rgba(220,38,38,.10);
            --purple: #7c3aed;
            --purple-bg: rgba(124,58,237,.10);
            --surface: #ffffff;
            --surface-soft: #f8fafc;
            --surface-muted: #eef2f7;
            --surface-hover: #f1f5f9;
            --line-subtle: rgba(15,23,42,.09);
            --shadow-panel: 0 8px 28px rgba(15,23,42,.09);
        }

        html[data-theme="light"], html[data-theme="light"] body {
            background: #eef3f8 !important;
            background-image: none !important;
            color: var(--text-main) !important;
        }
        html[data-theme="light"] .background-elements { opacity: .16; }
        html[data-theme="light"] .glow { filter: blur(150px); }

        /* Surfaces */
        html[data-theme="light"] .glass-panel,
        html[data-theme="light"] .card,
        html[data-theme="light"] .team-card,
        html[data-theme="light"] .panel,
        html[data-theme="light"] .metric-card,
        html[data-theme="light"] .modal-content,
        html[data-theme="light"] .notif-panel {
            background: var(--surface) !important;
            border-color: var(--panel-border) !important;
            color: var(--text-main) !important;
            box-shadow: var(--shadow-panel) !important;
            backdrop-filter: none !important;
        }
        html[data-theme="light"] .app-header,
        html[data-theme="light"] .header {
            border-color: var(--panel-border) !important;
        }
        html[data-theme="light"] .badge,
        html[data-theme="light"] .meta-pill,
        html[data-theme="light"] .secondary-btn,
        html[data-theme="light"] .notif-bell {
            background: var(--surface-soft) !important;
            border-color: var(--panel-border) !important;
            color: var(--text-main) !important;
        }
        html[data-theme="light"] .secondary-btn:hover,
        html[data-theme="light"] .notif-bell:hover {
            background: #e8f0ff !important;
            border-color: rgba(37,99,235,.42) !important;
        }

        /* Form controls */
        html[data-theme="light"] input,
        html[data-theme="light"] select,
        html[data-theme="light"] textarea {
            background: #ffffff !important;
            border-color: rgba(15,23,42,.18) !important;
            color: var(--text-main) !important;
        }
        html[data-theme="light"] input::placeholder,
        html[data-theme="light"] textarea::placeholder { color: #8795a8 !important; }
        html[data-theme="light"] input:focus,
        html[data-theme="light"] select:focus,
        html[data-theme="light"] textarea:focus {
            border-color: var(--brand-primary) !important;
            box-shadow: 0 0 0 3px rgba(37,99,235,.13) !important;
        }
        html[data-theme="light"] input[type="file"]::file-selector-button {
            background: #e8f0ff; border: 1px solid #bfdbfe; color: #1d4ed8;
            border-radius: 6px; padding: .35rem .55rem; cursor: pointer;
        }

        /* Main scheduler and progress */
        html[data-theme="light"] .empty-state,
        html[data-theme="light"] .kpi-card,
        html[data-theme="light"] .gantt-panel,
        html[data-theme="light"] .progress-tracker-panel { background: #fff !important; }
        html[data-theme="light"] .empty-icon { color: #94a3b8 !important; }
        html[data-theme="light"] .project-progress-row,
        html[data-theme="light"] .member-card,
        html[data-theme="light"] .tp-stat-box,
        html[data-theme="light"] .evidence-card,
        html[data-theme="light"] .review-queue-item {
            background: var(--surface-soft) !important;
            border-color: var(--line-subtle) !important;
            color: var(--text-main) !important;
        }
        html[data-theme="light"] .assign-row {
            background: #fff !important;
            border-color: var(--line-subtle) !important;
        }
        html[data-theme="light"] .assign-row:hover { background: #f5f8fc !important; }
        html[data-theme="light"] .assign-row.is-completed { background: #ecfdf5 !important; }
        html[data-theme="light"] .member-progress-bar,
        html[data-theme="light"] .progress-track,
        html[data-theme="light"] .progress-container,
        html[data-theme="light"] .task-track,
        html[data-theme="light"] .wb-bar-bg { background: #e2e8f0 !important; }
        html[data-theme="light"] .component-progress-track { background: #dbe3ed !important; }
        html[data-theme="light"] .component-task-card { background-color: rgba(248,250,252,.9) !important; }
        html[data-theme="light"] .component-task-title,
        html[data-theme="light"] .component-task-name:not(.completed) { color: var(--text-main) !important; }
        html[data-theme="light"] .component-task-row { border-color: var(--line-subtle) !important; }
        html[data-theme="light"] .component-owner { color: #334155 !important; }
        html[data-theme="light"] .tp-stat-val,
        html[data-theme="light"] .task-name,
        html[data-theme="light"] .member-name { color: var(--text-main) !important; }
        html[data-theme="light"] .review-queue { background: #f0f9ff !important; }

        /* Gantt DOM is generated dynamically with inline dark colors. */
        html[data-theme="light"] #ganttContainer { background: #fff !important; }
        html[data-theme="light"] #ganttContainer > div { border-color: var(--line-subtle) !important; }
        html[data-theme="light"] #ganttContainer .gantt-task-name { color: var(--text-main) !important; }
        html[data-theme="light"] #ganttContainer .gantt-lane-name { color: #334155 !important; }
        html[data-theme="light"] #ganttContainer .gantt-lane-header { background: #f4f7fb !important; }
        html[data-theme="light"] #ganttContainer .gantt-task-row:hover { background: #f8fafc !important; }
        html[data-theme="light"] #ganttContainer .gantt-grid-line { background: rgba(15,23,42,.09) !important; }
        html[data-theme="light"] #ganttContainer .gantt-today-label { color: #a16207 !important; }

        /* Assignment selector */
        html[data-theme="light"] .ms-display,
        html[data-theme="light"] .ms-panel {
            background: #fff !important;
            border-color: rgba(15,23,42,.15) !important;
            color: var(--text-main) !important;
        }
        html[data-theme="light"] .ms-panel { box-shadow: 0 12px 30px rgba(15,23,42,.16) !important; }
        html[data-theme="light"] .ms-option { color: var(--text-main) !important; }
        html[data-theme="light"] .ms-option:hover { background: #eaf1ff !important; }
        html[data-theme="light"] .ms-sep { border-color: var(--line-subtle) !important; }

        /* Workload result */
        html[data-theme="light"] .workload-result-card { background: #f0fdf9 !important; border-color: #a7f3d0 !important; }
        html[data-theme="light"] .wb-summary,
        html[data-theme="light"] .wb-member-name,
        html[data-theme="light"] .wb-hours,
        html[data-theme="light"] .wb-method-note { color: #334155 !important; }
        html[data-theme="light"] .wb-stat,
        html[data-theme="light"] .workload-result-card > div:nth-of-type(2) > div {
            background: #fff !important; border: 1px solid var(--line-subtle);
        }
        html[data-theme="light"] .wb-method-note { border-color: var(--line-subtle) !important; }
        html[data-theme="light"] .workload-result-card > div:nth-of-type(2) > div:nth-child(1) span:nth-child(2) { color: #a16207 !important; }
        html[data-theme="light"] .workload-result-card > div:nth-of-type(2) > div:nth-child(2) span:nth-child(2) { color: #1d4ed8 !important; }
        html[data-theme="light"] .workload-result-card > div:nth-of-type(2) > div:nth-child(3) span:nth-child(2) { color: #b91c1c !important; }
        html[data-theme="light"] .wb-score-badge.balance-excellent > div { color: #047857 !important; }
        html[data-theme="light"] .wb-score-badge.balance-good > div { color: #1d4ed8 !important; }
        html[data-theme="light"] .wb-score-badge.balance-fair > div { color: #92400e !important; }
        html[data-theme="light"] .wb-score-badge.balance-poor > div,
        html[data-theme="light"] .wb-score-badge.balance-overloaded > div { color: #b91c1c !important; }

        /* Modals and history */
        html[data-theme="light"] .modal-overlay { background: rgba(15,23,42,.42) !important; }
        html[data-theme="light"] .modal-box { background: #fff !important; color: var(--text-main) !important; }
        html[data-theme="light"] .modal-header { border-color: var(--line-subtle) !important; }
        html[data-theme="light"] #tpModalTitle { color: var(--text-main) !important; }
        html[data-theme="light"] #webhookInstructions { background: var(--surface-soft) !important; }
        html[data-theme="light"] .schedule-history-item {
            background: #eff6ff !important; border-color: #bfdbfe !important;
        }
        html[data-theme="light"] .schedule-history-item:hover { background: #dbeafe !important; }
        html[data-theme="light"] .history-version { color: #1d4ed8 !important; }
        html[data-theme="light"] .history-group { color: #6d28d9 !important; }
        html[data-theme="light"] .history-task-count { color: var(--text-main) !important; }
        html[data-theme="light"] .history-actions { border-color: var(--line-subtle) !important; }

        /* Academic scheduler */
        html[data-theme="light"] #academicSchedulerModal .modal-box { background: #fff !important; }
        html[data-theme="light"] #academicSchedulerModal h3 { color: var(--text-main) !important; }
        html[data-theme="light"] #academicManagementControls > div:first-child > div,
        html[data-theme="light"] #academicManagementControls > div:nth-child(2) {
            background-color: #f8fafc !important;
        }
        html[data-theme="light"] #projectAutofillBanner,
        html[data-theme="light"] #academicBatchBar,
        html[data-theme="light"] .academic-results-toolbar { background: #f5f3ff !important; }
        html[data-theme="light"] .evt-filter-btn,
        html[data-theme="light"] .academic-compact-btn,
        html[data-theme="light"] .academic-page-btn {
            background: #fff !important; border-color: rgba(15,23,42,.15) !important;
            color: #475569 !important;
        }
        html[data-theme="light"] .evt-filter-btn.active {
            background: #e0e7ff !important; border-color: #818cf8 !important; color: #4338ca !important;
        }
        html[data-theme="light"] .academic-search-box,
        html[data-theme="light"] #academicBatchSelect { background: #fff !important; color: var(--text-main) !important; border-color: rgba(15,23,42,.15) !important; }
        html[data-theme="light"] .academic-group-section { background: #fff !important; border-color: var(--line-subtle) !important; }
        html[data-theme="light"] .academic-group-toggle:hover { background: #f5f3ff !important; }
        html[data-theme="light"] .academic-group-id { color: #1d4ed8 !important; }
        html[data-theme="light"] .academic-group-events { border-color: var(--line-subtle) !important; }
        html[data-theme="light"] .academic-event-card { color: var(--text-main) !important; }
        html[data-theme="light"] .academic-event-proposal .academic-event-title { color: #4338ca !important; }
        html[data-theme="light"] .academic-event-pp1 .academic-event-title { color: #92400e !important; }
        html[data-theme="light"] .academic-event-pp2 .academic-event-title { color: #047857 !important; }
        html[data-theme="light"] .academic-event-viva .academic-event-title { color: #be185d !important; }
        html[data-theme="light"] .academic-event-status.status-scheduled { color: #047857 !important; }
        html[data-theme="light"] .academic-event-status.status-completed { color: #1d4ed8 !important; }
        html[data-theme="light"] .academic-event-status.status-unscheduled { color: #b91c1c !important; }
        html[data-theme="light"] .academic-panel-member { background: rgba(255,255,255,.72) !important; border: 1px solid rgba(15,23,42,.08); }
        html[data-theme="light"] .academic-panel-name { color: var(--text-main) !important; }
        html[data-theme="light"] .academic-panel-role { color: #4338ca !important; }
        html[data-theme="light"] .academic-summary-card { background: #fff !important; border-color: var(--line-subtle) !important; }
        html[data-theme="light"] .academic-summary-card > div:first-child { color: var(--text-main) !important; }
        html[data-theme="light"] .academic-empty-result { border-color: rgba(15,23,42,.16) !important; }
        html[data-theme="light"] #academicManagementControls [style*="color:#818cf8"],
        html[data-theme="light"] #academicSchedulerModal [style*="color:#a5b4fc"],
        html[data-theme="light"] #academicSchedulerModal [style*="color:#c4b5fd"] { color: #4338ca !important; }
        html[data-theme="light"] #academicManagementControls [style*="color:#34d399"],
        html[data-theme="light"] .academic-group-badge[style*="color:#86efac"] { color: #047857 !important; }
        html[data-theme="light"] #academicManagementControls [style*="color:#fbbf24"] { color: #92400e !important; }
        html[data-theme="light"] #academicManagementControls [style*="color:#f9a8d4"] { color: #be185d !important; }
        html[data-theme="light"] #supervisorPreview [style*="color:#e2e8f0"],
        html[data-theme="light"] #hallPreview [style*="color:#e2e8f0"] { color: var(--text-main) !important; }
        html[data-theme="light"] .academic-group-badge[style*="color:#fca5a5"] { color: #b91c1c !important; }

        /* Standalone scheduling pages */
        html[data-theme="light"] .task-item,
        html[data-theme="light"] .supervisor-box { background: var(--surface-muted) !important; }
        html[data-theme="light"] .team-title { color: var(--text-main) !important; }
        html[data-theme="light"] .team-proj,
        html[data-theme="light"] .loader { color: var(--text-muted) !important; }
        html[data-theme="light"] .member-id { color: #1d4ed8 !important; }
        html[data-theme="light"] .back-btn { background: #eaf1ff !important; color: #1d4ed8 !important; }
        html[data-theme="light"] .team-badge { color: #047857 !important; }
        html[data-theme="light"] .badge.pending { color: #475569 !important; }
        html[data-theme="light"] .badge.on-time { color: #047857 !important; }
        html[data-theme="light"] .badge.late { color: #b91c1c !important; }
        html[data-theme="light"] .member-item,
        html[data-theme="light"] h2 { border-color: var(--line-subtle) !important; }

        /* Preserve semantic foregrounds on filled controls and badges. */
        html[data-theme="light"] .primary-btn,
        html[data-theme="light"] #btnOpenAcademicScheduler,
        html[data-theme="light"] #btnExportCalendar,
        html[data-theme="light"] #btnExportExcel,
        html[data-theme="light"] .member-avatar,
        html[data-theme="light"] .task-bar,
        html[data-theme="light"] .notif-badge { color: #fff !important; }
        html[data-theme="light"] .evidence-badge.pending { color: #92400e !important; }
        html[data-theme="light"] .evidence-badge.approved { color: #047857 !important; }
        html[data-theme="light"] .evidence-badge.rejected { color: #b91c1c !important; }
        html[data-theme="light"] .review-action.approve { color: #047857 !important; }
        html[data-theme="light"] .review-action.changes { color: #92400e !important; }
        html[data-theme="light"] .review-action.reject { color: #b91c1c !important; }

        html[data-theme="light"] ::-webkit-scrollbar-track { background: #edf2f7 !important; }
        html[data-theme="light"] ::-webkit-scrollbar-thumb { background: #bdc8d6 !important; }
        html[data-theme="light"] ::-webkit-scrollbar-thumb:hover { background: #94a3b8 !important; }
    `;

    /* ── 2. Style element reference ─────────────────────────────────────────── */
    let _styleEl = null;

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        if (theme === 'light') {
            if (!_styleEl) {
                _styleEl = document.createElement('style');
                _styleEl.id = 'ipms-light-override';
                _styleEl.textContent = LIGHT_CSS;
                /* Append to <head> — always AFTER all static <style> blocks */
                document.head.appendChild(_styleEl);
            }
        } else {
            if (_styleEl) { _styleEl.remove(); _styleEl = null; }
        }
    }

    /* ── 3. Apply saved theme immediately (prevents dark flash on light mode) ─ */
    const saved = localStorage.getItem('ipms-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);

    /* ── 4. After DOM ready: inject CSS + create button ────────────────────── */
    document.addEventListener('DOMContentLoaded', function () {
        /* Apply theme CSS (injected after all inline <style> tags → always wins) */
        applyTheme(saved);

        /* Build button with 100% inline styles — page CSS cannot touch these */
        const btn = document.createElement('button');
        btn.id = 'ipmsThemeToggle';
        btn.setAttribute('aria-label', 'Toggle light/dark mode');

        /* ── Use setProperty with 'important' so stylesheet rules (e.g. button { width:100% })
           cannot override our button's layout. This is the ONLY way to guarantee
           these values beat any external/internal stylesheet !important rule. ── */
        const setI = (prop, val) => btn.style.setProperty(prop, val, 'important');

        setI('position',        'fixed');
        setI('bottom',          '24px');
        setI('right',           '24px');
        setI('top',             'auto');
        setI('left',            'auto');
        setI('width',           'auto');
        setI('min-height',      'auto');
        setI('height',          'auto');
        setI('margin',          '0');
        setI('margin-top',      '0');
        setI('z-index',         '2147483647');
        setI('display',         'flex');
        setI('align-items',     'center');
        setI('gap',             '7px');
        setI('padding',         '9px 18px');
        setI('border-radius',   '999px');
        setI('font-family',     "'Inter', system-ui, sans-serif");
        setI('font-size',       '0.82rem');
        setI('font-weight',     '600');
        setI('cursor',          'pointer');
        setI('transition',      'background 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease');
        setI('box-shadow',      '0 4px 20px rgba(0,0,0,0.35)');
        setI('backdrop-filter', 'blur(12px)');
        setI('letter-spacing',  '0.02em');
        setI('outline',         'none');
        setI('user-select',     'none');
        setI('white-space',     'nowrap');
        setI('text-transform',  'none');

        // Keep the theme control clear of the scheduler's academic-action
        // button instead of stacking both controls in the same corner.
        if (document.getElementById('btnOpenAcademicScheduler')) {
            setI('bottom', '88px');
        }

        function updateBtn(theme) {
            if (theme === 'dark') {
                btn.innerHTML = '&#9728;&#65039; Light Mode';
                setI('background', 'rgba(255,255,255,0.12)');
                setI('color',      '#f8fafc');
                setI('border',     '1px solid rgba(255,255,255,0.2)');
            } else {
                btn.innerHTML = '&#127769; Dark Mode';
                setI('background', 'rgba(15,23,42,0.88)');
                setI('color',      '#f8fafc');
                setI('border',     '1px solid rgba(0,0,0,0.2)');
            }
        }

        updateBtn(saved);
        document.body.appendChild(btn);

        btn.addEventListener('click', function () {
            const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            localStorage.setItem('ipms-theme', next);
            applyTheme(next);
            updateBtn(next);
        });

        /* Hover effects via pointer events */
        btn.addEventListener('mouseenter', function () {
            btn.style.transform  = 'translateY(-2px)';
            btn.style.boxShadow  = '0 8px 28px rgba(0,0,0,0.4)';
        });
        btn.addEventListener('mouseleave', function () {
            btn.style.transform  = '';
            btn.style.boxShadow  = '0 4px 20px rgba(0,0,0,0.35)';
        });
    });

})();
