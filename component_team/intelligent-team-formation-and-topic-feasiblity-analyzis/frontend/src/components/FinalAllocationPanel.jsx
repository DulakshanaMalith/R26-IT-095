import { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8003';

function getErrorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return error.message || 'The final allocation request could not be completed.';
}

export default function FinalAllocationPanel({ workbookFile, selectedSolution, supervisorAllocation, studentsPerTeam }) {
  const [savedAllocation, setSavedAllocation] = useState(null);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const saveFinalAllocation = async () => {
    if (!selectedSolution || !supervisorAllocation) {
      setErrorMessage('Select a Pareto solution and complete supervisor allocation first.');
      return;
    }
    setSaving(true);
    setErrorMessage('');
    try {
      const response = await axios.post(`${API_BASE_URL}/api/final-allocations`, {
        source_file_name: workbookFile?.name || null,
        students_per_team: Number(studentsPerTeam),
        optimizer: {
          algorithm: 'Heuristic-Seeded NSGA-II',
          optimizer_version: 'V3',
        },
        selected_solution: selectedSolution,
        supervisor_allocation: supervisorAllocation,
      });
      setSavedAllocation(response.data.allocation);
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
      const response = await axios.get(
        `${API_BASE_URL}/api/final-allocations/${savedAllocation.allocation_id}/export.${format}`,
        { responseType: 'blob' }
      );
      const contentDisposition = response.headers['content-disposition'] || '';
      const match = contentDisposition.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || `${savedAllocation.allocation_id}_final_team_allocation.${format}`;
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error(`${format.toUpperCase()} export failed:`, error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setDownloading('');
    }
  };

  return (
    <div className="mt-7 border border-emerald-500/30 bg-emerald-500/5 rounded-xl p-5">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h3 className="text-xl font-bold text-white">Confirm Final Allocation</h3>
          <p className="text-sm text-slate-400 mt-1 max-w-3xl">
            Save the selected team-project allocation together with its supervisor assignments as the official final allocation. PDF and Excel exports are generated from the saved database record.
          </p>
        </div>
        {!savedAllocation && (
          <button
            type="button"
            onClick={saveFinalAllocation}
            disabled={saving}
            className="px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold disabled:opacity-40"
          >
            {saving ? 'Saving...' : 'Save Final Allocation'}
          </button>
        )}
      </div>
      {errorMessage && (
        <div className="mt-4 border border-red-500/40 bg-red-500/10 rounded-lg p-4 text-red-300">
          {errorMessage}
        </div>
      )}
      {savedAllocation && (
        <div className="mt-5 border border-emerald-500/40 bg-emerald-500/10 rounded-lg p-4">
          <p className="font-semibold text-emerald-300">Final allocation saved successfully.</p>
          <p className="text-sm text-slate-300 mt-1">
            Allocation ID: <span className="font-mono font-bold text-white">{savedAllocation.allocation_id}</span>
          </p>
          <p className="text-xs text-slate-400 mt-2">
            {savedAllocation.student_count} students · {savedAllocation.project_count} teams · Solution {savedAllocation.solution_id}
          </p>
          <div className="flex flex-wrap gap-3 mt-4">
            <button
              type="button"
              onClick={() => downloadExport('pdf')}
              disabled={Boolean(downloading)}
              className="px-4 py-2 rounded-lg border border-slate-600 bg-slate-800 hover:bg-slate-700 text-white text-sm font-semibold disabled:opacity-40"
            >
              {downloading === 'pdf' ? 'Preparing PDF...' : 'Download PDF'}
            </button>
            <button
              type="button"
              onClick={() => downloadExport('xlsx')}
              disabled={Boolean(downloading)}
              className="px-4 py-2 rounded-lg border border-slate-600 bg-slate-800 hover:bg-slate-700 text-white text-sm font-semibold disabled:opacity-40"
            >
              {downloading === 'xlsx' ? 'Preparing Excel...' : 'Download Excel'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
