import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8003';

export default function TopicFeasibilityPanel({
  workbookFile,
  selectedSolution,
}) {
  const teams = selectedSolution?.teams || [];

  const [sourceProjectId, setSourceProjectId] = useState('');
  const [targetProjectId, setTargetProjectId] = useState('');
  const [result, setResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    if (!teams.length) {
      setSourceProjectId('');
      setTargetProjectId('');
      setResult(null);
      return;
    }

    setSourceProjectId(
      teams[0].project_id
    );

    setTargetProjectId(
      teams[0].project_id
    );

    setResult(null);
    setErrorMessage('');
  }, [selectedSolution]);

  const sourceTeam = useMemo(
    () =>
      teams.find(
        (team) =>
          team.project_id ===
          sourceProjectId
      ) || null,
    [teams, sourceProjectId]
  );

  const targetProject = useMemo(
    () =>
      teams.find(
        (team) =>
          team.project_id ===
          targetProjectId
      ) || null,
    [teams, targetProjectId]
  );

  const getErrorMessage = (error) => {
    const detail =
      error.response?.data?.detail;

    if (typeof detail === 'string') {
      return detail;
    }

    if (detail?.message) {
      return detail.message;
    }

    return (
      error.message ||
      'Topic feasibility analysis failed.'
    );
  };

  const analyzeFeasibility = async () => {
    if (!workbookFile) {
      setErrorMessage(
        'The cohort workbook is not available.'
      );
      return;
    }

    if (
      !sourceTeam ||
      !targetProject
    ) {
      setErrorMessage(
        'Please select a team and topic.'
      );
      return;
    }

    const studentIds =
      sourceTeam.students.map(
        (student) =>
          student.student_id
      );

    const formData =
      new FormData();

    formData.append(
      'file',
      workbookFile
    );

    formData.append(
      'project_id',
      targetProject.project_id
    );

    formData.append(
      'team_student_ids',
      studentIds.join(',')
    );

    setAnalyzing(true);
    setErrorMessage('');
    setResult(null);

    try {
      const response =
        await axios.post(
          `${API_BASE_URL}/api/topic-feasibility/analyze`,
          formData
        );

      setResult(
        response.data
          .topic_feasibility
      );
    } catch (error) {
      console.error(
        'Topic feasibility failed:',
        error
      );

      setErrorMessage(
        getErrorMessage(error)
      );
    } finally {
      setAnalyzing(false);
    }
  };

  const percent = (value) =>
    `${(
      Number(value || 0) * 100
    ).toFixed(1)}%`;

  if (!selectedSolution) {
    return null;
  }

  return (
    <section className="mt-8 bg-slate-800/80 border border-slate-700 rounded-xl p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white">
          Topic Technical Feasibility
        </h2>

        <p className="text-sm text-slate-400 mt-2 max-w-3xl">
          Evaluate an existing team against
          the modeled technical requirements
          of an approved project or topic.
          This analysis measures technical
          coverage only and does not predict
          overall project success.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div>
          <label className="block text-sm font-semibold text-slate-300 mb-2">
            Team to Evaluate
          </label>

          <select
            value={sourceProjectId}
            onChange={(event) => {
              setSourceProjectId(
                event.target.value
              );

              setResult(null);
            }}
            className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white"
          >
            {teams.map((team) => (
              <option
                key={team.project_id}
                value={team.project_id}
              >
                Team assigned to{' '}
                {team.project_id} —{' '}
                {team.project_title}
              </option>
            ))}
          </select>

          {sourceTeam && (
            <div className="mt-3 flex flex-wrap gap-2">
              {sourceTeam.students.map(
                (student) => (
                  <span
                    key={
                      student.student_id
                    }
                    className="text-xs px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-300"
                  >
                    {
                      student.student_id
                    }
                  </span>
                )
              )}
            </div>
          )}
        </div>

        <div>
          <label className="block text-sm font-semibold text-slate-300 mb-2">
            Topic / Project Requirements
          </label>

          <select
            value={targetProjectId}
            onChange={(event) => {
              setTargetProjectId(
                event.target.value
              );

              setResult(null);
            }}
            className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white"
          >
            {teams.map((team) => (
              <option
                key={team.project_id}
                value={team.project_id}
              >
                {team.project_id} —{' '}
                {team.project_title}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={
            analyzeFeasibility
          }
          disabled={analyzing}
          className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold disabled:opacity-40"
        >
          {analyzing
            ? 'Analyzing...'
            : 'Analyze Technical Feasibility'}
        </button>

        {sourceProjectId ===
          targetProjectId && (
          <p className="text-xs text-slate-500">
            Evaluating the team against
            its currently assigned project.
          </p>
        )}
      </div>

      {errorMessage && (
        <div className="mt-5 border border-red-500/40 bg-red-500/10 rounded-lg p-4 text-red-300">
          {errorMessage}
        </div>
      )}

      {result && (
        <div className="mt-8">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
            <div>
              <p className="text-xs font-mono text-indigo-400">
                {
                  result.project
                    .project_id
                }
              </p>

              <h3 className="text-xl font-bold text-white">
                {
                  result.project
                    .project_title
                }
              </h3>
            </div>

            <span
              className={`px-3 py-1.5 rounded-full text-xs font-bold border ${
                result.technical_deficit ===
                0
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                  : 'border-amber-500/40 bg-amber-500/10 text-amber-300'
              }`}
            >
              {result.status}
            </span>
          </div>

          {!result.team
            .team_size_matches_project && (
            <div className="mb-6 border border-amber-500/40 bg-amber-500/10 rounded-lg p-4">
              <p className="font-semibold text-amber-300">
                Team Size Mismatch
              </p>

              <p className="text-sm text-slate-300 mt-1">
                This project expects{' '}
                {
                  result.team
                    .expected_team_size
                }{' '}
                members, but the selected
                team currently contains{' '}
                {
                  result.team
                    .actual_team_size
                }.
              </p>

              <p className="text-xs text-slate-400 mt-2">
                Technical coverage is still
                calculated for the current
                team. This result does not
                mean that the project's team
                size requirement has been
                satisfied.
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-7">
            <MetricCard
              label="Technical Coverage"
              value={percent(
                result.technical_coverage
              )}
            />

            <MetricCard
              label="Technical Deficit"
              value={percent(
                result.technical_deficit
              )}
            />

            <MetricCard
              label="Requirements Covered"
              value={
                `${result.requirement_summary.covered_requirements}` +
                ` / ` +
                `${result.requirement_summary.total_requirements}`
              }
            />

            <MetricCard
              label="Technical Gaps"
              value={
                result.requirement_summary
                  .gap_requirements
              }
            />
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-left text-slate-400">
                  <th className="py-3 pr-4">
                    Technology
                  </th>

                  <th className="py-3 pr-4">
                    Min Level
                  </th>

                  <th className="py-3 pr-4">
                    Required
                  </th>

                  <th className="py-3 pr-4">
                    Qualified
                  </th>

                  <th className="py-3 pr-4">
                    Coverage
                  </th>

                  <th className="py-3">
                    Status
                  </th>
                </tr>
              </thead>

              <tbody>
                {result.requirements.map(
                  (requirement) => (
                    <tr
                      key={
                        requirement.technology
                      }
                      className="border-b border-slate-800"
                    >
                      <td className="py-3 pr-4 font-semibold text-white">
                        {
                          requirement.technology
                        }
                      </td>

                      <td className="py-3 pr-4">
                        {
                          requirement.min_level
                        }
                      </td>

                      <td className="py-3 pr-4">
                        {
                          requirement.required_members
                        }
                      </td>

                      <td className="py-3 pr-4">
                        {
                          requirement.qualified_members
                        }
                      </td>

                      <td className="py-3 pr-4">
                        {percent(
                          requirement.coverage
                        )}
                      </td>

                      <td className="py-3">
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${
                            requirement.status ===
                            'Covered'
                              ? 'bg-emerald-500/10 text-emerald-300'
                              : 'bg-red-500/10 text-red-300'
                          }`}
                        >
                          {
                            requirement.status
                          }
                        </span>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>

          {result.requirements.some(
            (requirement) =>
              requirement.status ===
              'Gap'
          ) && (
            <div className="mt-7">
              <h4 className="font-bold text-white mb-3">
                Identified Technical Gaps
              </h4>

              <div className="space-y-3">
                {result.requirements
                  .filter(
                    (requirement) =>
                      requirement.status ===
                      'Gap'
                  )
                  .map(
                    (requirement) => (
                      <div
                        key={
                          requirement.technology
                        }
                        className="border border-red-500/30 bg-red-500/5 rounded-lg p-4"
                      >
                        <p className="font-semibold text-red-300">
                          {
                            requirement.technology
                          }
                        </p>

                        <p className="text-sm text-slate-400 mt-1">
                          Requires{' '}
                          {
                            requirement.required_members
                          }{' '}
                          member(s) at level{' '}
                          {
                            requirement.min_level
                          }{' '}
                          or above, but only{' '}
                          {
                            requirement.qualified_members
                          }{' '}
                          currently qualify.
                        </p>

                        <p className="text-xs text-slate-500 mt-2">
                          Additional qualified
                          members needed:{' '}
                          {
                            requirement.gap_members
                          }
                        </p>
                      </div>
                    )
                  )}
              </div>
            </div>
          )}

          <div className="mt-7 border border-slate-700 bg-slate-900/60 rounded-lg p-4 text-xs text-slate-400">
            {
              result.interpretation
                .scope_note
            }
          </div>
        </div>
      )}
    </section>
  );
}

function MetricCard({
  label,
  value,
}) {
  return (
    <div className="bg-slate-900/70 border border-slate-700 rounded-xl p-4">
      <p className="text-xs uppercase text-slate-500">
        {label}
      </p>

      <p className="text-2xl font-bold text-white mt-2">
        {value}
      </p>
    </div>
  );
}