import { useState } from 'react';
import axios from 'axios';
import FinalAllocationPanel from './FinalAllocationPanel';
const API_BASE_URL = 'http://127.0.0.1:8003';
function getErrorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return error.message || 'Supervisor allocation failed.';
}
function statusStyle(status) {
  if (status === 'Strong Expertise Match') return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  if (status === 'Expertise Match') return 'border-blue-200 bg-blue-50 text-blue-800';
  if (status === 'Interest Match') return 'border-violet-200 bg-violet-50 text-violet-800';
  return 'border-amber-200 bg-amber-50 text-amber-800';
}
export default function SupervisorAllocationPanel({ workbookFile, selectedSolution, studentsPerTeam, onAllocated, onFinalized }) {
  const [result, setResult] = useState(null);
  const [allocating, setAllocating] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const teams = selectedSolution?.teams ?? [];
  const allocateSupervisors = async () => {
    if (!workbookFile) return setErrorMessage('The cohort workbook is not available.');
    const formData = new FormData();
    formData.append('file', workbookFile);
    formData.append('students_per_team', String(studentsPerTeam));
    setAllocating(true);
    setErrorMessage('');
    setResult(null);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/supervisor-allocation/allocate`, formData);
      setResult(response.data.supervisor_allocation);
      onAllocated?.(response.data.supervisor_allocation);
    } catch (error) {
      console.error('Supervisor allocation failed:', error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setAllocating(false);
    }
  };
  if (!selectedSolution) return null;
  return (
    <div className="border-t border-slate-100 p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-700 text-sm font-bold text-white">5</span><div><h2 className="text-lg font-bold text-slate-900">Supervisor Allocation</h2><p className="mt-1 max-w-3xl text-sm text-slate-600">Assign supervisors to the selected teams using project-domain expertise, research interests, hard capacity and workload.</p></div></div>
        <button type="button" onClick={allocateSupervisors} disabled={allocating} className="rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-800 disabled:opacity-40">{allocating ? 'Allocating...' : 'Allocate Supervisors'}</button>
      </div>
      <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">This is a downstream operational feature. It is separate from the evaluated two-objective NSGA-II team-formation methodology.</div>
      {errorMessage && <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{errorMessage}</div>}
      {result && (
        <div className="mt-6">
          <dl className="grid grid-cols-2 overflow-hidden rounded-xl border border-slate-200 lg:grid-cols-4"><Metric label="Projects Assigned" value={result.summary.projects_assigned} /><Metric label="Supervisors Used" value={result.summary.supervisors_used} bordered /><Metric label="Expertise Matches" value={result.summary.projects_with_expertise_match} bordered /><Metric label="No Domain Match" value={result.summary.projects_without_domain_match} bordered /></dl>
          <div className="mt-5 space-y-3">
            {result.assignments.map((assignment) => {
              const team = teams.find((item) => item.project_id === assignment.project_id);
              return (
                <details key={assignment.project_id} className="group overflow-hidden rounded-xl border border-slate-200 bg-white">
                  <summary className="flex cursor-pointer flex-col gap-3 px-5 py-4 hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between">
                    <div><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs text-blue-700">{assignment.project_id}</span><span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusStyle(assignment.match_status)}`}>{assignment.match_status}</span></div><h3 className="mt-1 text-base font-bold text-slate-900">{assignment.project_title}</h3><p className="mt-1 text-sm text-slate-600"><span className="font-semibold text-slate-800">{assignment.supervisor_name}</span> · {assignment.supervisor_id}</p></div>
                    <div className="flex items-center gap-4"><div className="text-right"><p className="text-xs text-slate-500">Projected load</p><p className="text-sm font-bold text-slate-900">{assignment.projected_load} / {assignment.maximum_teams}</p></div><span className="text-slate-400 transition group-open:rotate-180">⌄</span></div>
                  </summary>
                  <div className="border-t border-slate-100 p-5">
                    {team && <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Assigned students</p><p className="mt-2 text-sm text-slate-700">{team.students.map((student) => student.student_id).join(', ')}</p></div>}
                    <div className="mt-5 grid gap-5 lg:grid-cols-3"><DomainGroup label="Project Domains" values={assignment.project_domains} /><DomainGroup label="Expertise Matches" values={assignment.expertise_matches} emptyText="No expertise-domain match" /><DomainGroup label="Interest Matches" values={assignment.interest_matches} emptyText="No research-interest match" /></div>
                    <dl className="mt-5 grid grid-cols-2 overflow-hidden rounded-lg border border-slate-200 md:grid-cols-4"><SmallMetric label="Current Load" value={assignment.current_load} /><SmallMetric label="Maximum Teams" value={assignment.maximum_teams} bordered /><SmallMetric label="Projected Load" value={assignment.projected_load} bordered /><SmallMetric label="Remaining Capacity" value={assignment.remaining_capacity} bordered /></dl>
                    <p className="mt-5 text-sm text-slate-600">{assignment.explanation}</p>
                  </div>
                </details>
              );
            })}
          </div>
          <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3"><p className="text-sm font-semibold text-slate-800">{result.algorithm}</p><p className="mt-1 text-xs text-slate-600">{result.interpretation}</p><p className="mt-1 text-xs text-slate-500">{result.research_scope}</p></div>
          <FinalAllocationPanel workbookFile={workbookFile} selectedSolution={selectedSolution} supervisorAllocation={result} studentsPerTeam={studentsPerTeam} onFinalized={onFinalized} />
        </div>
      )}
    </div>
  );
}
function Metric({ label, value, bordered }) { return <div className={`px-4 py-3 ${bordered ? 'border-l border-slate-100' : ''}`}><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 text-xl font-bold text-slate-900">{value}</dd></div>; }
function SmallMetric({ label, value, bordered }) { return <div className={`px-3 py-3 ${bordered ? 'border-l border-slate-100' : ''}`}><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 text-base font-bold text-slate-900">{value}</dd></div>; }
function DomainGroup({ label, values, emptyText = 'None' }) {
  return <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>{values?.length ? <div className="mt-2 flex flex-wrap gap-2">{values.map((value) => <span key={value} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700">{value}</span>)}</div> : <p className="mt-2 text-xs text-slate-500">{emptyText}</p>}</div>;
}
