import { useMemo, useState } from 'react';
import axios from 'axios';
const API_BASE_URL = 'http://127.0.0.1:8003';
const percent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
function getErrorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return error.message || 'Technical coverage inspection failed.';
}
export default function TopicFeasibilityPanel({ workbookFile, selectedSolution, studentsPerTeam }) {
  const teams = useMemo(() => selectedSolution?.teams ?? [], [selectedSolution]);
  const defaultProjectId = teams[0]?.project_id ?? '';
  const [sourceProjectId, setSourceProjectId] = useState(defaultProjectId);
  const [targetProjectId, setTargetProjectId] = useState(defaultProjectId);
  const [result, setResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const sourceTeam = teams.find((team) => team.project_id === sourceProjectId) || teams[0] || null;
  const targetProject = teams.find((team) => team.project_id === targetProjectId) || teams[0] || null;
  const inspectTechnicalCoverage = async () => {
    if (!workbookFile) return setErrorMessage('The cohort workbook is not available.');
    if (!sourceTeam || !targetProject) return setErrorMessage('Please select a team and project.');
    const formData = new FormData();
    formData.append('file', workbookFile);
    formData.append('project_id', targetProject.project_id);
    formData.append('team_student_ids', sourceTeam.students.map((student) => student.student_id).join(','));
    formData.append('students_per_team', String(studentsPerTeam));
    setAnalyzing(true);
    setErrorMessage('');
    setResult(null);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/topic-feasibility/analyze`, formData);
      setResult(response.data.topic_feasibility);
    } catch (error) {
      console.error('Technical coverage inspection failed:', error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setAnalyzing(false);
    }
  };
  if (!selectedSolution || !teams.length) return null;
  return (
    <div className="border-t border-slate-100 p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-blue-200 bg-blue-50 text-sm font-bold text-blue-700">4A</span><div><div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-bold text-slate-900">Technical Coverage Inspection</h2><span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">Optional</span></div><p className="mt-1 max-w-3xl text-sm text-slate-600">Inspect requirement-level technical coverage for an existing team and approved project. Technical coverage was already considered during team formation; this view explains the result in detail.</p></div></div>
      </div>
      <div className="mt-5 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-xs text-blue-900"><span className="font-semibold">Decision-support inspection only.</span> It does not change the selected allocation, rerun NSGA-II, block supervisor allocation, or predict overall project success.</div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div><label className="mb-2 block text-sm font-semibold text-slate-700">Team to inspect</label><select value={sourceTeam?.project_id ?? ''} onChange={(event) => { setSourceProjectId(event.target.value); setResult(null); setErrorMessage(''); }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100">{teams.map((team) => <option key={team.project_id} value={team.project_id}>Team assigned to {team.project_id} — {team.project_title}</option>)}</select>{sourceTeam && <p className="mt-2 text-xs text-slate-500">Members: {sourceTeam.students.map((student) => student.student_id).join(', ')}</p>}</div>
        <div><label className="mb-2 block text-sm font-semibold text-slate-700">Project requirements to compare</label><select value={targetProject?.project_id ?? ''} onChange={(event) => { setTargetProjectId(event.target.value); setResult(null); setErrorMessage(''); }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100">{teams.map((team) => <option key={team.project_id} value={team.project_id}>{team.project_id} — {team.project_title}</option>)}</select></div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3"><button type="button" onClick={inspectTechnicalCoverage} disabled={analyzing} className="rounded-lg border border-blue-700 bg-white px-4 py-2.5 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-40">{analyzing ? 'Inspecting...' : 'Inspect Technical Coverage'}</button>{sourceTeam?.project_id === targetProject?.project_id && <p className="text-xs text-slate-500">Inspecting this team against its currently assigned project.</p>}</div>
      {errorMessage && <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{errorMessage}</div>}
      {result && <FeasibilityResult result={result} />}
    </div>
  );
}
function FeasibilityResult({ result }) {
  const gaps = result.requirements.filter((requirement) => requirement.status === 'Gap');
  return (
    <div className="mt-6 overflow-hidden rounded-xl border border-slate-200">
      <div className="flex flex-col gap-3 bg-slate-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-xs font-mono text-blue-700">{result.project.project_id}</p><h3 className="text-base font-bold text-slate-900">{result.project.project_title}</h3></div><span className={`w-fit rounded-full border px-3 py-1 text-xs font-semibold ${result.technical_deficit === 0 ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{result.status}</span></div>
      <div className="p-5">
        {result.team.is_remainder_team && <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900"><span className="font-semibold">Approved remainder team.</span> Target size is {result.team.expected_team_size}; this team contains {result.team.actual_team_size} student(s).</div>}
        {!result.team.team_size_matches_project && <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"><span className="font-semibold">Team size mismatch.</span> Project expects {result.team.expected_team_size} members but this team contains {result.team.actual_team_size}. Technical coverage is still shown for the current team.</div>}
        <dl className="grid grid-cols-2 overflow-hidden rounded-lg border border-slate-200 lg:grid-cols-4"><Metric label="Technical Coverage" value={percent(result.technical_coverage)} /><Metric label="Technical Deficit" value={percent(result.technical_deficit)} bordered /><Metric label="Requirements Covered" value={`${result.requirement_summary.covered_requirements} / ${result.requirement_summary.total_requirements}`} bordered /><Metric label="Technical Gaps" value={result.requirement_summary.gap_requirements} bordered /></dl>
        <div className="mt-5 overflow-x-auto rounded-lg border border-slate-200"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs text-slate-600"><tr><th className="px-3 py-2">Technology</th><th className="px-3 py-2">Min level</th><th className="px-3 py-2">Required</th><th className="px-3 py-2">Qualified</th><th className="px-3 py-2">Coverage</th><th className="px-3 py-2">Status</th></tr></thead><tbody>{result.requirements.map((requirement) => <tr key={requirement.technology} className="border-t border-slate-100"><td className="px-3 py-2 font-semibold text-slate-900">{requirement.technology}</td><td className="px-3 py-2 text-slate-700">{requirement.min_level}</td><td className="px-3 py-2 text-slate-700">{requirement.required_members}</td><td className="px-3 py-2 text-slate-700">{requirement.qualified_members}</td><td className="px-3 py-2 text-slate-700">{percent(requirement.coverage)}</td><td className="px-3 py-2"><span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${requirement.status === 'Covered' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'}`}>{requirement.status}</span></td></tr>)}</tbody></table></div>
        {gaps.length > 0 && <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4"><h4 className="text-sm font-bold text-red-900">Identified technical gaps</h4><ul className="mt-2 space-y-2 text-sm text-red-800">{gaps.map((requirement) => <li key={requirement.technology}><span className="font-semibold">{requirement.technology}:</span> requires {requirement.required_members} member(s) at level {requirement.min_level}+, but {requirement.qualified_members} qualify. Additional qualified members needed: {requirement.gap_members}.</li>)}</ul></div>}
        <p className="mt-5 text-xs text-slate-500">{result.interpretation.scope_note}</p>
      </div>
    </div>
  );
}
function Metric({ label, value, bordered }) { return <div className={`px-4 py-3 ${bordered ? 'border-l border-slate-100' : ''}`}><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 text-lg font-bold text-slate-900">{value}</dd></div>; }
