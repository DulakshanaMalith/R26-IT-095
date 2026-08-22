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
        /* === BODY === */
        body, html {
            background: #f0f4f8 !important;
            background-image: none !important;
            background-attachment: unset !important;
            color: #1e293b !important;
        }

        /* === ALL CARDS / PANELS === */
        .panel, .card, .glass-card, .metric-card, .upload-area,
        .schedule-output, .stat-card, .modal-content, .ms-panel,
        .result-summary > div, .gantt-row, .assign-row,
        .notif-panel, .member-card, .app-shell, .app-main,
        .form-section, .output-section, .sample-section,
        .progress-card, .wbs-section, .team-section {
            background: #ffffff !important;
            background-color: #ffffff !important;
            border-color: rgba(0, 0, 0, 0.1) !important;
            color: #1e293b !important;
            box-shadow: 0 2px 16px rgba(0, 0, 0, 0.08) !important;
        }

        /* === RISK APP SPECIFIC PANELS === */
        .panel, .result-summary > div {
            background: rgba(255, 255, 255, 0.95) !important;
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
        }

        /* === NAVIGATION / TOP BAR === */
        .top-bar, nav, .navbar, .app-header, header.app-header {
            background: rgba(255, 255, 255, 0.95) !important;
            border-bottom: 1px solid rgba(0, 0, 0, 0.1) !important;
            backdrop-filter: blur(10px) !important;
        }

        /* === ALL TEXT === */
        h1, h2, h3, h4, h5, h6, strong, b {
            color: #1e293b !important;
            -webkit-text-fill-color: unset !important;
        }
        p, span, label, li, td, th, div,
        .summary-label, .metric-card span, .metric-card strong {
            color: #1e293b !important;
        }

        /* Keep gradient title on index header */
        header h1 {
            background: linear-gradient(to right, #2563eb, #7c3aed) !important;
            -webkit-background-clip: text !important;
            -webkit-text-fill-color: transparent !important;
            background-clip: text !important;
        }

        /* Muted text */
        .task-meta, .stat-label, .notif-time, .timeline-mark,
        .shap-explanation, .summary-label, .text-muted {
            color: #64748b !important;
        }

        /* === INPUTS === */
        input, select, textarea {
            background: #f8fafc !important;
            background-color: #f8fafc !important;
            border: 1px solid rgba(0, 0, 0, 0.15) !important;
            color: #1e293b !important;
        }
        input::placeholder, textarea::placeholder {
            color: #94a3b8 !important;
        }
        input:focus, select:focus, textarea:focus {
            border-color: #2563eb !important;
            box-shadow: 0 0 0 3px rgba(37,99,235,0.15) !important;
        }

        /* === SAMPLE BUTTONS (risk page) === */
        .sample-button {
            background: rgba(0, 0, 0, 0.04) !important;
            border: 1px solid rgba(0, 0, 0, 0.12) !important;
            color: #475569 !important;
        }
        .sample-button.active {
            border-width: 2px !important;
            color: #1e293b !important;
        }

        /* === GANTT === */
        .task-track  { background: #e2e8f0 !important; }
        .task-name   { color: #1e293b !important; }
        .gantt-timeline-header { border-color: rgba(0,0,0,0.08) !important; }

        /* === MULTI-SELECT === */
        .ms-display {
            background: #f8fafc !important;
            border-color: rgba(0,0,0,0.12) !important;
            color: #1e293b !important;
        }
        .ms-option      { color: #1e293b !important; }
        .ms-option:hover { background: rgba(37,99,235,0.06) !important; }

        /* === PROGRESS BAR TRACK === */
        .progress-track { background: #e2e8f0 !important; }

        /* === INDEX PAGE CARDS === */
        .card:hover {
            box-shadow: 0 10px 30px rgba(37,99,235,0.15) !important;
            border-color: rgba(37,99,235,0.4) !important;
        }
        p.subtitle { color: #64748b !important; }

        /* === SCROLLBAR === */
        ::-webkit-scrollbar-track  { background: #f1f5f9 !important; }
        ::-webkit-scrollbar-thumb  { background: #cbd5e1 !important; }
        ::-webkit-scrollbar-thumb:hover { background: #94a3b8 !important; }
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
