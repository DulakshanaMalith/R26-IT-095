// ============================================================
// IPMS ADAPTIVE SCHEDULING — Frontend Script
// ============================================================
// FILE STRUCTURE (use Ctrl+G to jump to any line):
//
//   Line   1  — DOMContentLoaded wrapper (all main UI logic lives here)
//   Line  16  — PDF Upload Handler → API: POST /api/schedule/upload-pdf
//   Line  49  — Generate Schedule Form Submit → API: POST /api/schedule/generate
//   Line  96  — renderResults()  — draws KPI cards + calls renderGantt()
//   Line 119  — renderGantt()    — draws the Gantt chart bars
//   Line 238  — openTaskProgressPopup() → API: GET /api/progress/individual
//   Line 365  — NOVELTY 10: What-If Monte Carlo → API: POST /api/simulate
//   Line 398  — NOVELTY 8:  Pareto/NSGA-II     → API: POST /api/schedule/pareto
//   Line 447  — GitHub Connect Modal → API: GET/POST /api/github/*
//   Line 489  — Notifications → API: GET /api/notifications
//   Line 523  — Milestone Submit → API: POST /api/milestone/submit
//   Line 582  — NOVELTY 12: initProgressTracker()
//   Line 645  — createMultiSelect()  — multi-member assignment dropdown
//   Line 782  — renderAssignmentTable() — draws the task assignment board
//   Line 861  — NOVELTY 12: Auto-Assign → API: POST /api/progress/auto-assign
//   Line 927  — Apply IT Number Names button
//   Line 964  — loadProgressCards() → API: GET /api/progress/individual
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    // Set default start date to today
    document.getElementById('startDate').valueAsDate = new Date();

    const form = document.getElementById('scheduleForm');
    const generateBtn = document.getElementById('generateBtn');
    const btnText = generateBtn.querySelector('span');
    const btnLoader = document.getElementById('btnLoader');
    
    const emptyState = document.getElementById('emptyState');
    const resultsContainer = document.getElementById('resultsContainer');
    const ganttContainer = document.getElementById('ganttContainer');
    const pdfUpload = document.getElementById('pdfUpload');
    const descriptionBox = document.getElementById('description');

    // ============================================================
    // SECTION 1: PDF UPLOAD HANDLER
    // ─────────────────────────────────────────────────────────────
    // API: POST /api/schedule/upload-pdf
    // When the user selects a PDF, this sends it to the backend.
    // Backend uses pdfplumber to extract text, then regex IT\d{8}
    // to find team member IT numbers.
    // Response: { extracted_text: "...", it_numbers: [...] }
    // ============================================================
    pdfUpload.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        // Hide any previous error
        const errorPanel  = document.getElementById('pdfErrorPanel');
        const errorType   = document.getElementById('pdfErrorType');
        const errorDetail = document.getElementById('pdfErrorDetail');
        if (errorPanel) errorPanel.style.display = 'none';

        try {
            descriptionBox.value = "⏳ Reading PDF... please wait.";
            const response = await fetch('/api/schedule/upload-pdf', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                descriptionBox.value = "";
                const rawMsg = data.detail || "Unknown error occurred.";

                // Parse the error into type line + detail lines
                const lines      = rawMsg.split('\n').map(l => l.trim()).filter(Boolean);
                const firstLine  = lines[0] || rawMsg;
                const restLines  = lines.slice(1).join('\n');

                // Extract "Detected document type: X" if present
                const typeMatch  = rawMsg.match(/Detected document type:\s*(.+)/i)
                               || rawMsg.match(/document type[:\s]+(.+)/i);
                const detectedType = typeMatch
                    ? `📄 Detected as: ${typeMatch[1].trim()}`
                    : `📄 ${firstLine}`;

                if (errorPanel && errorType && errorDetail) {
                    errorType.textContent   = detectedType;
                    errorDetail.textContent = restLines || firstLine;
                    errorPanel.style.display = 'block';
                    errorPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
                return;
            }

            // ✅ Success — hide error panel, fill textarea
            if (errorPanel) errorPanel.style.display = 'none';
            descriptionBox.value = data.extracted_text;

            // Brief success flash on the upload button
            const uploadLabel = document.querySelector('label[for="pdfUpload"]');
            if (uploadLabel) {
                const orig = uploadLabel.innerHTML;
                uploadLabel.innerHTML = '<i class="fa-solid fa-circle-check"></i> PDF Loaded ✓';
                uploadLabel.style.color = '#34d399';
                setTimeout(() => {
                    uploadLabel.innerHTML = orig;
                    uploadLabel.style.color = '';
                }, 2500);
            }

        } catch (error) {
            console.error(error);
            descriptionBox.value = "";
            if (errorPanel && errorType && errorDetail) {
                errorType.textContent   = "⚠️ Network Error";
                errorDetail.textContent = "Could not reach the backend server.\nMake sure the server is running on port 8000.";
                errorPanel.style.display = 'block';
            }
        }
        pdfUpload.value = ''; // Reset input so same file can be re-uploaded
    });

    // ============================================================
    // SECTION 2: GENERATE SCHEDULE — MAIN FORM SUBMIT ⭐
    // ─────────────────────────────────────────────────────────────
    // API: POST /api/schedule/generate
    // Payload: { description, team_size, duration_months,
    //            function_points, start_date }
    // Backend pipeline:
    //   1. Extract WBS tasks (5 strategies: regex → verb → T5)
    //   2. Estimate effort with XGBoost (Model 2)
    //   3. Predict delay risk with Logistic Regression (Model 3)
    //   4. Scale durations proportionally across total project days
    // Response: { schedule: [...tasks], total_tasks, total_effort_hours,
    //             total_duration_days, team_members: [IT numbers] }
    // ============================================================
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const description = document.getElementById('description').value.trim();
        if (!description) {
            alert('Please paste a project proposal description.');
            return;
        }

        // UI Loading State
        btnText.classList.add('hidden');
        btnLoader.classList.remove('hidden');
        generateBtn.disabled = true;

        // Build the request payload — these fields are validated by
        // Pydantic's ProjectRequest model on the backend (main.py)
        const payload = {
            description: description,                                            // Raw proposal text
            team_size: parseInt(document.getElementById('teamSize').value),      // Number of developers
            duration_months: parseFloat(document.getElementById('duration').value), // Project length
            function_points: parseInt(document.getElementById('complexity').value),  // Complexity score (FP)
            start_date: document.getElementById('startDate').value               // Gantt start date
        };

        try {
            const response = await fetch('/api/schedule/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`API Error: ${response.statusText}`);
            }

            const data = await response.json();
            renderResults(data);

        } catch (error) {
            console.error(error);
            alert('Failed to generate schedule. Make sure the FastAPI backend is running on port 8000.\n\nError: ' + error.message);
        } finally {
            // Restore UI
            btnText.classList.remove('hidden');
            btnLoader.classList.add('hidden');
            generateBtn.disabled = false;
        }
    });

    // ============================================================
    // SECTION 3: RENDER RESULTS
    // ─────────────────────────────────────────────────────────────
    // Called after a successful /api/schedule/generate response.
    // Updates the 4 KPI cards (Tasks, Effort, Days, High-Risk count)
    // then calls renderGantt() to draw the chart and
    // initProgressTracker() to set up Novelty 12.
    // ============================================================
    function renderResults(data) {
        // Update KPI summary cards at the top of the results panel
        document.getElementById('kpiTasks').textContent = data.total_tasks;
        document.getElementById('kpiEffort').textContent = `${data.total_effort_hours} hrs`;
        document.getElementById('kpiDays').textContent = data.total_duration_days;
        
        const highRiskCount = data.schedule.filter(t => t.delay_risk_pct >= 50).length;
        const riskEl = document.getElementById('kpiRisk');
        riskEl.textContent = highRiskCount;
        riskEl.style.color = highRiskCount > 0 ? 'var(--danger)' : 'var(--success)';

        // Switch Views
        emptyState.classList.add('hidden');
        resultsContainer.classList.remove('hidden');

        // Render Gantt
        renderGantt(data.schedule, data.total_duration_days);

        // NOVELTY 12: Initialize the progress tracker with this schedule's tasks
        // Pass real team member names extracted by the backend from the PDF
        initProgressTracker(data.schedule, data.team_size, data.team_members || []);
    }

    // ============================================================
    // SECTION 4: JIRA-STYLE GANTT CHART RENDERER  ⭐
    // ─────────────────────────────────────────────────────────────
    // Draws a professional Jira-like Gantt with:
    //   • Month labels (M1, M2 ... M10) on the timeline ruler
    //   • Swim lanes grouped per team member
    //   • Color-coded bars per member (blue, purple, green, orange)
    //   • "All Members" lane for shared tasks
    //   • Risk badges (ON TRACK / HIGH RISK / OVERDUE)
    //   • Animated bar entry on load
    // ============================================================
    function renderGantt(schedule, totalDays) {
        ganttContainer.innerHTML = '';

        // Member color palette (Jira-like)
        const MEMBER_COLORS = [
            { bar: 'linear-gradient(90deg,#3b82f6,#2563eb)', avatar: '#3b82f6', label: '#93c5fd' },
            { bar: 'linear-gradient(90deg,#8b5cf6,#7c3aed)', avatar: '#8b5cf6', label: '#c4b5fd' },
            { bar: 'linear-gradient(90deg,#10b981,#059669)', avatar: '#10b981', label: '#6ee7b7' },
            { bar: 'linear-gradient(90deg,#f59e0b,#d97706)', avatar: '#f59e0b', label: '#fcd34d' },
            { bar: 'linear-gradient(90deg,#ec4899,#db2777)', avatar: '#ec4899', label: '#f9a8d4' },
            { bar: 'linear-gradient(90deg,#14b8a6,#0d9488)', avatar: '#14b8a6', label: '#5eead4' },
        ];
        const SHARED_COLOR = { bar: 'linear-gradient(90deg,#475569,#334155)', avatar: '#64748b', label: '#94a3b8' };
        const RISK_COLOR   = { bar: 'linear-gradient(90deg,#ef4444,#b91c1c)', shadow: 'rgba(239,68,68,0.45)' };
        const WARN_COLOR   = { bar: 'linear-gradient(90deg,#f59e0b,#b45309)', shadow: 'rgba(245,158,11,0.35)' };

        // ── Collect unique members ─────────────────────────────────────────────
        // Pull member list from the progress tracker state (populated by initProgressTracker)
        const memberSet = [];
        schedule.forEach(t => {
            const owner = t.component_owner || t.assigned_to || null;
            if (owner && owner !== 'all' && !memberSet.includes(owner)) memberSet.push(owner);
        });

        // ── Calculate project date range ───────────────────────────────────────
        let projStart = null, projEnd = null;
        schedule.forEach(t => {
            const s = new Date(t.start_date), e = new Date(t.end_date);
            if (!projStart || s < projStart) projStart = s;
            if (!projEnd   || e > projEnd)   projEnd   = e;
        });
        if (!projStart) projStart = new Date();
        if (!projEnd)   projEnd   = new Date(projStart.getTime() + totalDays * 86400000);
        const projTotalMs = projEnd - projStart || 1;

        // Number of months on the timeline
        const numMonths = Math.max(1, Math.ceil(projTotalMs / (30 * 86400000)));

        // Helper: convert date → left% on the timeline
        const dateToPct = d => Math.max(0, Math.min(100, ((new Date(d) - projStart) / projTotalMs) * 100));
        const daysToPct = days => Math.max(0.5, (days / (projTotalMs / 86400000)) * 100);

        // ── TODAY marker position ─────────────────────────────────────────────
        const todayPct = dateToPct(new Date());

        // ── Month header ruler ─────────────────────────────────────────────────
        const ruler = document.createElement('div');
        ruler.style.cssText = `
            display:flex; position:relative; height:36px; margin-bottom:2px;
            border-bottom:1px solid rgba(255,255,255,0.08);
        `;

        // Left label column
        const rulerLabel = document.createElement('div');
        rulerLabel.style.cssText = 'width:220px;min-width:220px;font-size:0.7rem;color:#64748b;display:flex;align-items:center;padding-left:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;';
        rulerLabel.textContent = 'Task / Assignee';
        ruler.appendChild(rulerLabel);

        // Month tick marks
        const rulerTrack = document.createElement('div');
        rulerTrack.style.cssText = 'flex:1;position:relative;';

        // Today line
        const todayLine = document.createElement('div');
        todayLine.style.cssText = `position:absolute;top:0;bottom:0;left:${todayPct}%;width:2px;background:rgba(251,191,36,0.5);z-index:5;pointer-events:none;`;
        const todayLbl = document.createElement('div');
        todayLbl.style.cssText = `position:absolute;top:2px;left:${todayPct}%;transform:translateX(-50%);font-size:0.6rem;color:#fbbf24;font-weight:700;white-space:nowrap;z-index:6;`;
        todayLbl.textContent = 'TODAY';
        rulerTrack.appendChild(todayLine);
        rulerTrack.appendChild(todayLbl);

        for (let m = 0; m <= numMonths; m++) {
            const pct = (m / numMonths) * 100;
            const tick = document.createElement('div');
            tick.style.cssText = `position:absolute;left:${pct}%;top:0;height:100%;display:flex;flex-direction:column;align-items:flex-start;`;
            const line = document.createElement('div');
            line.style.cssText = 'width:1px;height:100%;background:rgba(255,255,255,0.07);';
            const lbl = document.createElement('span');
            lbl.style.cssText = 'font-size:0.68rem;color:#64748b;font-weight:600;padding-left:4px;margin-top:6px;white-space:nowrap;';
            lbl.textContent = m === 0 ? 'Start' : `M${m}`;
            tick.appendChild(line);
            tick.appendChild(lbl);
            rulerTrack.appendChild(tick);
        }
        ruler.appendChild(rulerTrack);
        ganttContainer.appendChild(ruler);

        // ── Helper to render one task row ──────────────────────────────────────
        function renderTaskRow(task, colorScheme, index, laneIndex) {
            const row = document.createElement('div');
            row.style.cssText = `
                display:flex; align-items:center; min-height:52px;
                border-bottom:1px solid rgba(255,255,255,0.04);
                transition:background 0.2s;
            `;
            row.addEventListener('mouseenter', () => row.style.background = 'rgba(255,255,255,0.025)');
            row.addEventListener('mouseleave', () => row.style.background = '');

            // ── Left: task info ──────────────────────────────────────────────
            const info = document.createElement('div');
            info.style.cssText = 'width:220px;min-width:220px;padding:8px 12px;';

            const taskName = document.createElement('div');
            taskName.style.cssText = 'font-size:0.8rem;font-weight:600;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px;cursor:pointer;';
            taskName.textContent = task.task_name;
            taskName.title = task.task_name;
            taskName.addEventListener('click', () => openTaskProgressPopup(task));

            const taskMeta = document.createElement('div');
            taskMeta.style.cssText = 'font-size:0.68rem;color:#64748b;margin-top:2px;';
            taskMeta.textContent = `${task.effort_hours}h · ${task.duration_days}d`;

            info.appendChild(taskName);
            info.appendChild(taskMeta);
            row.appendChild(info);

            // ── Right: Gantt track ───────────────────────────────────────────
            const track = document.createElement('div');
            track.style.cssText = 'flex:1;position:relative;height:52px;';

            // Today vertical line (extends through all rows)
            const tLine = document.createElement('div');
            tLine.style.cssText = `position:absolute;left:${todayPct}%;top:0;bottom:0;width:2px;background:rgba(251,191,36,0.25);z-index:2;pointer-events:none;`;
            track.appendChild(tLine);

            // Determine bar color based on risk
            const today = new Date(); today.setHours(0,0,0,0);
            const endDate = new Date(task.end_date); endDate.setHours(0,0,0,0);
            const isOverdue = !task.status?.includes('COMPLETED') && today > endDate;
            const isHighRisk = task.delay_risk_pct >= 50 && !isOverdue;

            let barBg = colorScheme.bar;
            let barShadow = `0 2px 8px ${colorScheme.avatar}55`;
            if (isOverdue)    { barBg = RISK_COLOR.bar;  barShadow = `0 2px 12px ${RISK_COLOR.shadow}`; }
            else if (isHighRisk) { barBg = WARN_COLOR.bar; barShadow = `0 2px 10px ${WARN_COLOR.shadow}`; }

            const leftPct  = dateToPct(task.start_date);
            const widthPct = daysToPct(task.duration_days);

            const bar = document.createElement('div');
            bar.style.cssText = `
                position:absolute; top:50%; transform:translateY(-50%);
                left:${leftPct}%; width:0%; height:28px;
                background:${barBg}; border-radius:6px;
                display:flex; align-items:center; padding:0 10px;
                font-size:0.7rem; font-weight:700; color:#fff;
                white-space:nowrap; overflow:hidden;
                box-shadow:${barShadow};
                cursor:pointer; transition:left 0.3s ease, width 0.5s ease, box-shadow 0.2s;
                z-index:3;
            `;
            bar.title = `${task.task_name} — ${task.duration_days}d`;
            bar.addEventListener('click', () => openTaskProgressPopup(task));
            bar.addEventListener('mouseenter', () => bar.style.filter = 'brightness(1.15)');
            bar.addEventListener('mouseleave', () => bar.style.filter = '');

            // Badge inside bar
            const badge = document.createElement('span');
            badge.textContent = isOverdue ? 'OVERDUE' : isHighRisk ? `${task.delay_risk_pct}% risk` : `${task.duration_days}d`;
            bar.appendChild(badge);

            // Risk icon badge (right side of bar)
            if (isOverdue || isHighRisk) {
                const riskIcon = document.createElement('div');
                riskIcon.style.cssText = `
                    position:absolute; right:-6px; top:50%; transform:translateY(-50%);
                    width:18px; height:18px; border-radius:50%;
                    background:${isOverdue ? '#dc2626' : '#f59e0b'};
                    display:flex; align-items:center; justify-content:center;
                    font-size:0.6rem; color:#fff; z-index:4; box-shadow:0 0 6px ${isOverdue ? '#dc262688' : '#f59e0b88'};
                `;
                riskIcon.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
                bar.appendChild(riskIcon);
            }

            track.appendChild(bar);
            row.appendChild(track);
            ganttContainer.appendChild(row);

            // Animate bar width after DOM insert
            setTimeout(() => { bar.style.width = `${widthPct}%`; }, 60 * index);
        }

        // ── Render swim lane header ────────────────────────────────────────────
        function renderLaneHeader(label, colorScheme, taskCount) {
            const lane = document.createElement('div');
            lane.style.cssText = `
                display:flex; align-items:center; height:36px;
                background:rgba(255,255,255,0.03);
                border-top:1px solid rgba(255,255,255,0.06);
                border-bottom:1px solid rgba(255,255,255,0.04);
                padding:0 12px; gap:8px;
            `;
            const dot = document.createElement('div');
            dot.style.cssText = `width:10px;height:10px;border-radius:50%;background:${colorScheme.avatar};flex-shrink:0;`;
            const name = document.createElement('span');
            name.style.cssText = `font-size:0.75rem;font-weight:700;color:${colorScheme.label};`;
            name.textContent = label;
            const count = document.createElement('span');
            count.style.cssText = 'font-size:0.65rem;color:#64748b;margin-left:auto;';
            count.textContent = `${taskCount} task${taskCount !== 1 ? 's' : ''}`;
            lane.appendChild(dot);
            lane.appendChild(name);
            lane.appendChild(count);
            ganttContainer.appendChild(lane);
        }

        // ── Split tasks into shared and per-member ─────────────────────────────
        const sharedTasks = schedule.filter(t => !t.component_owner || t.component_owner === 'all');
        const memberTasks = {};
        memberSet.forEach(m => { memberTasks[m] = []; });
        schedule.forEach(t => {
            const owner = t.component_owner;
            if (owner && owner !== 'all' && memberTasks[owner]) {
                memberTasks[owner].push(t);
            }
        });

        // If no per-member tasks exist (no component_owner data), show all tasks flat
        const hasPerMember = memberSet.length > 0;

        let rowIdx = 0;

        if (hasPerMember) {
            // ── All Members lane ──────────────────────────────────────────────
            if (sharedTasks.length > 0) {
                renderLaneHeader('All Members — Shared Tasks', SHARED_COLOR, sharedTasks.length);
                sharedTasks.forEach((t, i) => renderTaskRow(t, SHARED_COLOR, rowIdx++, -1));
            }

            // ── Per-member lanes ──────────────────────────────────────────────
            memberSet.forEach((member, mi) => {
                const color = MEMBER_COLORS[mi % MEMBER_COLORS.length];
                const tasks = memberTasks[member] || [];
                const shortName = member.length > 12 ? member.substring(0, 12) + '…' : member;
                renderLaneHeader(shortName, color, tasks.length);
                if (tasks.length === 0) {
                    const empty = document.createElement('div');
                    empty.style.cssText = 'padding:10px 12px 10px 220px;font-size:0.75rem;color:#475569;border-bottom:1px solid rgba(255,255,255,0.04);';
                    empty.textContent = 'No individual tasks assigned yet.';
                    ganttContainer.appendChild(empty);
                } else {
                    tasks.forEach((t, i) => renderTaskRow(t, color, rowIdx++, mi));
                }
            });
        } else {
            // Flat list (no component detection)
            schedule.forEach((t, i) => {
                const color = MEMBER_COLORS[i % MEMBER_COLORS.length];
                renderTaskRow(t, color, rowIdx++, 0);
            });
        }
    }


    // ============================================================
    // Task Progress Popup (click on Gantt bar day badge)
    // ============================================================
    // ============================================================
    // SECTION 5: TASK PROGRESS POPUP
    // ─────────────────────────────────────────────────────────────
    // Triggered when user clicks any Gantt bar.
    // API: GET /api/progress/individual
    // Shows: task duration, effort hours, delay risk label,
    //        start/end dates, assigned member with progress %,
    //        bottleneck warning if member progress < 50%,
    //        and a mini summary of all team members.
    // ============================================================
    async function openTaskProgressPopup(task) {
        const modal = document.getElementById('taskProgressModal');
        if (!modal) return;

        // Show loading state
        modal.classList.remove('hidden');
        document.getElementById('tpModalTitle').textContent = task.task_name;
        document.getElementById('tpModalBody').innerHTML = `
            <div style="text-align:center;padding:2rem;color:var(--text-muted);">
                <i class="fa-solid fa-spinner fa-spin fa-2x"></i>
                <p style="margin-top:1rem;">Loading progress data...</p>
            </div>`;

        try {
            const res = await fetch('/api/progress/individual');
            const data = await res.json();

            // ── Dynamic Risk Calculator ───────────────────────────────────────
            // The ML model gives a STATIC prediction at generation time.
            // Here we OVERRIDE it with live date + progress awareness so that:
            //   • Overdue tasks (deadline passed, not done) → OVERDUE 🔴
            //   • Deadline is today/tomorrow with <80% progress → HIGH RISK 🔴
            //   • Behind expected pace (progress < days elapsed %) → HIGH RISK 🔴
            //   • Otherwise use the ML model's prediction
            // ────────────────────────────────────────────────────────────────────
            const today       = new Date(); today.setHours(0,0,0,0);
            const startDate   = new Date(task.start_date); startDate.setHours(0,0,0,0);
            const endDate     = new Date(task.end_date);   endDate.setHours(0,0,0,0);
            const isCompleted = task.status === 'COMPLETED';

            // Find this task's assigned member progress (from API response)
            let memberProgress = 0;
            for (const m of (data.members || [])) {
                const found = m.tasks.find(t => t.task_id === task.task_id);
                if (found) { memberProgress = m.progress_pct; break; }
            }

            // Days elapsed vs total task days (expected progress %)
            const totalTaskDays   = Math.max(1, (endDate - startDate) / 86400000);
            const elapsedDays     = Math.max(0, (today   - startDate) / 86400000);
            const expectedProgress = Math.min(100, (elapsedDays / totalTaskDays) * 100);
            const daysUntilEnd    = Math.ceil((endDate - today) / 86400000);

            let riskColor, riskLabel;

            if (isCompleted) {
                // Task already done — always safe
                riskColor = '#10b981'; riskLabel = '✅ COMPLETED';
            } else if (today > endDate) {
                // Deadline has PASSED and task is not done → OVERDUE
                const daysLate = Math.abs(daysUntilEnd);
                riskColor = '#dc2626'; riskLabel = `🚨 OVERDUE (${daysLate}d late)`;
            } else if (daysUntilEnd <= 1 && memberProgress < 80) {
                // Deadline is TODAY or TOMORROW and progress is low
                riskColor = '#ef4444'; riskLabel = `⚠️ HIGH RISK (due ${daysUntilEnd === 0 ? 'today' : 'tomorrow'})`;
            } else if (elapsedDays > 0 && memberProgress < (expectedProgress - 20)) {
                // Significantly behind expected pace (>20% behind schedule)
                riskColor = '#ef4444'; riskLabel = `⚠️ HIGH RISK (${Math.round(expectedProgress - memberProgress)}% behind pace)`;
            } else if (task.delay_risk_pct >= 50) {
                // ML model flags it as high risk
                riskColor = '#f59e0b'; riskLabel = `⚠️ AT RISK (${task.delay_risk_pct}% risk score)`;
            } else {
                // All checks pass — genuinely on track
                riskColor = '#10b981'; riskLabel = '✅ ON TRACK';
            }

            const taskStatus = isCompleted ? '✓ Completed' : 'In Progress';


            // Find which member is assigned to this task
            let assignedMember = null;
            for (const member of (data.members || [])) {
                const found = member.tasks.find(t => t.task_id === task.task_id);
                if (found) { assignedMember = { member, taskEntry: found }; break; }
            }

            // Build assigned member card
            const assignedHtml = assignedMember ? (() => {
                const m = assignedMember.member;
                const pct = m.progress_pct;
                const barColor = pct >= 75 ? '#10b981' : pct >= 40 ? '#3b82f6' : '#f59e0b';
                const initials = m.member.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
                return `
                <div class="tp-assigned-card">
                    <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.75rem;">
                        <div class="member-avatar" style="width:40px;height:40px;font-size:1rem;">${initials}</div>
                        <div>
                            <div style="font-weight:700;font-size:0.95rem;">${m.member}</div>
                            <div style="font-size:0.75rem;color:var(--text-muted);">${m.completed_tasks}/${m.total_tasks} tasks done • ${m.completed_effort_hours}/${m.total_effort_hours} hrs</div>
                        </div>
                        <span style="margin-left:auto;font-size:1.2rem;font-weight:800;color:${barColor};">${pct}%</span>
                    </div>
                    <div style="background:rgba(255,255,255,0.08);border-radius:8px;height:10px;overflow:hidden;">
                        <div style="height:100%;width:${pct}%;background:${barColor};border-radius:8px;transition:width 0.8s ease;"></div>
                    </div>
                    ${m.is_bottleneck ? `<div style="margin-top:0.6rem;color:#f59e0b;font-size:0.78rem;"><i class="fa-solid fa-triangle-exclamation"></i> Bottleneck detected — behind schedule</div>` : ''}
                </div>`;
            })() : `<div style="color:var(--text-muted);font-size:0.85rem;padding:1rem;background:rgba(255,255,255,0.04);border-radius:8px;">
                <i class="fa-solid fa-user-slash"></i> No member assigned to this task yet.<br>
                <span style="font-size:0.78rem;">Use the Task Assignment Board below to assign someone.</span>
            </div>`;

            // Build all-members summary (mini cards)
            const allMembersHtml = (data.members && data.members.length > 0) ? `
            <div style="margin-top:1.25rem;">
                <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);margin-bottom:0.6rem;">All Members Overview</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;">
                ${data.members.map(m => {
                    const pct = m.progress_pct;
                    const bc = pct >= 75 ? '#10b981' : pct >= 40 ? '#3b82f6' : '#f59e0b';
                    const initials = m.member.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
                    return `<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:0.6rem;">
                        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.4rem;">
                            <div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,${bc},${bc}88);display:flex;align-items:center;justify-content:center;font-size:0.65rem;font-weight:700;color:#fff;">${initials}</div>
                            <div style="flex:1;min-width:0;">
                                <div style="font-size:0.78rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${m.member}</div>
                                <div style="font-size:0.68rem;color:var(--text-muted);">${m.total_tasks} tasks</div>
                            </div>
                            <span style="font-size:0.82rem;font-weight:700;color:${bc};">${pct}%</span>
                        </div>
                        <div style="background:rgba(255,255,255,0.08);border-radius:4px;height:5px;overflow:hidden;">
                            <div style="height:100%;width:${pct}%;background:${bc};border-radius:4px;"></div>
                        </div>
                    </div>`;
                }).join('')}
                </div>
            </div>` : '';

                document.getElementById('tpModalBody').innerHTML = `
                <!-- Task Header Info -->
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.75rem;margin-bottom:1.25rem;">
                    <div class="tp-stat-box">
                        <span class="tp-stat-label">Duration</span>
                        <span class="tp-stat-val">${task.duration_days} days</span>
                    </div>
                    <div class="tp-stat-box">
                        <span class="tp-stat-label">Effort</span>
                        <span class="tp-stat-val">${task.effort_hours} hrs</span>
                    </div>
                    <div class="tp-stat-box">
                        <span class="tp-stat-label">Risk</span>
                        <span class="tp-stat-val" style="color:${riskColor};font-size:0.78rem;">${riskLabel}</span>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-bottom:1.25rem;">
                    <div class="tp-stat-box"><span class="tp-stat-label">Start Date</span><span class="tp-stat-val" style="font-size:0.82rem;">${task.start_date}</span></div>
                    <div class="tp-stat-box"><span class="tp-stat-label">End Date</span><span class="tp-stat-val" style="font-size:0.82rem;">${task.end_date}</span></div>
                </div>

                <!-- SHAP Explainability Panel -->
                ${(task.shap_factors && task.shap_factors.length > 0) ? `
                <div style="margin-bottom:1.25rem;background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:12px;padding:1rem;">
                    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#818cf8;margin-bottom:0.75rem;">
                        <i class="fa-solid fa-brain"></i> AI Risk Explanation (SHAP)
                    </div>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:0.75rem;">
                        Top factors driving the <strong style="color:${riskColor};">${task.delay_risk_pct}% risk score</strong>:
                    </div>
                    ${task.shap_factors.map((f, idx) => {
                        const absVal = Math.abs(f.shap_value);
                        const maxVal = Math.abs(task.shap_factors[0].shap_value) || 1;
                        const barPct = Math.round((absVal / maxVal) * 100);
                        const barColor = f.shap_value > 0 ? '#ef4444' : '#10b981';
                        const icon = f.shap_value > 0 ? '▲' : '▼';
                        return `
                        <div style="margin-bottom:0.6rem;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.25rem;">
                                <span style="font-size:0.8rem;font-weight:600;color:#e2e8f0;">${icon} ${f.label}</span>
                                <span style="font-size:0.72rem;color:${barColor};font-weight:700;">${f.shap_value > 0 ? '+' : ''}${f.shap_value.toFixed(3)}</span>
                            </div>
                            <div style="background:rgba(255,255,255,0.06);border-radius:4px;height:6px;overflow:hidden;">
                                <div style="height:100%;width:${barPct}%;background:${barColor};border-radius:4px;transition:width 0.6s ease;"></div>
                            </div>
                        </div>`;
                    }).join('')}
                    <div style="margin-top:0.75rem;font-size:0.72rem;color:var(--text-muted);border-top:1px solid rgba(255,255,255,0.08);padding-top:0.6rem;">
                        <i class="fa-solid fa-circle-info"></i> Red bars raise risk · Green bars lower risk · Values are SHAP attributions
                    </div>
                </div>` : ''}


                <!-- Assigned Member -->
                <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);margin-bottom:0.6rem;">
                    <i class="fa-solid fa-user-check"></i> Assigned Member
                </div>
                ${assignedHtml}

                <!-- Project Progress -->
                <div style="margin-top:1.25rem;padding:0.75rem;background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);border-radius:8px;">
                    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;color:var(--text-muted);margin-bottom:0.4rem;">Overall Project Progress</div>
                    <div style="display:flex;align-items:center;gap:0.75rem;">
                        <div style="flex:1;background:rgba(255,255,255,0.08);border-radius:8px;height:10px;overflow:hidden;">
                            <div style="height:100%;width:${data.project_progress_pct}%;background:linear-gradient(90deg,#3b82f6,#8b5cf6);border-radius:8px;transition:width 0.8s;"></div>
                        </div>
                        <span style="font-weight:800;font-size:1rem;color:#3b82f6;">${data.project_progress_pct}%</span>
                    </div>
                </div>

                ${allMembersHtml}
            `;
        } catch (err) {
            document.getElementById('tpModalBody').innerHTML = `<p style="color:#ef4444;">Failed to load progress data. Please try again.</p>`;
            console.error(err);
        }
    }

    // ============================================================
    // SECTION 6: NOVELTY 10 — MONTE CARLO WHAT-IF SIMULATOR ⭐
    // ─────────────────────────────────────────────────────────────
    // API: POST /api/simulate
    // Payload: { intervention_type: 'ADD_DEVELOPER' | 'EXTEND_SPRINT',
    //            intervention_value: 1.0 }
    // Backend: runs 1,000 Monte Carlo simulations with Gaussian
    //          noise (sigma=10%) and returns:
    //   - simulated_runs: 1000
    //   - mean_new_duration_days: average completion time
    //   - probability_on_time: % of runs that finished in time
    // ============================================================
    const btnSimulate = document.getElementById('btnSimulate');
    if (btnSimulate) {
        btnSimulate.addEventListener('click', async () => {
            const intervention = document.getElementById('simIntervention').value;
            const resContainer = document.getElementById('simResults');
            btnSimulate.textContent = "Simulating...";
            btnSimulate.disabled = true;

            try {
                const response = await fetch('/api/simulate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ intervention_type: intervention, intervention_value: 1.0 })
                });
                
                if (!response.ok) throw new Error("Need an active schedule first!");
                const data = await response.json();
                
                document.getElementById('simRuns').textContent = data.simulated_runs;
                document.getElementById('simDuration').textContent = data.mean_new_duration_days.toFixed(1);
                document.getElementById('simProb').textContent = data.probability_on_time.toFixed(1) + "%";
                
                resContainer.classList.remove('hidden');
            } catch (err) {
                alert(err.message);
            } finally {
                btnSimulate.textContent = "Run Monte Carlo";
                btnSimulate.disabled = false;
            }
        });
    }

    // ============================================================
    // SECTION 7: NOVELTY 8 — PARETO-OPTIMAL SCHEDULE (NSGA-II) ⭐
    // ─────────────────────────────────────────────────────────────
    // API: POST /api/schedule/pareto
    // Backend: runs NSGA-II genetic algorithm (pop_size=20, n_gen=10)
    //          optimising 3 objectives simultaneously:
    //   1. Duration  — minimise total project days
    //   2. Burnout   — minimise variance in effort across tasks
    //   3. Milestone Visibility — maximise early task weight
    // Returns top 3 Pareto-front solutions (trade-off options)
    // for the project manager to choose from.
    // ============================================================
    const btnPareto = document.getElementById('btnPareto');
    if (btnPareto) {
        btnPareto.addEventListener('click', async () => {
            const resContainer = document.getElementById('paretoResults');
            const tableBody = document.getElementById('paretoTableBody');
            btnPareto.textContent = "Running NSGA-II...";
            btnPareto.disabled = true;

            try {
                const response = await fetch('/api/schedule/pareto', { method: 'POST' });
                const data = await response.json();
                
                tableBody.innerHTML = "";
                data.pareto_fronts.forEach(opt => {
                    tableBody.innerHTML += `
                        <tr>
                            <td><strong>Option ${opt.option_id}</strong></td>
                            <td>${opt.duration_days} d</td>
                            <td>${opt.burnout_variance_score}</td>
                            <td>${opt.milestone_visibility_score}</td>
                        </tr>
                    `;
                });
                resContainer.classList.remove('hidden');
            } catch (err) {
                alert("Failed to generate Pareto schedules.");
            } finally {
                btnPareto.textContent = "Generate NSGA-II Trade-offs";
                btnPareto.disabled = false;
            }
        });
    }

    // Delegate submit doc button clicks inside gantt
    ganttContainer.addEventListener('click', (e) => {
        const btn = e.target.closest('.task-submit-btn');
        if (!btn) return;
        currentSubmitTaskId = parseInt(btn.dataset.taskid);
        document.getElementById('submitModalTaskName').textContent = `Task: ${btn.dataset.taskname}`;
        document.getElementById('submitResult').classList.add('hidden');
        document.getElementById('milestoneFile').value = '';
        document.getElementById('submitModal').classList.remove('hidden');
    });
});

// --- State for submit modal ---
let currentSubmitTaskId = null;

// ============================================================
// SECTION 8: GITHUB INTEGRATION
// ─────────────────────────────────────────────────────────────
// Two API calls:
//   GET  /api/github/status   — checks if repo is already connected
//   POST /api/github/register — saves repo URL so backend can
//                               receive webhook push events
// Once registered, GitHub sends commit data to:
//   POST /api/webhooks/github  (NOVELTY 9 — Sentiment Analysis)
// The webhook handler reads commit messages, runs DistilBERT
// sentiment, and auto-updates the matching task status.
// ============================================================
document.getElementById('btnGithubConnect').addEventListener('click', async () => {
    const modal = document.getElementById('githubModal');
    const banner = document.getElementById('githubStatusBanner');
    modal.classList.remove('hidden');
    banner.classList.add('hidden');
    // Check if already connected
    try {
        const res = await fetch('/api/github/status');
        const data = await res.json();
        if (data.connected) {
            banner.textContent = `✅ Connected to: ${data.repo_url}`;
            banner.classList.remove('hidden');
            document.getElementById('githubRepoUrl').value = data.repo_url;
        }
    } catch(e) {}
});
document.getElementById('closeGithubModal').addEventListener('click', () => {
    document.getElementById('githubModal').classList.add('hidden');
});
document.getElementById('btnRegisterGithub').addEventListener('click', async () => {
    const url = document.getElementById('githubRepoUrl').value.trim();
    if (!url) return;
    const btn = document.getElementById('btnRegisterGithub');
    btn.textContent = 'Connecting...';
    try {
        const res = await fetch('/api/github/register', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({repo_url: url})
        });
        const data = await res.json();
        document.getElementById('webhookUrl').textContent = window.location.origin + '/api/webhooks/github';
        document.getElementById('webhookInstructions').classList.remove('hidden');
        const banner = document.getElementById('githubStatusBanner');
        banner.textContent = '✅ Repository registered! Follow the instructions below to activate webhook.';
        banner.classList.remove('hidden');
    } catch(e) { alert('Failed to register.'); }
    btn.textContent = 'Connect';
});

// --- Notifications ---
// ============================================================
// SECTION 9: NOTIFICATIONS
// ─────────────────────────────────────────────────────────────
// API: GET /api/notifications
// Fetches system notifications (task completions, risk alerts,
// GitHub push events) and displays them in the bell dropdown.
// POST /api/notifications/read — marks all as read.
// ============================================================
async function loadNotifications() {
    try {
        const res = await fetch('/api/notifications');
        const data = await res.json();
        const badge = document.getElementById('notifBadge');
        const list = document.getElementById('notifList');
        const count = data.notifications.length;
        if (count > 0) {
            badge.textContent = count;
            badge.classList.remove('hidden');
            list.innerHTML = data.notifications.map(n => `
                <div class="notif-item ${n.type.toLowerCase()}">
                    <div>${n.message}</div>
                    <div class="notif-time">${new Date(n.created_at).toLocaleString()}</div>
                </div>
            `).join('');
        } else {
            badge.classList.add('hidden');
            list.innerHTML = '<p style="color:var(--text-muted);padding:1rem;font-size:0.85rem;">No unread notifications.</p>';
        }
    } catch(e) {}
}
loadNotifications();
setInterval(loadNotifications, 30000);

document.getElementById('notifBell').addEventListener('click', () => {
    document.getElementById('notifPanel').classList.toggle('hidden');
});
document.getElementById('btnMarkRead').addEventListener('click', async () => {
    await fetch('/api/notifications/read', {method:'POST'});
    loadNotifications();
    document.getElementById('notifPanel').classList.add('hidden');
});

// ============================================================
// SECTION 10: MILESTONE DOCUMENT SUBMISSION
// ─────────────────────────────────────────────────────────────
// API: POST /api/milestone/submit
// Allows team members to upload a PDF/Word document to prove
// a WBS task has been completed (e.g. design doc, report).
// The backend checks the task's requires_document flag and
// stores the file reference in the database.
// ============================================================
document.getElementById('closeSubmitModal').addEventListener('click', () => {
    document.getElementById('submitModal').classList.add('hidden');
});
document.getElementById('btnSubmitMilestone').addEventListener('click', async () => {
    const fileInput = document.getElementById('milestoneFile');
    if (!fileInput.files[0]) { alert('Please select a file first.'); return; }
    const btn = document.getElementById('btnSubmitMilestone');
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Uploading...';
    btn.disabled = true;
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('task_id', currentSubmitTaskId);
    try {
        const res = await fetch('/api/milestone/submit', {method:'POST', body: formData});
        const data = await res.json();
        const result = document.getElementById('submitResult');
        result.textContent = `✅ ${data.message} — File: ${data.filename}`;
        result.classList.remove('hidden');
        loadNotifications();
        setTimeout(() => {
            document.getElementById('submitModal').classList.add('hidden');
        }, 2000);
    } catch(e) { alert('Upload failed. Please try again.'); }
    btn.innerHTML = '<i class="fa-solid fa-upload"></i> Upload & Mark Complete';
    btn.disabled = false;
});

// Close modals on overlay click
document.getElementById('githubModal').addEventListener('click', (e) => {
    if (e.target === document.getElementById('githubModal')) document.getElementById('githubModal').classList.add('hidden');
});
document.getElementById('submitModal').addEventListener('click', (e) => {
    if (e.target === document.getElementById('submitModal')) document.getElementById('submitModal').classList.add('hidden');
});

// Task Progress Modal — close on X button or overlay click
const taskProgressModal = document.getElementById('taskProgressModal');
if (taskProgressModal) {
    document.getElementById('closeTaskProgressModal').addEventListener('click', () => {
        taskProgressModal.classList.add('hidden');
    });
    taskProgressModal.addEventListener('click', (e) => {
        if (e.target === taskProgressModal) taskProgressModal.classList.add('hidden');
    });
    // Also close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') taskProgressModal.classList.add('hidden');
    });
}

// ============================================================
// NOVELTY 12: Individual WBS Progress Tracker JavaScript
// ============================================================

// Stores real names returned by the backend (extracted from PDF)
let currentTeamMembers = [];
let currentSchedule = [];

// ============================================================
// SECTION 11: NOVELTY 12 — INDIVIDUAL PROGRESS TRACKER INIT ⭐
// ─────────────────────────────────────────────────────────────
// Called right after schedule generation with the returned
// task list and team member IT numbers.
// Sets up:
//   • The member name input chips (IT numbers displayed as pills)
//   • The task assignment table (renderAssignmentTable)
//   • The progress cards panel (loadProgressCards)
// All changes persist to SQLite via the /api/progress/* endpoints.
// ============================================================
async function initProgressTracker(schedule, teamSize, teamMembers) {
    currentSchedule = schedule;

    // Reset old assignments on the backend when a new schedule is generated
    await fetch('/api/progress/reset', { method: 'DELETE' });

    // A name is a "placeholder" only if it matches "Member N" pattern.
    // IT numbers (IT22117014) and any other real strings are treated as valid.
    const isPlaceholder = !teamMembers || teamMembers.length === 0 ||
        teamMembers.every(n => /^Member\s*\d+$/i.test(n));

    if (!isPlaceholder) {
        currentTeamMembers = teamMembers.slice(0, teamSize);
    } else {
        currentTeamMembers = Array.from({ length: teamSize }, (_, i) => `Member ${i + 1}`);
    }

    // ── Update the team names display panel ──────────────────────
    const namesDisplay = document.getElementById('teamNamesDisplay');
    if (namesDisplay) {
        if (isPlaceholder) {
            namesDisplay.innerHTML = `
                <span style="display:inline-block;background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.35);
                    border-radius:20px;padding:4px 14px;margin:2px;font-size:0.82rem;color:#fbbf24;">
                    <i class="fa-solid fa-triangle-exclamation" style="margin-right:6px;"></i>
                    No IT numbers found — enter names below ↓
                </span>`;
        } else {
            // Show IT numbers with a monospace chip style
            namesDisplay.innerHTML = currentTeamMembers.map(name => {
                const isIT = /^IT\d{8}$/.test(name);
                return `<span style="display:inline-block;
                    background:${isIT ? 'rgba(139,92,246,0.15)' : 'rgba(59,130,246,0.15)'};
                    border:1px solid ${isIT ? 'rgba(139,92,246,0.4)' : 'rgba(59,130,246,0.3)'};
                    border-radius:20px;padding:3px 12px;margin:2px;
                    font-size:0.82rem;font-family:${isIT ? 'monospace' : 'inherit'};
                    color:${isIT ? '#c4b5fd' : '#93c5fd'};">${name}</span>`;
            }).join('');
        }
    }

    // ── Set up the manual override input ─────────────────────────
    const namesInput = document.getElementById('teamNamesInput');
    if (namesInput) {
        if (isPlaceholder) {
            namesInput.value = '';
            namesInput.placeholder = 'e.g. IT22117014, IT22113004, IT22115024, IT22118042';
            setTimeout(() => namesInput.focus(), 300);
        } else {
            // Pre-fill with extracted IT numbers so user can edit/override
            namesInput.value = currentTeamMembers.join(', ');
            namesInput.placeholder = 'Override with names if needed';
        }
    }

    renderAssignmentTable(schedule, currentTeamMembers);
    loadProgressCards();
}

// ============================================================
// Custom Multi-Select Builder for task assignment
// Allows picking 1, 2, 3, or all members per task
// ============================================================
// ============================================================
// SECTION 12: MULTI-SELECT DROPDOWN COMPONENT
// ─────────────────────────────────────────────────────────────
// Custom dropdown that allows assigning 1 or MORE team members
// to a single task (e.g. collaborative tasks like Testing need
// all 4 members; individual dev tasks need only 1).
// When selection changes → API: POST /api/progress/assign
// ============================================================
function createMultiSelect(taskId, taskName, effort, memberNames, initialValue) {
    const wrapper = document.createElement('div');
    wrapper.className = 'ms-wrapper';
    wrapper.dataset.taskid   = taskId;
    wrapper.dataset.taskname = taskName;
    wrapper.dataset.effort   = effort;

    // ── Display button ─────────────────────────────────────────
    const display = document.createElement('div');
    display.className = 'ms-display';
    const displayText = document.createElement('span');
    displayText.className = 'ms-display-text';
    displayText.textContent = '-- Select --';
    const chevron = document.createElement('i');
    chevron.className = 'fa-solid fa-chevron-down ms-chevron';
    display.appendChild(displayText);
    display.appendChild(chevron);

    // ── Options panel ───────────────────────────────────────────
    const panel = document.createElement('div');
    panel.className = 'ms-panel hidden';

    // "All Members" option
    const allOpt = buildCheckboxRow('All Members', '👥 All Members');
    panel.appendChild(allOpt);
    const sep = document.createElement('div');
    sep.className = 'ms-sep';
    panel.appendChild(sep);
    // Individual member options
    memberNames.forEach(name => panel.appendChild(buildCheckboxRow(name, name)));

    wrapper.appendChild(display);
    wrapper.appendChild(panel);

    function buildCheckboxRow(value, label) {
        const row = document.createElement('label');
        row.className = 'ms-option';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = value;
        const lbl = document.createElement('span');
        lbl.textContent = label;
        row.appendChild(cb); row.appendChild(lbl);
        return row;
    }

    // ── Update display text based on checked boxes ──────────────
    function refreshDisplay() {
        const checked = [...panel.querySelectorAll('input:checked')].map(c => c.value);
        if (checked.length === 0) {
            displayText.textContent = '-- Select --';
            displayText.style.color = 'var(--text-muted)';
        } else if (checked.includes('All Members')) {
            displayText.textContent = '👥 All Members';
            displayText.style.color = '#3b82f6';
        } else if (checked.length === 1) {
            displayText.textContent = checked[0];
            displayText.style.color = '#f8fafc';
        } else {
            displayText.textContent = `${checked.length} members selected`;
            displayText.style.color = '#a78bfa';
        }
        return checked.includes('All Members') ? 'All Members' : checked.join(',');
    }

    // ── Expose setValues so auto-balance can update the UI ──────
    wrapper._setValues = function(valueStr) {
        const values = valueStr === 'All Members'
            ? ['All Members']
            : (valueStr || '').split(',').map(v => v.trim()).filter(Boolean);
        panel.querySelectorAll('input').forEach(cb => {
            cb.checked = values.includes(cb.value);
        });
        refreshDisplay();
    };

    // Set initial value
    if (initialValue) wrapper._setValues(initialValue);

    // ── Toggle panel open/close ─────────────────────────────────
    display.addEventListener('click', e => {
        e.stopPropagation();
        // Close all other panels
        document.querySelectorAll('.ms-panel:not(.hidden)').forEach(p => {
            if (p !== panel) p.classList.add('hidden');
        });
        panel.classList.toggle('hidden');
        chevron.style.transform = panel.classList.contains('hidden') ? '' : 'rotate(180deg)';
    });

    // ── Handle checkbox changes ────────────────────────────────
    panel.addEventListener('change', async e => {
        const cb = e.target;
        if (cb.type !== 'checkbox') return;
        // Mutual exclusion: "All Members" vs individuals
        if (cb.value === 'All Members' && cb.checked) {
            panel.querySelectorAll('input').forEach(c => { if (c.value !== 'All Members') c.checked = false; });
        } else if (cb.value !== 'All Members' && cb.checked) {
            const allCb = panel.querySelector('input[value="All Members"]');
            if (allCb) allCb.checked = false;
        }
        const assignedTo = refreshDisplay();
        if (!assignedTo || assignedTo === '') return;
        // Save to API
        try {
            await fetch('/api/progress/assign', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: parseInt(taskId),
                    task_name: taskName,
                    assigned_to: assignedTo,
                    effort_hours: parseFloat(effort)
                })
            });
            loadProgressCards();
        } catch (err) { console.error('Assignment save failed:', err); }
    });

    // Stop panel clicks from bubbling to document (which closes panels)
    panel.addEventListener('click', e => e.stopPropagation());

    return wrapper;
}

// Close all multi-select panels when clicking outside
document.addEventListener('click', () => {
    document.querySelectorAll('.ms-panel:not(.hidden)').forEach(p => {
        p.classList.add('hidden');
        const chevron = p.previousElementSibling?.querySelector('.ms-chevron');
        if (chevron) chevron.style.transform = '';
    });
});

// ============================================================
// Render Assignment Table
// ============================================================
// ============================================================
// SECTION 13: TASK ASSIGNMENT BOARD RENDERER
// ─────────────────────────────────────────────────────────────
// Renders the full assignment table showing every WBS task
// with a multi-select dropdown for member assignment.
// Each row also has a "Mark Done" button:
//   → API: POST /api/progress/task-complete
//     Updates task status to COMPLETED in task_assignments
//     and schedule_versions tables (SQLite).
// ============================================================
function renderAssignmentTable(schedule, memberNames) {
    const container = document.getElementById('assignmentTable');
    container.innerHTML = '';

    // Header
    const header = document.createElement('div');
    header.className = 'assign-row';
    header.style.cssText = 'background:rgba(255,255,255,0.04);font-size:0.78rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;letter-spacing:0.05em;';
    header.innerHTML = `<span>#</span><span>Task Name</span><span>Assign To</span><span>Effort</span><span>Status</span>`;
    container.appendChild(header);

    schedule.forEach(task => {
        const isCompleted = task.status === 'COMPLETED';
        const row = document.createElement('div');
        row.className = `assign-row ${isCompleted ? 'is-completed' : ''}`;
        row.id = `assign-row-${task.task_id}`;

        // Static columns
        const numSpan = document.createElement('span');
        numSpan.className = 'assign-task-num';
        numSpan.textContent = task.task_id;

        const nameSpan = document.createElement('span');
        nameSpan.className = 'assign-task-name';
        nameSpan.title = task.task_name;
        nameSpan.textContent = task.task_name;

        // Multi-select
        const multiSelect = createMultiSelect(
            task.task_id, task.task_name, task.effort_hours, memberNames, ''
        );

        const effortSpan = document.createElement('span');
        effortSpan.className = 'assign-effort';
        effortSpan.textContent = `${task.effort_hours}h`;

        // Complete button
        const statusSlot = document.createElement('span');
        if (isCompleted) {
            statusSlot.innerHTML = `<span class="completed-badge"><i class="fa-solid fa-check"></i> Done</span>`;
        } else {
            const btn = document.createElement('button');
            btn.className = 'btn-complete-task';
            btn.dataset.taskid = task.task_id;
            btn.title = 'Click to mark this task as completed';
            btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Mark Done';
            btn.addEventListener('click', async () => {
                btn.disabled = true;
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
                try {
                    await fetch('/api/progress/task-complete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ task_id: parseInt(task.task_id) })
                    });
                    row.classList.add('is-completed');
                    btn.outerHTML = `<span class="completed-badge"><i class="fa-solid fa-check"></i> Done</span>`;
                    loadProgressCards();
                } catch (err) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa-solid fa-check"></i> Complete';
                    console.error('Complete task failed:', err);
                }
            });
            statusSlot.appendChild(btn);
        }

        row.appendChild(numSpan);
        row.appendChild(nameSpan);
        row.appendChild(multiSelect);
        row.appendChild(effortSpan);
        row.appendChild(statusSlot);
        container.appendChild(row);
    });
}

// ============================================================
// Auto-Balance Workload Button Handler
// ============================================================
// ============================================================
// SECTION 14: NOVELTY 12 — AUTO-ASSIGN (LPT Algorithm) ⭐
// ─────────────────────────────────────────────────────────────
// API: POST /api/progress/auto-assign
// Payload: { team_members: [...IT numbers], tasks: [...] }
// Backend logic (main.py ~line 1068):
//   1. Identifies COLLABORATIVE tasks by keyword matching
//      (kickoff, testing, integration, deployment, etc.)
//      → Assigns to ALL members, splits effort equally
//   2. Sorts remaining INDIVIDUAL tasks by effort DESC (LPT order)
//      → Assigns each to the member with the LEAST current load
//         (greedy load-balancing = Longest Processing Time algo)
// This ensures fair workload distribution automatically.
// ============================================================
const btnAutoAssign = document.getElementById('btnAutoAssign');
if (btnAutoAssign) {
    btnAutoAssign.addEventListener('click', async () => {
        if (!currentSchedule.length || !currentTeamMembers.length) {
            alert('Please generate a schedule first.');
            return;
        }

        btnAutoAssign.disabled = true;
        btnAutoAssign.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Balancing...';

        try {
            const tasks = currentSchedule.map(t => ({
                task_id: t.task_id,
                task_name: t.task_name,
                effort_hours: t.effort_hours
            }));

            const res = await fetch('/api/progress/auto-assign', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    team_members: currentTeamMembers,
                    tasks: tasks,
                    proposal_text: document.getElementById('proposalText')?.value || '',
                    project_id: window._currentProjectId || 'demo_project_01'
                })
            });

            const data = await res.json();

            // Update all multi-selects to reflect auto-assigned values
            data.assignments.forEach(a => {
                const wrapper = document.querySelector(`.ms-wrapper[data-taskid="${a.task_id}"]`);
                if (wrapper && wrapper._setValues) {
                    wrapper._setValues(a.assigned_to);
                    if (a.is_collaborative) {
                        const row = document.getElementById(`assign-row-${a.task_id}`);
                        if (row) row.style.background = 'rgba(59,130,246,0.08)';
                    }
                }
                // Fix 4: Inject "Why?" button into each individual task row
                if (!a.is_collaborative && a.assign_reason) {
                    const row = document.getElementById(`assign-row-${a.task_id}`);
                    if (row && !row.querySelector('.why-btn')) {
                        const whyBtn = document.createElement('button');
                        whyBtn.className = 'why-btn';
                        whyBtn.title = 'See why this member was selected';
                        whyBtn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Why?';
                        whyBtn.style.cssText = `
                            font-size:0.7rem;padding:2px 8px;border-radius:6px;cursor:pointer;
                            background:rgba(139,92,246,0.15);border:1px solid rgba(139,92,246,0.35);
                            color:#c4b5fd;margin-left:4px;white-space:nowrap;
                        `;
                        whyBtn.addEventListener('click', () => {
                            const existing = row.querySelector('.why-tooltip');
                            if (existing) { existing.remove(); return; }
                            const tip = document.createElement('div');
                            tip.className = 'why-tooltip';
                            tip.style.cssText = `
                                grid-column:1/-1;padding:0.75rem 1rem;margin-top:0.25rem;
                                background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.3);
                                border-radius:8px;font-size:0.74rem;color:#ddd6fe;line-height:1.6;
                            `;
                            tip.innerHTML = `<i class="fa-solid fa-robot" style="color:#a78bfa;margin-right:6px;"></i><strong>Algorithm Decision:</strong><br>${a.assign_reason.replace(/\|/g, '<br>→')}`;
                            row.after(tip);
                        });
                        // Insert before the effort span (4th child)
                        const effortSpan = row.querySelector('.assign-effort');
                        if (effortSpan) effortSpan.before(whyBtn);
                    }
                }
            });

            // ── Render component-grouped task board ─────────────────
            if (data.component_summary && data.component_summary.length > 0) {
                renderComponentTaskBoard(data.component_summary, data.member_components || {});
            }

            // Reload progress cards
            await loadProgressCards();

            // ============================================================
            // Fix 1+2: Render Workload Balance Panel (replaces alert)
            // ============================================================
            renderWorkloadBalancePanel(data);

        } catch (err) {
            console.error('Auto-assign failed:', err);
            alert('Auto-assign failed. Make sure a schedule is generated first.');
        } finally {
            btnAutoAssign.disabled = false;
            btnAutoAssign.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Auto-Balance Workload';
        }
    });
}

// ============================================================
// Apply Names Button Handler — manual name override
// ============================================================
// ============================================================
// SECTION 15: APPLY IT NUMBER NAMES
// ─────────────────────────────────────────────────────────────
// Reads the 4 text inputs where the user types their IT numbers
// (e.g. IT22117014) and updates the assignment table dropdowns
// to show real IT numbers instead of generic Member 1/2/3/4.
// No API call needed — this is a pure frontend update.
// ============================================================
const btnApplyNames = document.getElementById('btnApplyNames');
if (btnApplyNames) {
    btnApplyNames.addEventListener('click', () => {
        const input = document.getElementById('teamNamesInput');
        if (!input || !input.value.trim()) {
            alert('Please type team member names separated by commas.');
            return;
        }

        // Parse comma-separated names, trim whitespace
        const parsed = input.value.split(',').map(n => n.trim()).filter(n => n.length > 1);
        if (parsed.length === 0) {
            alert('No valid names found. Please enter names separated by commas (e.g. Alice, Bob, Charlie).');
            return;
        }

        // Update the global team members list
        currentTeamMembers = parsed;

        // Update the badge display
        const namesDisplay = document.getElementById('teamNamesDisplay');
        if (namesDisplay) {
            namesDisplay.innerHTML = currentTeamMembers.map(name =>
                `<span style="display:inline-block;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);border-radius:20px;padding:2px 10px;margin:2px;font-size:0.8rem;">${name}</span>`
            ).join('');
        }

        // Re-render the assignment table with new names
        if (currentSchedule.length > 0) {
            renderAssignmentTable(currentSchedule, currentTeamMembers);
            loadProgressCards();
        }

        alert(`✅ Names updated! Dropdowns now show: ${currentTeamMembers.join(', ')}`);
    });
}

// ============================================================
// SECTION 16: PROGRESS CARDS — EFFORT-WEIGHTED PROGRESS ⭐
// ─────────────────────────────────────────────────────────────
// API: GET /api/progress/individual
// Backend (main.py ~line 975) returns per-member stats:
//   - total_effort_hours (XGBoost-predicted)
//   - completed_effort_hours
//   - progress_pct = completed / total * 100  (effort-weighted!)
//   - is_bottleneck = progress_pct < 50%
//
// KEY POINT for viva: Progress is weighted by EFFORT HOURS,
// not by task count. A 100-hour task completion contributes
// more than a 5-hour task — giving a fair, true measure.
// ============================================================
async function loadProgressCards() {
    try {
        const res = await fetch('/api/progress/individual');
        const data = await res.json();
        renderProgressRing(data.project_progress_pct);
        renderMemberCards(data);
        // Update project stats
        document.getElementById('projectTotalEffort').textContent = `${data.total_effort_hours} hrs`;
        document.getElementById('projectCompletedEffort').textContent = `${data.completed_effort_hours} hrs`;
        document.getElementById('projectAssignedTasks').textContent =
            data.members.reduce((sum, m) => sum + m.total_tasks, 0);
    } catch (err) {
        console.error('Progress load failed:', err);
    }
}

function renderProgressRing(pct) {
    const circle = document.getElementById('projectRingCircle');
    const label = document.getElementById('projectProgressPct');
    if (!circle || !label) return;
    const circumference = 314.16;
    const offset = circumference - (pct / 100) * circumference;
    circle.style.strokeDashoffset = offset;
    // Color based on progress
    circle.style.stroke = pct >= 75 ? '#10b981' : pct >= 40 ? '#3b82f6' : '#f59e0b';
    label.textContent = `${pct}%`;
}

function renderMemberCards(data) {
    const container = document.getElementById('memberCards');
    if (!data.members || data.members.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted);font-size:0.85rem;">Assign tasks above to see individual progress cards.</p>';
        return;
    }

    container.innerHTML = data.members.map(member => {
        const pct = member.progress_pct;
        const pctClass = pct >= 75 ? 'done' : pct >= 40 ? 'warning' : 'danger';
        const initials = member.member.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
        const bottleneckHtml = member.is_bottleneck
            ? `<div class="bottleneck-alert"><i class="fa-solid fa-triangle-exclamation"></i> Bottleneck detected — behind schedule</div>`
            : '';

        return `
            <div class="member-card ${member.is_bottleneck ? 'bottleneck' : ''}">
                <div class="member-card-header">
                    <div style="display:flex;align-items:center;">
                        <div class="member-avatar">${initials}</div>
                        <span class="member-name">${member.member}</span>
                    </div>
                    <span class="member-pct ${pctClass}">${pct}%</span>
                </div>
                <div class="member-progress-bar">
                    <div class="member-progress-fill ${pctClass}" style="width:${pct}%"></div>
                </div>
                <div class="member-stats-row">
                    <span>${member.completed_tasks}/${member.total_tasks} tasks done</span>
                    <span>${member.completed_effort_hours}/${member.total_effort_hours} hrs</span>
                </div>
                ${bottleneckHtml}
            </div>
        `;
    }).join('');
}

// Refresh button
document.getElementById('btnRefreshProgress').addEventListener('click', loadProgressCards);

// On page load, try to load existing progress (persisted in DB)
loadProgressCards();


// ============================================================
// COMPONENT-AWARE TASK BOARD — renderComponentTaskBoard()
// ============================================================
const COMP_COLORS = [
    { bg: 'rgba(99,102,241,0.12)', border: 'rgba(99,102,241,0.4)',  accent: '#818cf8' },
    { bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.4)',  accent: '#34d399' },
    { bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.4)',  accent: '#fbbf24' },
    { bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.4)',   accent: '#f87171' },
    { bg: 'rgba(168,85,247,0.12)', border: 'rgba(168,85,247,0.4)',  accent: '#c084fc' },
];
const SHARED_COLOR = { bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.3)', accent: '#60a5fa' };

function renderComponentTaskBoard(componentSummary, memberComponents) {
    const container = document.getElementById('assignmentTable');
    if (!container) return;
    container.innerHTML = '';

    const heading = document.createElement('div');
    heading.style.cssText = 'padding:0.5rem 0 1rem;font-size:0.8rem;color:var(--text-muted);';
    heading.innerHTML = '<i class="fa-solid fa-layer-group" style="margin-right:6px;color:#818cf8;"></i> Tasks grouped by component. Click a header to collapse/expand.';
    container.appendChild(heading);

    componentSummary.forEach((comp, idx) => {
        const isShared = comp.member === 'All Members';
        const color = isShared ? SHARED_COLOR : COMP_COLORS[idx % COMP_COLORS.length];
        const icon = isShared ? 'fa-users' : 'fa-cube';
        const totalTasks = comp.tasks.length;
        const doneTasks = comp.tasks.filter(t => t.status === 'COMPLETED').length;
        const progressPct = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : 0;

        const card = document.createElement('div');
        card.style.cssText = `border:1px solid ${color.border};border-radius:14px;background:${color.bg};margin-bottom:1rem;overflow:hidden;`;

        const headerDiv = document.createElement('div');
        headerDiv.style.cssText = `display:flex;align-items:center;justify-content:space-between;padding:0.9rem 1.2rem;cursor:pointer;user-select:none;border-bottom:1px solid ${color.border};`;

        const leftInfo = document.createElement('div');
        leftInfo.style.cssText = 'display:flex;align-items:center;gap:0.75rem;';
        leftInfo.innerHTML = `
            <i class="fa-solid ${icon}" style="color:${color.accent};font-size:1rem;"></i>
            <div>
                <div style="font-weight:700;font-size:0.92rem;color:#e2e8f0;">
                    ${isShared ? '\u{1F91D} Shared Tasks \u2014 All Members' : '\u{1F4E6} ' + comp.component_name}
                </div>
                ${!isShared ? `<div style="font-size:0.76rem;color:${color.accent};margin-top:2px;">Owner: ${comp.member}</div>` : ''}
            </div>`;

        const rightInfo = document.createElement('div');
        rightInfo.style.cssText = 'display:flex;align-items:center;gap:1rem;';
        rightInfo.innerHTML = `
            <span style="font-size:0.76rem;color:var(--text-muted);">${totalTasks} tasks &bull; ${comp.total_effort}h</span>
            <div style="width:80px;height:6px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden;">
                <div style="width:${progressPct}%;height:100%;background:${color.accent};border-radius:3px;"></div>
            </div>
            <span style="font-size:0.78rem;font-weight:600;color:${color.accent};">${progressPct}%</span>
            <i class="fa-solid fa-chevron-down comp-chevron" style="color:var(--text-muted);font-size:0.75rem;transition:transform 0.3s;"></i>`;

        headerDiv.appendChild(leftInfo);
        headerDiv.appendChild(rightInfo);

        const bodyDiv = document.createElement('div');
        bodyDiv.style.cssText = 'padding:0.5rem 0;';

        const colRow = document.createElement('div');
        colRow.style.cssText = `display:grid;grid-template-columns:2rem 1fr 7rem 5rem 5rem;padding:0.4rem 1.2rem;font-size:0.72rem;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;`;
        colRow.innerHTML = '<span>#</span><span>Task</span><span>Assigned To</span><span style="text-align:right;">Effort</span><span style="text-align:center;">Status</span>';
        bodyDiv.appendChild(colRow);

        comp.tasks.forEach((task, ti) => {
            const isDone = task.status === 'COMPLETED';
            const taskRow = document.createElement('div');
            taskRow.id = `comp-row-${task.task_id}-${idx}`;
            taskRow.style.cssText = `display:grid;grid-template-columns:2rem 1fr 7rem 5rem 5rem;padding:0.5rem 1.2rem;align-items:center;font-size:0.83rem;border-top:1px solid rgba(255,255,255,0.05);background:${isDone ? 'rgba(16,185,129,0.06)' : 'transparent'};opacity:${isDone ? '0.7' : '1'};`;

            const assigneeTxt = isShared ? 'All Members' : (task.assigned_to || comp.member);
            const shortAssignee = assigneeTxt.length > 12 ? assigneeTxt.substring(0, 10) + '\u2026' : assigneeTxt;

            taskRow.innerHTML = `
                <span style="color:var(--text-muted);">${ti + 1}</span>
                <span style="font-weight:500;color:${isDone ? '#6b7280' : '#e2e8f0'};text-decoration:${isDone ? 'line-through' : 'none'};" title="${task.task_name}">${task.task_name}</span>
                <span style="font-size:0.74rem;color:${color.accent};background:${color.bg};border:1px solid ${color.border};border-radius:10px;padding:1px 8px;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${assigneeTxt}">${shortAssignee}</span>
                <span style="text-align:right;color:var(--text-muted);font-size:0.8rem;">${task.effort_hours}h</span>
                <span style="text-align:center;" class="status-cell-${task.task_id}"></span>`;

            const statusCell = taskRow.querySelector(`.status-cell-${task.task_id}`);
            if (isDone) {
                statusCell.innerHTML = `<span style="color:#34d399;font-size:0.75rem;font-weight:600;"><i class="fa-solid fa-check"></i> Done</span>`;
            } else {
                const doneBtn = document.createElement('button');
                doneBtn.style.cssText = `font-size:0.7rem;padding:3px 8px;border-radius:8px;cursor:pointer;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.35);color:#34d399;white-space:nowrap;`;
                doneBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Done';
                doneBtn.addEventListener('click', async () => {
                    doneBtn.disabled = true;
                    doneBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
                    try {
                        await fetch('/api/progress/task-complete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ task_id: parseInt(task.task_id) })
                        });
                        taskRow.style.background = 'rgba(16,185,129,0.06)';
                        taskRow.style.opacity = '0.7';
                        statusCell.innerHTML = `<span style="color:#34d399;font-size:0.75rem;font-weight:600;"><i class="fa-solid fa-check"></i> Done</span>`;
                        loadProgressCards();
                    } catch (e) {
                        doneBtn.disabled = false;
                        doneBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Done';
                    }
                });
                statusCell.appendChild(doneBtn);
            }
            bodyDiv.appendChild(taskRow);
        });

        if (comp.tasks.length === 0) {
            bodyDiv.innerHTML += `<div style="padding:1rem 1.2rem;color:var(--text-muted);font-size:0.82rem;">No tasks assigned yet.</div>`;
        }

        // Collapse toggle
        let collapsed = false;
        headerDiv.addEventListener('click', () => {
            collapsed = !collapsed;
            bodyDiv.style.display = collapsed ? 'none' : 'block';
            const chevron = headerDiv.querySelector('.comp-chevron');
            if (chevron) chevron.style.transform = collapsed ? 'rotate(-90deg)' : 'rotate(0deg)';
        });

        card.appendChild(headerDiv);
        card.appendChild(bodyDiv);
        container.appendChild(card);
    });
}

// ============================================================
// Fix 2: WORKLOAD BALANCE PANEL — renderWorkloadBalancePanel()
// ─────────────────────────────────────────────────────────────
// Called after auto-assign. Renders:
//   • Animated horizontal bars per member (with hours label)
//   • Average line across all bars
//   • Balance Score badge (CV% — Coefficient of Variation)
//   • Balance label: EXCELLENT / GOOD / FAIR / POOR
//   • Collaborative vs individual task summary
// ============================================================
function renderWorkloadBalancePanel(data) {
    const panel = document.getElementById('workloadBalancePanel');
    if (!panel) return;

    const summary       = data.workload_summary || [];
    const balanceScore  = data.balance_score_pct ?? null;
    const cvPct         = data.cv_percent ?? null;
    const meanHours     = data.mean_effort_hours ?? 0;
    const maxDev        = data.max_deviation_hours ?? 0;
    const label         = data.balance_label || 'N/A';
    const collabCount   = data.collaborative_count || 0;
    const indivCount    = data.individual_count    || 0;
    const method        = data.fairness_method     || '';

    const maxHours = Math.max(...summary.map(w => w.total_effort_hours), 1);

    // Colour per balance label
    const labelColors = {
        EXCELLENT : { bg: 'rgba(16,185,129,0.2)',  border: 'rgba(16,185,129,0.5)',  text: '#34d399' },
        GOOD      : { bg: 'rgba(59,130,246,0.2)',   border: 'rgba(59,130,246,0.5)',  text: '#93c5fd' },
        FAIR      : { bg: 'rgba(245,158,11,0.2)',   border: 'rgba(245,158,11,0.5)',  text: '#fcd34d' },
        POOR      : { bg: 'rgba(239,68,68,0.2)',    border: 'rgba(239,68,68,0.5)',   text: '#fca5a5' },
    };
    const lc = labelColors[label] || labelColors.GOOD;

    // Member colour palette (same as Gantt)
    const barColors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#14b8a6'];

    // Build bar rows HTML
    const barsHtml = summary.map((w, i) => {
        const pct       = Math.max(1, (w.total_effort_hours / maxHours) * 100);
        const color     = barColors[i % barColors.length];
        const shortName = w.member.length > 14 ? w.member.substring(0, 14) + '…' : w.member;
        const diffFromMean = (w.total_effort_hours - meanHours).toFixed(1);
        const diffSign  = diffFromMean >= 0 ? `+${diffFromMean}h` : `${diffFromMean}h`;
        const diffColor = Math.abs(diffFromMean) < 15 ? '#64748b' : (diffFromMean > 0 ? '#f59e0b' : '#3b82f6');

        return `
        <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.55rem;">
            <div style="width:110px;min-width:110px;font-size:0.76rem;color:#cbd5e1;text-align:right;
                        font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
                 title="${w.member}">${shortName}</div>
            <div style="flex:1;position:relative;height:26px;">
                <div class="wb-bar-bg" style="width:100%;height:100%;background:rgba(255,255,255,0.05);border-radius:6px;overflow:hidden;">
                    <div class="wb-bar-fill" data-target="${pct}"
                         style="height:100%;width:0%;background:linear-gradient(90deg,${color},${color}cc);
                                border-radius:6px;transition:width 0.8s cubic-bezier(.4,0,.2,1);
                                display:flex;align-items:center;padding-left:8px;">
                    </div>
                </div>
                <!-- Mean line marker -->
                <div style="position:absolute;top:0;bottom:0;left:${(meanHours/maxHours*100).toFixed(1)}%;
                            width:2px;background:rgba(251,191,36,0.6);border-radius:1px;pointer-events:none;"
                     title="Team average: ${meanHours}h"></div>
            </div>
            <div style="width:80px;min-width:80px;font-size:0.76rem;display:flex;gap:4px;align-items:center;">
                <span style="color:#f8fafc;font-weight:700;">${w.total_effort_hours}h</span>
                <span style="color:${diffColor};font-size:0.68rem;">(${diffSign})</span>
            </div>
        </div>`;
    }).join('');

    panel.style.display = 'block';
    panel.innerHTML = `
    <div style="background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.2);border-radius:12px;padding:1.25rem;">

        <!-- Header row -->
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.75rem;margin-bottom:1rem;">
            <div>
                <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);margin-bottom:0.25rem;">
                    <i class="fa-solid fa-scale-balanced"></i> Workload Distribution Result
                </div>
                <div style="font-size:0.78rem;color:#94a3b8;">
                    📋 ${collabCount} collaborative tasks → All Members &nbsp;|&nbsp;
                    👤 ${indivCount} individual tasks → RF + LPT assigned
                </div>
            </div>
            <!-- Balance Score Badge -->
            <div style="text-align:center;padding:0.6rem 1.2rem;
                        background:${lc.bg};border:2px solid ${lc.border};border-radius:10px;">
                <div style="font-size:1.6rem;font-weight:800;color:${lc.text};line-height:1;">${balanceScore ?? '—'}%</div>
                <div style="font-size:0.65rem;font-weight:700;color:${lc.text};text-transform:uppercase;letter-spacing:0.08em;">Balance Score</div>
                <div style="font-size:0.68rem;color:${lc.text};margin-top:2px;font-weight:600;">${label}</div>
            </div>
        </div>

        <!-- Stats row -->
        <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem;">
            <div style="background:rgba(0,0,0,0.2);border-radius:8px;padding:0.5rem 0.85rem;font-size:0.75rem;">
                <span style="color:var(--text-muted);">CV (spread): </span>
                <span style="color:#fcd34d;font-weight:700;">${cvPct ?? '—'}%</span>
                <span style="color:var(--text-muted);font-size:0.68rem;"> (lower = more equal)</span>
            </div>
            <div style="background:rgba(0,0,0,0.2);border-radius:8px;padding:0.5rem 0.85rem;font-size:0.75rem;">
                <span style="color:var(--text-muted);">Team avg: </span>
                <span style="color:#93c5fd;font-weight:700;">${meanHours}h</span>
            </div>
            <div style="background:rgba(0,0,0,0.2);border-radius:8px;padding:0.5rem 0.85rem;font-size:0.75rem;">
                <span style="color:var(--text-muted);">Max deviation: </span>
                <span style="color:#fca5a5;font-weight:700;">+${maxDev}h</span>
            </div>
        </div>

        <!-- Legend -->
        <div style="display:flex;align-items:center;gap:1rem;font-size:0.68rem;color:var(--text-muted);margin-bottom:0.75rem;">
            <span><span style="display:inline-block;width:20px;height:2px;background:rgba(251,191,36,0.6);vertical-align:middle;margin-right:4px;"></span> Team average (${meanHours}h)</span>
            <span>Bars show individual effort hours. Diff from avg shown in brackets.</span>
        </div>

        <!-- Bar chart -->
        <div id="workloadBars">${barsHtml}</div>

        <!-- Fairness method note -->
        <div style="margin-top:0.85rem;font-size:0.7rem;color:#475569;border-top:1px solid rgba(255,255,255,0.06);padding-top:0.6rem;">
            <i class="fa-solid fa-circle-nodes" style="margin-right:4px;"></i>
            <strong>Method:</strong> ${method} &nbsp;|&nbsp;
            <i class="fa-solid fa-triangle-exclamation" style="color:#fbbf24;margin-right:2px;"></i>
            <strong>Overload Guard:</strong> W_best &gt; W_min × 1.40 → reassign to least-loaded member
        </div>
    </div>`;

    // Animate bars after DOM paint
    requestAnimationFrame(() => {
        setTimeout(() => {
            panel.querySelectorAll('.wb-bar-fill').forEach(bar => {
                bar.style.width = bar.dataset.target + '%';
            });
        }, 80);
    });

    // Scroll to the balance panel
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
