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
    if (!workbookFile) {
      setErrorMessage('The cohort workbook is not available.');
      return;
    }
    if (!sourceTeam || !targetProject) {
      setErrorMessage('Please select a team and project.');
      return;
    }
    const studentIds = sourceTeam.students.map((student) => student.student_id);
    const formData = new FormData();
    formData.append('file', workbookFile);
    formData.append('project_id', targetProject.project_id);
    formData.append('team_student_ids', studentIds.join(','));
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
    <section className="mt-8 bg-slate-800/80 border border-slate-700 rounded-xl p-6">
      <div className="mb-6">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-2xl font-bold text-white">Technical Coverage Inspection</h2>
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold border border-indigo-500/40 bg-indigo-500/10 text-indigo-300">
            Optional
          </span>
        </div>
        <p className="text-sm text-slate-400 mt-2 max-w-3xl">
          Inspect the requirement-level technical coverage of an existing team against an approved project or topic. Technical requirement coverage has already been considered during team formation, so this inspection provides a detailed explanation of that technical fit.
        </p>
        <div className="mt-4 border border-slate-600 bg-slate-900/60 rounded-lg p-4">
          <p className="text-sm font-semibold text-slate-200">Decision-support inspection only</p>
          <p className="text-xs text-slate-400 mt-1">
            This step is optional. It does not change the selected team allocation, rerun NSGA-II, block supervisor allocation, or predict overall project success. Supervisor allocation can be performed independently.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div>
          <label className="block text-sm font-semibold text-slate-300 mb-2">
            Team to Inspect
          </label>
          <select
            value={sourceTeam?.project_id ?? ''}
            onChange={(event) => {
              setSourceProjectId(event.target.value);
              setResult(null);
              setErrorMessage('');
            }}
            className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white"
          >
            {teams.map((team) => (
              <option key={team.project_id} value={team.project_id}>
                Team assigned to {team.project_id} — {team.project_title}
              </option>
            ))}
          </select>
          {sourceTeam && (
            <div className="mt-3 flex flex-wrap gap-2">
              {sourceTeam.students.map((student) => (
                <span
                  key={student.student_id}
                  className="text-xs px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-300"
                >
                  {student.student_id}
                </span>
              ))}
            </div>
          )}
        </div>
        <div>
          <label className="block text-sm font-semibold text-slate-300 mb-2">
            Project Requirements to Compare
          </label>
          <select
            value={targetProject?.project_id ?? ''}
            onChange={(event) => {
              setTargetProjectId(event.target.value);
              setResult(null);
              setErrorMessage('');
            }}
            className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white"
          >
            {teams.map((team) => (
              <option key={team.project_id} value={team.project_id}>
                {team.project_id} — {team.project_title}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={inspectTechnicalCoverage}
          disabled={analyzing}
          className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold disabled:opacity-40"
        >
          {analyzing ? 'Inspecting...' : 'Inspect Technical Coverage'}
        </button>
        {sourceTeam?.project_id === targetProject?.project_id && (
          <p className="text-xs text-slate-500">
            Inspecting this team against its currently assigned project.
          </p>
        )}
      </div>
      {errorMessage && (
        <div className="mt-5 border border-red-500/40 bg-red-500/10 rounded-lg p-4 text-red-300">
          {errorMessage}
        </div>
      )}
      {result && <FeasibilityResult result={result} />}
    </section>
  );
}
function FeasibilityResult({ result }) {
  const gapRequirements = result.requirements.filter((requirement) => requirement.status === 'Gap');
  return (
    <div className="mt-8">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
        <div>
          <p className="text-xs font-mono text-indigo-400">{result.project.project_id}</p>
          <h3 className="text-xl font-bold text-white">{result.project.project_title}</h3>
          <p className="text-xs text-slate-500 mt-1">Detailed technical requirement coverage</p>
        </div>
        <span
          className={`px-3 py-1.5 rounded-full text-xs font-bold border ${
            result.technical_deficit === 0
              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
              : 'border-amber-500/40 bg-amber-500/10 text-amber-300'
          }`}
        >
          {result.status}
        </span>
      </div>
      {result.team.is_remainder_team && (
        <div className="mb-6 border border-indigo-500/40 bg-indigo-500/10 rounded-lg p-4">
          <p className="font-semibold text-indigo-300">Approved Remainder Team</p>
          <p className="text-sm text-slate-300 mt-1">
            The cohort target is {result.team.expected_team_size} students per team, and this is the permitted remainder team containing {result.team.actual_team_size} student(s).
          </p>
        </div>
      )}
      {!result.team.team_size_matches_project && (
        <div className="mb-6 border border-amber-500/40 bg-amber-500/10 rounded-lg p-4">
          <p className="font-semibold text-amber-300">Team Size Mismatch</p>
          <p className="text-sm text-slate-300 mt-1">
            This project expects {result.team.expected_team_size} members, but the selected team currently contains {result.team.actual_team_size}.
          </p>
          <p className="text-xs text-slate-400 mt-2">
            Technical coverage is still calculated for the current team. This result does not mean that the project's team size requirement has been satisfied.
          </p>
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-7">
        <MetricCard label="Technical Coverage" value={percent(result.technical_coverage)} />
        <MetricCard label="Technical Deficit" value={percent(result.technical_deficit)} />
        <MetricCard
          label="Requirements Covered"
          value={`${result.requirement_summary.covered_requirements} / ${result.requirement_summary.total_requirements}`}
        />
        <MetricCard
          label="Technical Gaps"
          value={result.requirement_summary.gap_requirements}
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-left text-slate-400">
              <th className="py-3 pr-4">Technology</th>
              <th className="py-3 pr-4">Min Level</th>
              <th className="py-3 pr-4">Required</th>
              <th className="py-3 pr-4">Qualified</th>
              <th className="py-3 pr-4">Coverage</th>
              <th className="py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {result.requirements.map((requirement) => (
              <tr key={requirement.technology} className="border-b border-slate-800">
                <td className="py-3 pr-4 font-semibold text-white">
                  {requirement.technology}
                </td>
                <td className="py-3 pr-4">{requirement.min_level}</td>
                <td className="py-3 pr-4">{requirement.required_members}</td>
                <td className="py-3 pr-4">{requirement.qualified_members}</td>
                <td className="py-3 pr-4">{percent(requirement.coverage)}</td>
                <td className="py-3">
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${
                      requirement.status === 'Covered'
                        ? 'bg-emerald-500/10 text-emerald-300'
                        : 'bg-red-500/10 text-red-300'
                    }`}
                  >
                    {requirement.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {gapRequirements.length > 0 && (
        <div className="mt-7">
          <h4 className="font-bold text-white mb-3">Identified Technical Gaps</h4>
          <div className="space-y-3">
            {gapRequirements.map((requirement) => (
              <div
                key={requirement.technology}
                className="border border-red-500/30 bg-red-500/5 rounded-lg p-4"
              >
                <p className="font-semibold text-red-300">{requirement.technology}</p>
                <p className="text-sm text-slate-400 mt-1">
                  Requires {requirement.required_members} member(s) at level{' '}
                  {requirement.min_level} or above, but only{' '}
                  {requirement.qualified_members} currently qualify.
                </p>
                <p className="text-xs text-slate-500 mt-2">
                  Additional qualified members needed: {requirement.gap_members}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="mt-7 border border-slate-700 bg-slate-900/60 rounded-lg p-4 text-xs text-slate-400">
        <p>{result.interpretation.scope_note}</p>
        <p className="mt-2">
          This inspection is explanatory only. It does not modify the selected allocation or control whether supervisor allocation can proceed.
        </p>
      </div>
    </div>
  );
}
function MetricCard({ label, value }) {
  return (
    <div className="bg-slate-900/70 border border-slate-700 rounded-xl p-4">
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className="text-2xl font-bold text-white mt-2">{value}</p>
    </div>
  );
}