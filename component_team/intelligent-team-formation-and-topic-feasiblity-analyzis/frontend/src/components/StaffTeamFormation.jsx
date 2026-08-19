import { useMemo, useState } from 'react';
import axios from 'axios';
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import TopicFeasibilityPanel from './TopicFeasibilityPanel';

const API_BASE_URL = 'http://127.0.0.1:8003';

const percent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;

function getErrorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(', ');
  return error.message || 'The request could not be completed.';
}

function roleStyle(role) {
  if (role === 'Technical-oriented endpoint') {
    return 'border-blue-500/40 bg-blue-500/10 text-blue-300';
  }
  if (role === 'Preference-oriented endpoint') {
    return 'border-purple-500/40 bg-purple-500/10 text-purple-300';
  }
  return 'border-amber-500/40 bg-amber-500/10 text-amber-300';
}

export default function StaffTeamFormation() {
  const [file, setFile] = useState(null);
  const [validation, setValidation] = useState(null);
  const [result, setResult] = useState(null);
  const [selectedSolutionId, setSelectedSolutionId] = useState(null);
  const [validating, setValidating] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const solutions = useMemo(
    () => result?.team_formation?.solutions ?? [],
    [result]
  );

  const selectedSolution = useMemo(() => {
    if (!solutions.length) return null;
    return (
      solutions.find((solution) => solution.solution_id === selectedSolutionId) ||
      solutions[0]
    );
  }, [solutions, selectedSolutionId]);

  const paretoData = useMemo(
    () =>
      solutions.map((solution) => ({
        solutionId: solution.solution_id,
        role: solution.role,
        technicalDeficit: solution.technical_requirement_deficit,
        preferenceDissatisfaction: solution.preference_dissatisfaction,
      })),
    [solutions]
  );

  const resetResults = () => {
    setValidation(null);
    setResult(null);
    setSelectedSolutionId(null);
    setErrorMessage('');
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;
    setFile(selectedFile);
    resetResults();
  };

  const buildFormData = () => {
    const formData = new FormData();
    formData.append('file', file);
    return formData;
  };

  const validateWorkbook = async () => {
    if (!file) {
      setErrorMessage('Please select an Excel workbook first.');
      return;
    }

    setValidating(true);
    setErrorMessage('');
    setResult(null);
    setSelectedSolutionId(null);

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/cohort/validate`,
        buildFormData()
      );
      setValidation(response.data);
    } catch (error) {
      console.error('Workbook validation failed:', error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setValidating(false);
    }
  };

  const optimizeTeams = async () => {
    if (!file) {
      setErrorMessage('Please select an Excel workbook first.');
      return;
    }

    setOptimizing(true);
    setErrorMessage('');

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/cohort/optimize`,
        buildFormData()
      );

      setResult(response.data);
      setValidation(response.data.validation);

      const returnedSolutions = response.data.team_formation?.solutions ?? [];
      setSelectedSolutionId(returnedSolutions[0]?.solution_id ?? null);
    } catch (error) {
      console.error('Team formation failed:', error);
      const detail = error.response?.data?.detail;
      if (detail?.validation) setValidation(detail.validation);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setOptimizing(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white">Intelligent Team Formation</h1>
        <p className="text-slate-400 mt-2 max-w-3xl">
          Staff-side decision support for allocating students to approved projects
          using technical requirement coverage and student project preference as
          separate Pareto objectives.
        </p>
      </div>

      <section className="bg-slate-800/80 border border-slate-700 rounded-xl p-6 shadow-lg">
        <div className="flex flex-col lg:flex-row lg:items-end gap-4">
          <div className="flex-1">
            <label className="block text-sm font-semibold text-slate-300 mb-2">
              Cohort Workbook
            </label>
            <input
              type="file"
              accept=".xlsx"
              onChange={handleFileChange}
              className="block w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
            />
            <p className="text-xs text-slate-500 mt-2">
              Upload the staff workbook containing Students, Preferences, Projects and
              ProjectRequirements.
            </p>
          </div>

          <button
            type="button"
            onClick={validateWorkbook}
            disabled={!file || validating || optimizing}
            className="px-5 py-2.5 rounded-lg border border-slate-600 bg-slate-700 hover:bg-slate-600 text-white disabled:opacity-40"
          >
            {validating ? 'Validating...' : 'Validate Workbook'}
          </button>

          <button
            type="button"
            onClick={optimizeTeams}
            disabled={
              !file ||
              validating ||
              optimizing ||
              (validation && validation.valid === false)
            }
            className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold disabled:opacity-40"
          >
            {optimizing ? 'Running V3...' : 'Run Team Formation'}
          </button>
        </div>

        {errorMessage && (
          <div className="mt-5 border border-red-500/40 bg-red-500/10 rounded-lg p-4 text-red-300">
            {errorMessage}
          </div>
        )}
      </section>

      {validation && <ValidationPanel validation={validation} />}

      {result && (
        <>
          <section className="mt-6 bg-slate-800/80 border border-slate-700 rounded-xl p-6">
            <div className="flex flex-col lg:flex-row lg:justify-between gap-5">
              <div>
                <h2 className="text-xl font-bold text-white">Pareto Decision Support</h2>
                <p className="text-sm text-slate-400 mt-1">
                  No solution is automatically selected. Compare technical coverage
                  against student preference satisfaction.
                </p>
              </div>

              <div className="text-sm text-slate-400">
                <p>
                  <strong className="text-white">
                    {result.team_formation.optimizer.algorithm}
                  </strong>
                </p>
                <p>Version: {result.team_formation.optimizer.optimizer_version}</p>
                <p>Pareto points: {result.team_formation.solution_count}</p>
              </div>
            </div>

            <div className="mt-6 h-80 w-full min-w-0 bg-slate-900/70 border border-slate-700 rounded-xl p-4">
              <ResponsiveContainer
                width="100%"
                height="100%"
                minWidth={0}
                minHeight={0}
                initialDimension={{ width: 900, height: 280 }}
              >
                <ScatterChart margin={{ top: 15, right: 25, bottom: 25, left: 45 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    type="number"
                    dataKey="technicalDeficit"
                    name="Technical Deficit"
                    domain={[0, 'auto']}
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    label={{
                      value: 'Technical Requirement Deficit',
                      position: 'insideBottom',
                      offset: -12,
                      fill: '#94a3b8',
                    }}
                  />
                  <YAxis
                    type="number"
                    dataKey="preferenceDissatisfaction"
                    name="Preference Dissatisfaction"
                    domain={[0, 'auto']}
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    label={{
                      value: 'Preference Dissatisfaction',
                      angle: -90,
                      position: 'insideLeft',
                      offset: -30,
                      fill: '#94a3b8',
                    }}
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: '3 3' }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const point = payload[0].payload;
                      return (
                        <div className="bg-slate-950 border border-slate-700 rounded-lg p-3 text-xs shadow-xl">
                          <p className="font-bold text-white">
                            Solution {point.solutionId}
                          </p>
                          <p className="text-slate-400">{point.role}</p>
                          <p className="mt-2">
                            Technical deficit:{' '}
                            {Number(point.technicalDeficit).toFixed(4)}
                          </p>
                          <p>
                            Preference dissatisfaction:{' '}
                            {Number(point.preferenceDissatisfaction).toFixed(4)}
                          </p>
                        </div>
                      );
                    }}
                  />
                  <Scatter
                    data={paretoData}
                    fill="#818cf8"
                    onClick={(point) => setSelectedSolutionId(point.solutionId)}
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
              {solutions.map((solution) => {
                const selected = selectedSolution?.solution_id === solution.solution_id;
                return (
                  <button
                    key={solution.solution_id}
                    type="button"
                    onClick={() => setSelectedSolutionId(solution.solution_id)}
                    className={`text-left rounded-xl border p-4 transition ${
                      selected
                        ? 'border-indigo-400 bg-indigo-500/10'
                        : 'border-slate-700 bg-slate-900/60 hover:border-slate-500'
                    }`}
                  >
                    <div className="flex justify-between gap-2">
                      <p className="font-bold text-white">
                        Solution {solution.solution_id}
                      </p>
                      <span
                        className={`text-[10px] px-2 py-1 rounded-full border ${roleStyle(
                          solution.role
                        )}`}
                      >
                        {solution.role}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 mt-4">
                      <div>
                        <p className="text-xs text-slate-500">Technical Coverage</p>
                        <p className="text-lg font-bold">
                          {percent(solution.technical_requirement_coverage)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">
                          Preference Satisfaction
                        </p>
                        <p className="text-lg font-bold">
                          {percent(solution.preference_satisfaction)}
                        </p>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          {selectedSolution && (
            <section className="mt-6">
              <div className="mb-5">
                <h2 className="text-2xl font-bold text-white">
                  Solution {selectedSolution.solution_id}
                </h2>
                <p className="text-slate-400 text-sm mt-1">{selectedSolution.role}</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                <MetricCard
                  label="Technical Coverage"
                  value={percent(selectedSolution.technical_requirement_coverage)}
                />
                <MetricCard
                  label="Technical Deficit"
                  value={percent(selectedSolution.technical_requirement_deficit)}
                />
                <MetricCard
                  label="Preference Satisfaction"
                  value={percent(selectedSolution.preference_satisfaction)}
                />
                <MetricCard
                  label="Preference Dissatisfaction"
                  value={percent(selectedSolution.preference_dissatisfaction)}
                />
              </div>

              <div className="space-y-6">
                {selectedSolution.teams.map((team) => (
                  <TeamCard key={team.project_id} team={team} />
                ))}
              </div>

              <TopicFeasibilityPanel
                key={selectedSolution.solution_id}
                workbookFile={file}
                selectedSolution={selectedSolution}
              />

              <div className="mt-6 bg-slate-900/60 border border-slate-700 rounded-lg p-4 text-xs text-slate-400">
                {result.team_formation.interpretation.allocation_count_note}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function ValidationPanel({ validation }) {
  const summaryItems = [
    ['Students', validation.summary?.students],
    ['Projects', validation.summary?.projects],
    ['Supervisors', validation.summary?.supervisors],
    ['Errors', validation.summary?.errors],
    ['Warnings', validation.summary?.warnings],
  ];

  return (
    <section className="mt-6 bg-slate-800/80 border border-slate-700 rounded-xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h2 className="text-xl font-bold text-white">Workbook Validation</h2>
          <p className="text-sm text-slate-400">Input integrity check before optimization.</p>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-xs font-bold border ${
            validation.valid
              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
              : 'border-red-500/40 bg-red-500/10 text-red-300'
          }`}
        >
          {validation.valid ? 'VALID' : 'INVALID'}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {summaryItems.map(([label, value]) => (
          <div
            key={label}
            className="bg-slate-900/70 border border-slate-700 rounded-lg p-4"
          >
            <p className="text-xs uppercase text-slate-500">{label}</p>
            <p className="text-2xl font-bold text-white mt-1">{value ?? 0}</p>
          </div>
        ))}
      </div>

      {validation.issues?.length > 0 && (
        <div className="mt-5 space-y-2">
          {validation.issues.map((issue, index) => (
            <div
              key={`${issue.code || 'issue'}-${index}`}
              className="bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm"
            >
              <span className="font-bold mr-2">{issue.severity}</span>
              <span>{issue.message}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
      <p className="text-xs text-slate-500 uppercase">{label}</p>
      <p className="text-2xl font-bold text-white mt-2">{value}</p>
    </div>
  );
}

function TeamCard({ team }) {
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
      <div className="p-5 border-b border-slate-700">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <p className="text-xs text-indigo-400 font-mono">{team.project_id}</p>
            <h3 className="text-xl font-bold text-white">{team.project_title}</h3>
            <p className="text-sm text-slate-400">Team size: {team.team_size}</p>
          </div>

          <div className="flex flex-wrap gap-3">
            <span
              className={`text-xs px-3 py-1 rounded-full border ${
                team.technical_deficit === 0
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                  : 'border-amber-500/40 bg-amber-500/10 text-amber-300'
              }`}
            >
              {team.technical_status}
            </span>
            <span className="text-xs px-3 py-1 rounded-full border border-indigo-500/40 bg-indigo-500/10 text-indigo-300">
              {(team.technical_coverage * 100).toFixed(1)}% coverage
            </span>
          </div>
        </div>
      </div>

      <div className="p-5">
        <h4 className="font-semibold text-white mb-3">Technical Requirements</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-left text-slate-400">
                <th className="py-2 pr-4">Technology</th>
                <th className="py-2 pr-4">Min Level</th>
                <th className="py-2 pr-4">Required</th>
                <th className="py-2 pr-4">Qualified</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {team.requirements.map((requirement) => (
                <tr
                  key={requirement.technology}
                  className="border-b border-slate-800"
                >
                  <td className="py-3 pr-4 font-semibold">{requirement.technology}</td>
                  <td className="py-3 pr-4">{requirement.min_level}</td>
                  <td className="py-3 pr-4">{requirement.required_members}</td>
                  <td className="py-3 pr-4">{requirement.qualified_members}</td>
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

        <div className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-3">
          <PreferenceStat
            label="First Choices"
            value={team.preference_summary.first_choice_count}
          />
          <PreferenceStat
            label="Ranked Assignments"
            value={team.preference_summary.ranked_choice_count}
          />
          <PreferenceStat
            label="Average Dissatisfaction"
            value={Number(team.preference_summary.average_dissatisfaction).toFixed(3)}
          />
        </div>

        <h4 className="font-semibold text-white mt-7 mb-3">Assigned Students</h4>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {team.students.map((student) => (
            <div
              key={student.student_id}
              className="bg-slate-900/70 border border-slate-700 rounded-lg p-4"
            >
              <div className="flex justify-between gap-4">
                <div>
                  <p className="font-mono font-bold text-white">{student.student_id}</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Preference rank: {student.preference_rank ?? 'Unranked'}
                  </p>
                </div>
                <span className="text-xs text-indigo-300">
                  Dissatisfaction: {Number(student.dissatisfaction).toFixed(3)}
                </span>
              </div>

              <div className="mt-3">
                <p className="text-xs text-slate-500 mb-2">Ranked projects</p>
                <div className="flex flex-wrap gap-2">
                  {student.ranked_projects?.map((projectId, index) => (
                    <span
                      key={`${student.student_id}-${projectId}`}
                      className="text-xs px-2 py-1 bg-slate-800 border border-slate-700 rounded"
                    >
                      {index + 1}. {projectId}
                    </span>
                  ))}
                </div>
              </div>

              <div className="mt-3">
                <p className="text-xs text-slate-500 mb-2">Relevant skills</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(student.relevant_skills).map(([technology, level]) => (
                    <span
                      key={technology}
                      className="text-xs px-2 py-1 bg-slate-800 border border-slate-700 rounded"
                    >
                      {technology}: {level}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PreferenceStat({ label, value }) {
  return (
    <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-lg font-semibold text-white mt-1">{value}</p>
    </div>
  );
}