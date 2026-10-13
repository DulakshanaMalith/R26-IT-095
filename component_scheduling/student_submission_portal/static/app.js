const projectInput = document.getElementById('projectId');
const studentInput = document.getElementById('studentId');
const taskSelect = document.getElementById('taskId');
const taskMeta = document.getElementById('taskMeta');
const form = document.getElementById('submissionForm');
const fileInput = document.getElementById('documentFile');
const message = document.getElementById('message');
let tasks = [];

function showMessage(text, type) {
    message.textContent = text;
    message.className = `message ${type}`;
    message.hidden = false;
}

function updateTaskMeta() {
    const task = tasks.find(item => String(item.task_id) === taskSelect.value);
    taskMeta.textContent = task
        ? `${task.task_key} · Assigned to ${task.assigned_to || 'All Members'} · Deadline ${task.end_date || 'not set'} · ${task.status}`
        : '';
}

document.getElementById('loadTasks').addEventListener('click', async () => {
    const projectId = projectInput.value.trim();
    const studentId = studentInput.value.trim();
    if (!projectId || !studentId) return showMessage('Enter both Group ID and Student ID.', 'error');
    const button = document.getElementById('loadTasks');
    button.disabled = true;
    button.textContent = 'Loading…';
    try {
        const response = await fetch(`/api/document-tasks?project_id=${encodeURIComponent(projectId)}&student_id=${encodeURIComponent(studentId)}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Tasks could not be loaded.');
        projectInput.value = payload.project_id || projectId;
        studentInput.value = payload.student_id || studentId;
        tasks = payload.tasks || [];
        if (!tasks.length) {
            form.hidden = true;
            return showMessage('No document tasks are assigned to this student in the latest schedule.', 'error');
        }
        taskSelect.innerHTML = tasks.map(task => `<option value="${task.task_id}">${task.task_key} — ${task.task_name}</option>`).join('');
        updateTaskMeta();
        form.hidden = false;
        message.hidden = true;
    } catch (error) {
        form.hidden = true;
        const detail = error instanceof TypeError
            ? 'The submission portal service is not responding. Start run_student_submission_portal.bat and keep its window open.'
            : error.message;
        showMessage(detail, 'error');
    } finally {
        button.disabled = false;
        button.textContent = 'Load my document tasks';
    }
});

taskSelect.addEventListener('change', updateTaskMeta);
fileInput.addEventListener('change', () => {
    document.getElementById('fileName').textContent = fileInput.files[0]?.name || 'Choose a PDF, Word or text document';
});

form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!fileInput.files[0]) return showMessage('Choose a document first.', 'error');
    const button = document.getElementById('submitButton');
    const body = new FormData();
    body.append('project_id', projectInput.value.trim());
    body.append('student_id', studentInput.value.trim());
    body.append('task_id', taskSelect.value);
    body.append('file', fileInput.files[0]);
    button.disabled = true;
    button.textContent = 'Submitting…';
    try {
        const response = await fetch('/api/submit', {method: 'POST', body});
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Submission failed.');
        showMessage(`Submitted successfully. ${payload.task_key} is now pending supervisor review (version ${payload.version}).`, 'success');
        form.reset();
        document.getElementById('fileName').textContent = 'Choose a PDF, Word or text document';
        updateTaskMeta();
    } catch (error) {
        const detail = error instanceof TypeError
            ? 'The submission portal service is not responding. Start run_student_submission_portal.bat and keep its window open.'
            : error.message;
        showMessage(detail, 'error');
    } finally {
        button.disabled = false;
        button.textContent = 'Submit for supervisor review';
    }
});

fetch('/api/health').then(response => response.json()).then(payload => {
    const status = document.getElementById('serviceStatus');
    const ok = payload.status === 'healthy';
    status.textContent = ok ? 'Scheduling service connected' : 'Scheduling service unavailable';
    status.className = `service-status ${ok ? 'ok' : 'bad'}`;
}).catch(() => {
    const status = document.getElementById('serviceStatus');
    status.textContent = 'Scheduling service unavailable';
    status.className = 'service-status bad';
});
