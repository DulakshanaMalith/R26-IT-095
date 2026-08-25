import { useState } from 'react';
import axios from 'axios';
const API_BASE_URL = 'http://127.0.0.1:8003';
const percent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
function getErrorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return error.message || 'The final allocation request could not be completed.';
}
function downloadBlob(response, fallbackName) {
  const contentDisposition = response.headers['content-disposition'] || '';
  const match = contentDisposition.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] || fallbackName;
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
export default function FinalAllocationPanel({ workbookFile, selectedSolution, supervisorAllocation, studentsPerTeam }) {
  const [savedAllocation, setSavedAllocation] = useState(null);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [revisionFile, setRevisionFile] = useState(null);
  const [changeReason, setChangeReason] = useState('');
  const [revisionPreview, setRevisionPreview] = useState(null);
  const [validatingRevision, setValidatingRevision] = useState(false);
  const [confirmingRevision, setConfirmingRevision] = useState(false);
  const saveFinalAllocation = async () => {
    if (!selectedSolution || !supervisorAllocation) {
      setErrorMessage('Select a Pareto solution and complete supervisor allocation first.');
      return;
    }
    setSaving(true);
    setErrorMessage('');
    try {
      const payload = {
        source_file_name: workbookFile?.name || null,
        students_per_team: Number(studentsPerTeam),
        optimizer: { algorithm: 'Heuristic-Seeded NSGA-II', optimizer_version: 'V3' },
        selected_solution: selectedSolution,
        supervisor_allocation: supervisorAllocation,
      };
      let response;
      if (workbookFile) {
        const formData = new FormData();
        formData.append('payload_json', JSON.stringify(payload));
        formData.append('file', workbookFile);
        response = await axios.post(`${API_BASE_URL}/api/final-allocations/with-source`, formData);
      } else {
        response = await axios.post(`${API_BASE_URL}/api/final-allocations`, payload);
      }
      setSavedAllocation(response.data.allocation);
      setRevisionPreview(null);
      setRevisionFile(null);
      setChangeReason('');
    } catch (error) {
      console.error('Final allocation save failed:', error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };
  const downloadExport = async (format) => {
    if (!savedAllocation?.allocation_id) return;
    setDownloading(format);
    setErrorMessage('');
    try {
      const response = await axios.get(`${API_BASE_URL}/api/final-allocations/${savedAllocation.allocation_id}/export.${format}`, { responseType: 'blob' });
      downloadBlob(response, `${savedAllocation.allocation_id}_final_team_allocation.${format}`);
    } catch (error) {
      console.error(`${format.toUpperCase()} export failed:`, error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setDownloading('');
    }
  };
  const downloadEditableAllocation = async () => {
    if (!savedAllocation?.allocation_id) return;
    setDownloading('editable');
    setErrorMessage('');
    try {
      const response = await axios.get(`${API_BASE_URL}/api/final-allocations/${savedAllocation.allocation_id}/editable.xlsx`, { responseType: 'blob' });
      downloadBlob(response, `${savedAllocation.allocation_id}_editable_allocation_revision.xlsx`);
    } catch (error) {
      console.error('Editable allocation download failed:', error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setDownloading('');
    }
  };
  const validateRevision = async () => {
    if (!savedAllocation?.allocation_id || !revisionFile) {
      setErrorMessage('Choose the edited allocation revision workbook first.');
      return;
    }
    setValidatingRevision(true);
    setErrorMessage('');
    setRevisionPreview(null);
    try {
      const formData = new FormData();
      formData.append('parent_allocation_id', savedAllocation.allocation_id);
      formData.append('file', revisionFile);
      const response = await axios.post(`${API_BASE_URL}/api/final-allocations/revisions/validate`, formData);
      setRevisionPreview(response.data);
    } catch (error) {
      console.error('Revision validation failed:', error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setValidatingRevision(false);
    }
  };
  const confirmRevision = async () => {
    if (!savedAllocation?.allocation_id || !revisionFile || !revisionPreview?.valid) return;
    setConfirmingRevision(true);
    setErrorMessage('');
    try {
      const formData = new FormData();
      formData.append('parent_allocation_id', savedAllocation.allocation_id);
      formData.append('change_reason', changeReason.trim());
      formData.append('file', revisionFile);
      const response = await axios.post(`${API_BASE_URL}/api/final-allocations/revisions/confirm`, formData);
      setSavedAllocation(response.data.allocation);
      setRevisionFile(null);
      setRevisionPreview(null);
      setChangeReason('');
    } catch (error) {
      console.error('Revision confirmation failed:', error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setConfirmingRevision(false);
    }
  };
  return (
    <div className="mt-7 border border-emerald-500/30 bg-emerald-500/5 rounded-xl p-5">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h3 className="text-xl font-bold text-white">Confirm Final Allocation</h3>
          <p className="text-sm text-slate-400 mt-1 max-w-3xl">Save the selected team-project allocation and supervisor assignments as the official ACTIVE allocation. The source workbook is stored as normalized reference data so later staff revisions can be safely recalculated and validated.</p>
        </div>
        {!savedAllocation && (
          <button type="button" onClick={saveFinalAllocation} disabled={saving} className="px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold disabled:opacity-40">
            {saving ? 'Saving...' : 'Save Final Allocation'}
          </button>
        )}
      </div>
      {errorMessage && <div className="mt-4 border border-red-500/40 bg-red-500/10 rounded-lg p-4 text-red-300">{errorMessage}</div>}
      {savedAllocation && (
        <div className="mt-5 space-y-5">
          <div className="border border-emerald-500/40 bg-emerald-500/10 rounded-lg p-4">
            <p className="font-semibold text-emerald-300">Official allocation is ACTIVE.</p>
            <p className="text-sm text-slate-300 mt-1">Allocation ID: <span className="font-mono font-bold text-white">{savedAllocation.allocation_id}</span></p>
            <p className="text-xs text-slate-400 mt-2">Revision {savedAllocation.revision_number || 1} · {savedAllocation.allocation_source === 'MANUAL_REVISION' ? 'Staff-revised allocation' : 'Optimizer-selected allocation'} · {savedAllocation.student_count} students · {savedAllocation.project_count} teams</p>
            {savedAllocation.parent_allocation_id && <p className="text-xs text-slate-500 mt-1">Parent allocation: {savedAllocation.parent_allocation_id}</p>}
            <div className="flex flex-wrap gap-3 mt-4">
              <button type="button" onClick={() => downloadExport('pdf')} disabled={Boolean(downloading)} className="px-4 py-2 rounded-lg border border-slate-600 bg-slate-800 hover:bg-slate-700 text-white text-sm font-semibold disabled:opacity-40">{downloading === 'pdf' ? 'Preparing PDF...' : 'Download PDF Report'}</button>
              <button type="button" onClick={() => downloadExport('xlsx')} disabled={Boolean(downloading)} className="px-4 py-2 rounded-lg border border-slate-600 bg-slate-800 hover:bg-slate-700 text-white text-sm font-semibold disabled:opacity-40">{downloading === 'xlsx' ? 'Preparing Excel...' : 'Download Excel Report'}</button>
              <button type="button" onClick={downloadEditableAllocation} disabled={Boolean(downloading) || savedAllocation.revision_enabled === false} className="px-4 py-2 rounded-lg border border-amber-500/50 bg-amber-500/10 hover:bg-amber-500/20 text-amber-200 text-sm font-semibold disabled:opacity-40">{downloading === 'editable' ? 'Preparing Editable Workbook...' : 'Download Editable Allocation'}</button>
            </div>
            <p className="text-xs text-slate-500 mt-3">PDF and Excel Report are read-only reporting outputs. Use only <span className="text-amber-300 font-semibold">Download Editable Allocation</span> when staff need to make a controlled manual revision.</p>
          </div>
          {savedAllocation.revision_enabled !== false && (
            <div className="border border-amber-500/30 bg-amber-500/5 rounded-xl p-5">
              <h4 className="text-lg font-bold text-white">Upload Revised Allocation</h4>
              <p className="text-sm text-slate-400 mt-1 max-w-3xl">Edit only the permitted fields in the downloaded editable workbook, then upload it here. The backend validates every student, project, team size and supervisor capacity and recalculates technical and preference metrics before anything is saved.</p>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
                <div>
                  <label className="block text-sm font-semibold text-slate-300 mb-2">Edited Allocation Workbook</label>
                  <input type="file" accept=".xlsx" onChange={(event) => { setRevisionFile(event.target.files?.[0] || null); setRevisionPreview(null); }} className="block w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-slate-700 file:text-white hover:file:bg-slate-600" />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-slate-300 mb-2">Reason for Change</label>
                  <input type="text" value={changeReason} onChange={(event) => setChangeReason(event.target.value)} placeholder="Example: coordinator-approved student swap" className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-white" />
                </div>
              </div>
              <button type="button" onClick={validateRevision} disabled={!revisionFile || validatingRevision || confirmingRevision} className="mt-4 px-5 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold disabled:opacity-40">{validatingRevision ? 'Validating Revision...' : 'Validate Revised Allocation'}</button>
              {revisionPreview?.valid && (
                <div className="mt-5 border border-sky-500/30 bg-sky-500/5 rounded-lg p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-sky-300">Revision validation passed.</p>
                      <p className="text-xs text-slate-400 mt-1">If confirmed, this becomes Revision {revisionPreview.next_revision_number} and the current allocation becomes ARCHIVED.</p>
                    </div>
                    <button type="button" onClick={confirmRevision} disabled={confirmingRevision} className="px-5 py-2.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold disabled:opacity-40">{confirmingRevision ? 'Saving Revision...' : 'Confirm Revised Allocation'}</button>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                    <Metric label="Moved Students" value={revisionPreview.changes?.moved_student_count ?? 0} />
                    <Metric label="Supervisor Changes" value={revisionPreview.changes?.changed_supervisor_count ?? 0} />
                    <Metric label="Technical Coverage" value={percent(revisionPreview.candidate?.technical_requirement_coverage)} />
                    <Metric label="Preference Satisfaction" value={percent(revisionPreview.candidate?.preference_satisfaction)} />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-xs text-slate-400">
                    <div className="bg-slate-900/60 rounded-lg p-3">Original: Technical {percent(revisionPreview.changes?.original_metrics?.technical_requirement_coverage)} · Preference {percent(revisionPreview.changes?.original_metrics?.preference_satisfaction)}</div>
                    <div className="bg-slate-900/60 rounded-lg p-3">Revised: Technical {percent(revisionPreview.changes?.revised_metrics?.technical_requirement_coverage)} · Preference {percent(revisionPreview.changes?.revised_metrics?.preference_satisfaction)}</div>
                  </div>
                  {(revisionPreview.warnings || []).map((warning) => <p key={warning} className="text-xs text-amber-300 mt-3">Warning: {warning}</p>)}
                </div>
              )}
            </div>
          )}
          <div className="border border-slate-700 bg-slate-900/60 rounded-lg p-4">
            <p className="text-sm font-semibold text-slate-200">Integration guarantee</p>
            <p className="text-xs text-slate-400 mt-1">Other components should retrieve current official teams from <span className="font-mono text-sky-300">GET /api/final-allocations/active/teams</span> or supervisor-specific groups from <span className="font-mono text-sky-300">GET /api/final-allocations/active/supervisors/{'{supervisor_id}'}/groups</span>. After a revision is confirmed, these endpoints automatically return the new ACTIVE revision.</p>
          </div>
        </div>
      )}
    </div>
  );
}
function Metric({ label, value }) {
  return <div className="bg-slate-900/70 border border-slate-700 rounded-lg p-3"><p className="text-xs text-slate-500">{label}</p><p className="text-lg font-bold text-white mt-1">{value}</p></div>;
}
