import { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8003';

function getErrorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return error.message || 'Supervisor allocation failed.';
}

function statusStyle(status) {
  if (status === 'Strong Expertise Match') {
    return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300';
  }
  if (status === 'Expertise Match') {
    return 'border-blue-500/40 bg-blue-500/10 text-blue-300';
  }
  if (status === 'Interest Match') {
    return 'border-purple-500/40 bg-purple-500/10 text-purple-300';
  }
  return 'border-amber-500/40 bg-amber-500/10 text-amber-300';
}

export default function SupervisorAllocationPanel({ workbookFile, selectedSolution }) {
  const [result, setResult] = useState(null);
  const [allocating, setAllocating] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const teams = selectedSolution?.teams ?? [];

  const allocateSupervisors = async () => {
    if (!workbookFile) {
      setErrorMessage('The cohort workbook is not available.');
      return;
    }
    const formData = new FormData();
    formData.append('file', workbookFile);
    setAllocating(true);
    setErrorMessage('');
    setResult(null);
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/supervisor-allocation/allocate`,
        formData
      );
      setResult(response.data.supervisor_allocation);
    } catch (error) {
      console.error('Supervisor allocation failed:', error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setAllocating(false);
    }
  };

  if (!selectedSolution) return null;

  return (
    <section className="mt-8 bg-slate-800/80 border border-slate-700 rounded-xl p-6">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5">
        <div>
          <h2 className="text-2xl font-bold text-white">Supervisor Allocation</h2>
          <p className="text-sm text-slate-400 mt-2 max-w-3xl">
            Assign supervisors to the projects in the selected team-formation solution using
            project-domain expertise, research interests and available supervisor capacity.
          </p>
        </div>
        <button
          type="button"
          onClick={allocateSupervisors}
          disabled={allocating}
          className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold disabled:opacity-40"
        >
          {allocating ? 'Allocating...' : 'Allocate Supervisors'}
        </button>
      </div>
      <div className="mt-5 border border-slate-700 bg-slate-900/60 rounded-lg p-4 text-xs text-slate-400">
        This is a downstream system feature and is separate from the evaluated
        multi-objective team-formation methodology.
      </div>
      {errorMessage && (
        <div className="mt-5 border border-red-500/40 bg-red-500/10 rounded-lg p-4 text-red-300">
          {errorMessage}
        </div>
      )}
      {result && (
        <div className="mt-7">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <SummaryCard label="Projects Assigned" value={result.summary.projects_assigned} />
            <SummaryCard label="Supervisors Used" value={result.summary.supervisors_used} />
            <SummaryCard
              label="Expertise Matches"
              value={result.summary.projects_with_expertise_match}
            />
            <SummaryCard
              label="No Domain Match"
              value={result.summary.projects_without_domain_match}
            />
          </div>
          <div className="space-y-5">
            {result.assignments.map((assignment) => {
              const team = teams.find((item) => item.project_id === assignment.project_id);
              return (
                <div
                  key={assignment.project_id}
                  className="bg-slate-900/70 border border-slate-700 rounded-xl p-5"
                >
                  <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                    <div>
                      <p className="text-xs font-mono text-indigo-400">
                        {assignment.project_id}
                      </p>
                      <h3 className="text-xl font-bold text-white">
                        {assignment.project_title}
                      </h3>
                      <p className="text-sm text-slate-400 mt-1">
                        Supervisor: <span className="text-white font-semibold">
                          {assignment.supervisor_name}
                        </span>{' '}
                        ({assignment.supervisor_id})
                      </p>
                    </div>
                    <span
                      className={`text-xs px-3 py-1.5 rounded-full border font-semibold ${statusStyle(
                        assignment.match_status
                      )}`}
                    >
                      {assignment.match_status}
                    </span>
                  </div>
                  {team && (
                    <div className="mt-5">
                      <p className="text-xs uppercase text-slate-500 mb-2">Assigned Team</p>
                      <div className="flex flex-wrap gap-2">
                        {team.students.map((student) => (
                          <span
                            key={student.student_id}
                            className="text-xs px-2 py-1 rounded bg-slate-800 border border-slate-700 text-slate-300"
                          >
                            {student.student_id}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-5">
                    <DomainGroup label="Project Domains" values={assignment.project_domains} />
                    <DomainGroup
                      label="Expertise Matches"
                      values={assignment.expertise_matches}
                      emptyText="No expertise-domain match"
                    />
                    <DomainGroup
                      label="Interest Matches"
                      values={assignment.interest_matches}
                      emptyText="No research-interest match"
                    />
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
                    <SmallMetric label="Current Load" value={assignment.current_load} />
                    <SmallMetric label="Maximum Teams" value={assignment.maximum_teams} />
                    <SmallMetric label="Projected Load" value={assignment.projected_load} />
                    <SmallMetric label="Remaining Capacity" value={assignment.remaining_capacity} />
                  </div>
                  <p className="text-sm text-slate-400 mt-5">{assignment.explanation}</p>
                </div>
              );
            })}
          </div>
          <div className="mt-6 border border-slate-700 bg-slate-900/60 rounded-lg p-4">
            <p className="text-sm font-semibold text-white">{result.algorithm}</p>
            <p className="text-xs text-slate-400 mt-2">{result.interpretation}</p>
            <p className="text-xs text-slate-500 mt-2">{result.research_scope}</p>
          </div>
        </div>
      )}
    </section>
  );
}

function SummaryCard({ label, value }) {
  return (
    <div className="bg-slate-900/70 border border-slate-700 rounded-xl p-4">
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className="text-2xl font-bold text-white mt-2">{value}</p>
    </div>
  );
}

function SmallMetric({ label, value }) {
  return (
    <div className="bg-slate-800/70 border border-slate-700 rounded-lg p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-lg font-semibold text-white mt-1">{value}</p>
    </div>
  );
}

function DomainGroup({ label, values, emptyText = 'None' }) {
  return (
    <div>
      <p className="text-xs uppercase text-slate-500 mb-2">{label}</p>
      {values?.length ? (
        <div className="flex flex-wrap gap-2">
          {values.map((value) => (
            <span
              key={value}
              className="text-xs px-2 py-1 rounded bg-slate-800 border border-slate-700 text-slate-300"
            >
              {value}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-500">{emptyText}</p>
      )}
    </div>
  );
}