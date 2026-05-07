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
            info.innerHTML = `
                <div class="task-name" title="${task.task_name}">${index + 1}. ${task.task_name}</div>
                <div class="task-meta">${task.effort_hours} hrs | ${task.duration_days} days</div>
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

            currentDayOffset += task.duration_days;
        });
    }
});
