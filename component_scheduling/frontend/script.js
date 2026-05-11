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

    pdfUpload.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            descriptionBox.value = "⏳ Reading PDF... please wait.";
            const response = await fetch('/api/schedule/upload-pdf', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                // Show the exact server-side error message to the user
                const errMsg = data.detail || 'Unknown error occurred.';
                descriptionBox.value = "";
                alert("PDF Error: " + errMsg);
                return;
            }

            descriptionBox.value = data.extracted_text;
        } catch (error) {
            console.error(error);
            descriptionBox.value = "";
            alert("Network error: Could not reach the backend. Make sure the server is running on port 8000.");
        }
        pdfUpload.value = ''; // Reset input
    });

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

        const payload = {
            description: description,
            team_size: parseInt(document.getElementById('teamSize').value),
            duration_months: parseFloat(document.getElementById('duration').value),
            function_points: parseInt(document.getElementById('complexity').value),
            start_date: document.getElementById('startDate').value
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

    function renderResults(data) {
        // Update KPIs
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
    }

    function renderGantt(schedule, totalDays) {
        ganttContainer.innerHTML = ''; // Clear old

        // 1. Create Timeline Header
        const headerRow = document.createElement('div');
        headerRow.className = 'gantt-timeline-header';
        
        // Add 4 tick marks evenly spaced
        for(let i=0; i<=4; i++) {
            const pct = (i / 4) * 100;
            const mark = document.createElement('div');
            mark.className = 'timeline-mark';
            mark.style.left = `${pct}%`;
            
            const dayNum = Math.round((totalDays * pct) / 100);
            mark.textContent = `Day ${dayNum}`;
            headerRow.appendChild(mark);
        }
        ganttContainer.appendChild(headerRow);

        // 2. Render Task Rows
        let currentDayOffset = 0;

        schedule.forEach((task, index) => {
            const row = document.createElement('div');
            row.className = 'gantt-row';

            // Left Sidebar: Task Info
            const info = document.createElement('div');
            info.className = 'task-info';
            const shapHtml = task.shap_explanation ? `<div class="shap-explanation" title="${task.shap_explanation}">${task.shap_explanation}</div>` : '';
            const isCompleted = task.status === 'COMPLETED';
            
            let actionBadge = '';
            if (isCompleted) {
                actionBadge = `<span style="font-size:0.65rem;color:#22c55e;">✓ Completed</span>`;
            } else if (task.requires_document) {
                actionBadge = `<button class="task-submit-btn" data-taskid="${task.task_id}" data-taskname="${task.task_name}">📎 Submit Doc</button>`;
            } else {
                actionBadge = `<span style="font-size:0.65rem;color:#94a3b8;"><i class="fa-brands fa-github"></i> Tracked via GitHub</span>`;
            }

            info.innerHTML = `
                <div class="task-name" title="${task.task_name}">${index + 1}. ${task.task_name}</div>
                <div class="task-meta">${task.effort_hours} hrs | ${task.duration_days} days</div>
                ${shapHtml}
                ${actionBadge}
            `;

            // Right Sidebar: Gantt Track
            const track = document.createElement('div');
            track.className = 'task-track';

            // Calculate positions percentages relative to total project duration
            const leftPct = (currentDayOffset / totalDays) * 100;
            const widthPct = (task.duration_days / totalDays) * 100;

            const isHighRisk = task.delay_risk_pct >= 50;
            
            const bar = document.createElement('div');
            bar.className = `task-bar ${isHighRisk ? 'risk-high' : 'risk-low'}`;
            // Animate entry
            bar.style.left = '0%';
            bar.style.width = '0%';
            
            bar.innerHTML = `${task.duration_days}d`;
            
            const riskBadge = document.createElement('div');
            riskBadge.className = `risk-badge ${isHighRisk ? 'high' : 'low'}`;
            riskBadge.innerHTML = isHighRisk ? `<i class="fa-solid fa-triangle-exclamation"></i> ${task.delay_risk_pct}% Risk` : `<i class="fa-solid fa-check"></i> OK`;

            track.appendChild(bar);
            track.appendChild(riskBadge);
            
            row.appendChild(info);
            row.appendChild(track);
            ganttContainer.appendChild(row);

            // Trigger animation after DOM insertion
            setTimeout(() => {
                bar.style.left = `${leftPct}%`;
                bar.style.width = `${widthPct}%`;
            }, 50 * index); // Stagger animation

            currentDayOffset += Number(task.duration_days);
        });
    }

    // --- Novelty 10: What-If Simulator ---
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

    // --- Novelty 8: Multi-Objective Pareto Schedules ---
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

// --- GitHub Connect Modal ---
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

// --- Milestone Submit Modal ---
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
