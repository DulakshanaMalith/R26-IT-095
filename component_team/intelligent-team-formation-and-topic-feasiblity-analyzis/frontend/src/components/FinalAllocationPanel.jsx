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
export default function FinalAllocationPanel({ workbookFile, selectedSolution, supervisorAllocation, studentsPerTeam, onFinalized }) {
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
    if (!selectedSolution || !supervisorAllocation) return setErrorMessage('Select an allocation and complete supervisor allocation first.');
    setSaving(true);
    setErrorMessage('');
    try {
      const payload = { source_file_name: workbookFile?.name || null, students_per_team: Number(studentsPerTeam), optimizer: { algorithm: 'Heuristic-Seeded NSGA-II', optimizer_version: 'V3' }, selected_solution: selectedSolution, supervisor_allocation: supervisorAllocation };
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
      onFinalized?.(response.data.allocation);
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
    if (!savedAllocation?.allocation_id || !revisionFile) return setErrorMessage('Choose the edited allocation revision workbook first.');
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
      onFinalized?.(response.data.allocation);
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
    <div className="mt-6 rounded-xl border border-slate-200 bg-white">
      <div className="flex flex-col gap-4 p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-700 text-sm font-bold text-white">6</span><div><h3 className="text-lg font-bold text-slate-900">Finalization & Revision</h3><p className="mt-1 max-w-3xl text-sm text-slate-600">Save the staff-confirmed allocation as the official ACTIVE record. Previous official allocations remain archived for traceability.</p></div></div>
        {!savedAllocation && <button type="button" onClick={saveFinalAllocation} disabled={saving} className="rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 disabled:opacity-40">{saving ? 'Saving...' : 'Save Final Allocation'}</button>}
      </div>
      {errorMessage && <div className="mx-5 mb-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{errorMessage}</div>}
      {savedAllocation && (
        <div className="border-t border-slate-100 p-5">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between"><div><div className="flex flex-wrap items-center gap-2"><span className="rounded-full border border-emerald-300 bg-white px-2.5 py-1 text-xs font-bold text-emerald-800">ACTIVE</span><span className="text-xs font-semibold text-emerald-900">Current official allocation</span></div><p className="mt-3 font-mono text-sm font-bold text-slate-900">{savedAllocation.allocation_id}</p><p className="mt-1 text-xs text-slate-600">Revision {savedAllocation.revision_number || 1} · {savedAllocation.allocation_source === 'MANUAL_REVISION' ? 'Staff-revised allocation' : 'Optimizer-selected allocation'} · {savedAllocation.student_count} students · {savedAllocation.project_count} teams</p>{savedAllocation.parent_allocation_id && <p className="mt-1 text-xs text-slate-500">Parent allocation: {savedAllocation.parent_allocation_id}</p>}</div></div>
            <div className="mt-4 flex flex-wrap gap-2"><button type="button" onClick={() => downloadExport('pdf')} disabled={Boolean(downloading)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40">{downloading === 'pdf' ? 'Preparing PDF...' : 'PDF Report'}</button><button type="button" onClick={() => downloadExport('xlsx')} disabled={Boolean(downloading)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40">{downloading === 'xlsx' ? 'Preparing Excel...' : 'Excel Report'}</button><button type="button" onClick={downloadEditableAllocation} disabled={Boolean(downloading) || savedAllocation.revision_enabled === false} className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900 hover:bg-amber-100 disabled:opacity-40">{downloading === 'editable' ? 'Preparing Workbook...' : 'Editable Allocation'}</button></div>
            <p className="mt-3 text-xs text-slate-600">PDF and Excel are reporting outputs. Use <span className="font-semibold text-amber-900">Editable Allocation</span> only for controlled staff revisions.</p>
          </div>
          {savedAllocation.revision_enabled !== false && (
            <div className="mt-5 rounded-xl border border-slate-200 bg-white">
              <div className="border-b border-slate-100 px-5 py-4"><h4 className="text-base font-bold text-slate-900">Revise Existing Allocation</h4><p className="mt-1 text-sm text-slate-600">Upload the edited allocation workbook. The backend validates structure and recalculates technical, preference and supervisor information before any new record is saved.</p></div>
              <div className="p-5"><div className="grid gap-4 lg:grid-cols-2"><div><label className="mb-2 block text-sm font-semibold text-slate-700">Edited allocation workbook</label><input type="file" accept=".xlsx" onChange={(event) => { setRevisionFile(event.target.files?.[0] || null); setRevisionPreview(null); }} className="block w-full rounded-lg border border-slate-300 bg-white text-sm text-slate-700 file:mr-4 file:border-0 file:border-r file:border-slate-200 file:bg-slate-50 file:px-4 file:py-2.5 file:font-semibold file:text-slate-700 hover:file:bg-slate-100" /></div><div><label className="mb-2 block text-sm font-semibold text-slate-700">Reason for change</label><input type="text" value={changeReason} onChange={(event) => setChangeReason(event.target.value)} placeholder="Example: coordinator-approved student swap" className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" /></div></div>
                <button type="button" onClick={validateRevision} disabled={!revisionFile || validatingRevision || confirmingRevision} className="mt-4 rounded-lg border border-amber-500 bg-white px-4 py-2.5 text-sm font-semibold text-amber-800 hover:bg-amber-50 disabled:opacity-40">{validatingRevision ? 'Validating...' : 'Validate Revised Allocation'}</button>
                {revisionPreview?.valid && <RevisionPreview preview={revisionPreview} confirmRevision={confirmRevision} confirmingRevision={confirmingRevision} />}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
function RevisionPreview({ preview, confirmRevision, confirmingRevision }) {
  const original = preview.changes?.original_metrics || {};
  const revised = preview.changes?.revised_metrics || {};
  return (
    <div className="mt-5 overflow-hidden rounded-xl border border-blue-200">
      <div className="flex flex-col gap-3 bg-blue-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-bold text-blue-900">Revision validation passed</p><p className="mt-1 text-xs text-blue-800">If confirmed, this becomes Revision {preview.next_revision_number} and the current allocation becomes ARCHIVED.</p></div><button type="button" onClick={confirmRevision} disabled={confirmingRevision} className="rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-40">{confirmingRevision ? 'Saving Revision...' : 'Confirm Revised Allocation'}</button></div>
      <div className="p-4"><dl className="grid grid-cols-2 overflow-hidden rounded-lg border border-slate-200 lg:grid-cols-4"><Metric label="Moved Students" value={preview.changes?.moved_student_count ?? 0} /><Metric label="Supervisor Changes" value={preview.changes?.changed_supervisor_count ?? 0} bordered /><Metric label="Technical Coverage" value={percent(preview.candidate?.technical_requirement_coverage)} bordered /><Metric label="Preference Satisfaction" value={percent(preview.candidate?.preference_satisfaction)} bordered /></dl>
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs text-slate-600"><tr><th className="px-3 py-2">Measure</th><th className="px-3 py-2">Original</th><th className="px-3 py-2">Revised</th></tr></thead><tbody><ComparisonRow label="Technical coverage" original={percent(original.technical_requirement_coverage)} revised={percent(revised.technical_requirement_coverage)} /><ComparisonRow label="Preference satisfaction" original={percent(original.preference_satisfaction)} revised={percent(revised.preference_satisfaction)} /></tbody></table></div>
        {(preview.warnings || []).map((warning) => <p key={warning} className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">Warning: {warning}</p>)}
      </div>
    </div>
  );
}
function Metric({ label, value, bordered }) { return <div className={`px-3 py-3 ${bordered ? 'border-l border-slate-100' : ''}`}><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 text-lg font-bold text-slate-900">{value}</dd></div>; }
function ComparisonRow({ label, original, revised }) { return <tr className="border-t border-slate-100"><td className="px-3 py-2 font-semibold text-slate-800">{label}</td><td className="px-3 py-2 text-slate-700">{original}</td><td className="px-3 py-2 font-semibold text-slate-900">{revised}</td></tr>; }
