import { useMemo, useState } from 'react';
import axios from 'axios';
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';
import TopicFeasibilityPanel from './TopicFeasibilityPanel';
import SupervisorAllocationPanel from './SupervisorAllocationPanel';
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
  if (role === 'Technical-oriented endpoint') return 'border-blue-200 bg-blue-50 text-blue-800';
  if (role === 'Preference-oriented endpoint') return 'border-violet-200 bg-violet-50 text-violet-800';
  return 'border-amber-200 bg-amber-50 text-amber-800';
}
function roleLabel(role) {
  if (role === 'Technical-oriented endpoint') return 'Technical-oriented';
  if (role === 'Preference-oriented endpoint') return 'Preference-oriented';
  return 'Trade-off alternative';
}
export default function StaffTeamFormation() {
  const [file, setFile] = useState(null);
  const [studentsPerTeam, setStudentsPerTeam] = useState('4');
  const [validation, setValidation] = useState(null);
  const [result, setResult] = useState(null);
  const [selectedSolutionId, setSelectedSolutionId] = useState(null);
  const [validating, setValidating] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [supervisorComplete, setSupervisorComplete] = useState(false);
  const [finalComplete, setFinalComplete] = useState(false);
  const teamSizeValue = Number(studentsPerTeam);
  const teamSizeValid = Number.isInteger(teamSizeValue) && teamSizeValue >= 2;
  const solutions = useMemo(() => result?.team_formation?.solutions ?? [], [result]);
  const selectedSolution = useMemo(() => {
    if (!solutions.length) return null;
    return solutions.find((solution) => solution.solution_id === selectedSolutionId) || solutions[0];
  }, [solutions, selectedSolutionId]);
  const paretoData = useMemo(() => solutions.map((solution) => ({
    solutionId: solution.solution_id,
    role: solution.role,
    technicalDeficit: solution.technical_requirement_deficit,
    preferenceDissatisfaction: solution.preference_dissatisfaction,
  })), [solutions]);
  const resetResults = () => {
    setValidation(null);
    setResult(null);
    setSelectedSolutionId(null);
    setErrorMessage('');
    setSupervisorComplete(false);
    setFinalComplete(false);
  };
  const handleFileChange = (event) => {
    setFile(event.target.files?.[0] || null);
    resetResults();
  };
  const buildFormData = () => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('students_per_team', String(teamSizeValue));
    return formData;
  };
  const validateWorkbook = async () => {
    if (!file) return setErrorMessage('Please select an Excel workbook first.');
    if (!teamSizeValid) return setErrorMessage('Students per team must be a whole number of at least 2.');
    setValidating(true);
    setErrorMessage('');
    setResult(null);
    setSelectedSolutionId(null);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/cohort/validate`, buildFormData());
      setValidation(response.data);
    } catch (error) {
      console.error('Workbook validation failed:', error);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setValidating(false);
    }
  };
  const optimizeTeams = async () => {
    if (!file) return setErrorMessage('Please select an Excel workbook first.');
    if (!teamSizeValid) return setErrorMessage('Students per team must be a whole number of at least 2.');
    setOptimizing(true);
    setErrorMessage('');
    try {
      const response = await axios.post(`${API_BASE_URL}/api/cohort/optimize`, buildFormData());
      setResult(response.data);
      setValidation(response.data.validation);
      const returnedSolutions = response.data.team_formation?.solutions ?? [];
      setSelectedSolutionId(returnedSolutions[0]?.solution_id ?? null);
      setSupervisorComplete(false);
      setFinalComplete(false);
    } catch (error) {
      console.error('Team formation failed:', error);
      const detail = error.response?.data?.detail;
      if (detail?.validation) setValidation(detail.validation);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setOptimizing(false);
    }
  };
  const selectSolution = (solutionId) => {
    setSelectedSolutionId(solutionId);
    setSupervisorComplete(false);
    setFinalComplete(false);
  };
  return (
    <div className="space-y-6">
      <WorkflowStrip hasFile={Boolean(file)} validation={validation} result={result} selectedSolution={selectedSolution} supervisorComplete={supervisorComplete} finalComplete={finalComplete} />
      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <SectionHeader step="1" title="Cohort Setup" description="Upload the staff workbook and define the uniform target team size for this cohort." />
        <div className="grid gap-5 border-t border-slate-100 p-6 lg:grid-cols-[1fr_180px_auto] lg:items-end">
          <div>
            <label className="mb-2 block text-sm font-semibold text-slate-700">Cohort workbook</label>
            <input type="file" accept=".xlsx" onChange={handleFileChange} className="block w-full rounded-lg border border-slate-300 bg-white text-sm text-slate-700 file:mr-4 file:border-0 file:border-r file:border-slate-200 file:bg-slate-50 file:px-4 file:py-2.5 file:font-semibold file:text-slate-700 hover:file:bg-slate-100" />
            <p className="mt-2 text-xs text-slate-500">Expected staff workbook includes Students, Preferences, Projects, ProjectRequirements and supervisor/domain sheets.</p>
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold text-slate-700">Students per team</label>
            <input type="number" min="2" step="1" value={studentsPerTeam} onChange={(event) => { setStudentsPerTeam(event.target.value); resetResults(); }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
            <p className="mt-2 text-xs text-slate-500">Applied across the cohort.</p>
          </div>
          <div className="flex flex-wrap gap-3 lg:justify-end">
            <button type="button" onClick={validateWorkbook} disabled={!file || !teamSizeValid || validating || optimizing} className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-40">{validating ? 'Validating...' : 'Validate Workbook'}</button>
            <button type="button" onClick={optimizeTeams} disabled={!file || !teamSizeValid || validating || optimizing || (validation && validation.valid === false)} className="rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-800 disabled:opacity-40">{optimizing ? 'Generating...' : 'Generate Team Allocations'}</button>
          </div>
        </div>
        {file && <div className="border-t border-slate-100 bg-slate-50 px-6 py-3 text-xs text-slate-600"><span className="font-semibold text-slate-700">Selected file:</span> {file.name}</div>}
        {errorMessage && <div className="m-6 mt-0 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{errorMessage}</div>}
      </section>
      {validation && <ValidationPanel validation={validation} studentsPerTeam={teamSizeValue} />}
      {result && (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <SectionHeader step="3" title="Allocation Alternatives" description="Compare nondominated team-project allocations. The system does not automatically choose one for staff." eyebrow="Pareto decision support" />
            <div className="border-t border-slate-100 p-6">
              <OptimizerSummary result={result} />
              <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-800">Trade-off view</h3>
                    <p className="text-xs text-slate-500">Lower values are better on both axes. Select a point or an alternative below.</p>
                  </div>
                </div>
                <div className="h-72 w-full min-w-0 rounded-lg bg-white p-2">
                  <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} initialDimension={{ width: 900, height: 260 }}>
                    <ScatterChart margin={{ top: 15, right: 25, bottom: 30, left: 45 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis type="number" dataKey="technicalDeficit" name="Technical Deficit" domain={[0, 'auto']} tick={{ fill: '#64748b', fontSize: 11 }} label={{ value: 'Technical Requirement Deficit', position: 'insideBottom', offset: -15, fill: '#64748b' }} />
                      <YAxis type="number" dataKey="preferenceDissatisfaction" name="Preference Dissatisfaction" domain={[0, 'auto']} tick={{ fill: '#64748b', fontSize: 11 }} label={{ value: 'Preference Dissatisfaction', angle: -90, position: 'insideLeft', offset: -30, fill: '#64748b' }} />
                      <Tooltip cursor={{ strokeDasharray: '3 3' }} content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const point = payload[0].payload;
                        return <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs shadow-lg"><p className="font-bold text-slate-900">Alternative {point.solutionId}</p><p className="text-slate-500">{roleLabel(point.role)}</p><p className="mt-2 text-slate-700">Technical deficit: {Number(point.technicalDeficit).toFixed(4)}</p><p className="text-slate-700">Preference dissatisfaction: {Number(point.preferenceDissatisfaction).toFixed(4)}</p></div>;
                      }} />
                      <Scatter data={paretoData} fill="#2563eb" onClick={(point) => selectSolution(point.solutionId)} />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div className="mt-6 grid gap-4 md:grid-cols-3">
                {solutions.map((solution) => {
                  const selected = selectedSolution?.solution_id === solution.solution_id;
                  return (
                    <button key={solution.solution_id} type="button" onClick={() => selectSolution(solution.solution_id)} className={`rounded-xl border p-4 text-left transition ${selected ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-100' : 'border-slate-200 bg-white hover:border-blue-300 hover:bg-slate-50'}`}>
                      <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-bold text-slate-900">Allocation {solution.solution_id}</p><p className="mt-1 text-xs text-slate-500">{selected ? 'Currently selected' : 'Select to review'}</p></div><span className={`rounded-full border px-2 py-1 text-[10px] font-semibold ${roleStyle(solution.role)}`}>{roleLabel(solution.role)}</span></div>
                      <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4"><div><dt className="text-xs text-slate-500">Technical coverage</dt><dd className="mt-1 text-lg font-bold text-slate-900">{percent(solution.technical_requirement_coverage)}</dd></div><div><dt className="text-xs text-slate-500">Preference satisfaction</dt><dd className="mt-1 text-lg font-bold text-slate-900">{percent(solution.preference_satisfaction)}</dd></div></dl>
                    </button>
                  );
                })}
              </div>
            </div>
          </section>
          {selectedSolution && (
            <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
              <SectionHeader step="4" title="Selected Allocation Review" description={`Allocation ${selectedSolution.solution_id} — ${roleLabel(selectedSolution.role)}. Review team details before moving to downstream actions.`} />
              <div className="border-t border-slate-100 p-6">
                <MetricStrip items={[
                  ['Technical Coverage', percent(selectedSolution.technical_requirement_coverage)],
                  ['Technical Deficit', percent(selectedSolution.technical_requirement_deficit)],
                  ['Preference Satisfaction', percent(selectedSolution.preference_satisfaction)],
                  ['Preference Dissatisfaction', percent(selectedSolution.preference_dissatisfaction)],
                ]} />
                <div className="mt-6 space-y-3">
                  {selectedSolution.teams.map((team, index) => <TeamCard key={team.project_id} team={team} teamNumber={index + 1} />)}
                </div>
                <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">{result.team_formation.interpretation.allocation_count_note}</div>
              </div>
              <TopicFeasibilityPanel key={selectedSolution.solution_id} workbookFile={file} selectedSolution={selectedSolution} studentsPerTeam={teamSizeValue} />
              <SupervisorAllocationPanel key={`supervisor-${selectedSolution.solution_id}`} workbookFile={file} selectedSolution={selectedSolution} studentsPerTeam={teamSizeValue} onAllocated={() => setSupervisorComplete(true)} onFinalized={() => setFinalComplete(true)} />
            </section>
          )}
        </>
      )}
    </div>
  );
}
function WorkflowStrip({ hasFile, validation, result, selectedSolution, supervisorComplete, finalComplete }) {
  const steps = [
    ['1', 'Setup', hasFile],
    ['2', 'Validate', validation?.valid === true],
    ['3', 'Generate', Boolean(result)],
    ['4', 'Review', Boolean(selectedSolution)],
    ['5', 'Supervisors', supervisorComplete],
    ['6', 'Finalize', finalComplete],
  ];
  return <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"><div className="flex min-w-[680px] items-center">{steps.map(([number, label, done], index) => <div key={label} className="flex flex-1 items-center"><div className="flex items-center gap-2"><span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${done ? 'bg-blue-700 text-white' : 'border border-slate-300 bg-white text-slate-500'}`}>{done ? '✓' : number}</span><span className={`text-xs font-semibold ${done ? 'text-slate-800' : 'text-slate-500'}`}>{label}</span></div>{index < steps.length - 1 && <div className={`mx-3 h-px flex-1 ${done ? 'bg-blue-200' : 'bg-slate-200'}`} />}</div>)}</div></div>;
}
function SectionHeader({ step, title, description, eyebrow }) {
  return <div className="flex flex-col gap-3 p-6 sm:flex-row sm:items-start sm:justify-between"><div className="flex gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-700 text-sm font-bold text-white">{step}</span><div>{eyebrow && <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-blue-700">{eyebrow}</p>}<h2 className="text-xl font-bold text-slate-900">{title}</h2><p className="mt-1 max-w-3xl text-sm text-slate-600">{description}</p></div></div></div>;
}
function ValidationPanel({ validation, studentsPerTeam }) {
  const summaryItems = [['Students', validation.summary?.students], ['Projects', validation.summary?.projects], ['Supervisors', validation.summary?.supervisors], ['Errors', validation.summary?.errors], ['Warnings', validation.summary?.warnings]];
  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4 p-6"><div className="flex gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-700 text-sm font-bold text-white">2</span><div><h2 className="text-xl font-bold text-slate-900">Workbook Validation</h2><p className="mt-1 text-sm text-slate-600">Checks the workbook before team formation starts.</p></div></div><span className={`rounded-full border px-3 py-1 text-xs font-bold ${validation.valid ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'}`}>{validation.valid ? 'VALID' : 'INVALID'}</span></div>
      <div className="border-t border-slate-100 p-6"><MetricStrip items={summaryItems} compact />{validation.summary?.students > 0 && Number.isInteger(studentsPerTeam) && studentsPerTeam >= 2 && <TeamPlan studentCount={validation.summary.students} studentsPerTeam={studentsPerTeam} />}{validation.issues?.length > 0 && <div className="mt-5 overflow-hidden rounded-lg border border-slate-200"><div className="bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600">Validation messages</div>{validation.issues.map((issue, index) => <div key={`${issue.code || 'issue'}-${index}`} className="border-t border-slate-100 px-4 py-3 text-sm text-slate-700"><span className={`mr-2 font-bold ${issue.severity === 'ERROR' ? 'text-red-700' : 'text-amber-700'}`}>{issue.severity}</span>{issue.message}</div>)}</div>}</div>
    </section>
  );
}
function TeamPlan({ studentCount, studentsPerTeam }) {
  const fullTeams = Math.floor(studentCount / studentsPerTeam);
  const remainder = studentCount % studentsPerTeam;
  const totalTeams = fullTeams + (remainder > 0 ? 1 : 0);
  return <div className={`mt-5 rounded-lg border px-4 py-3 ${remainder > 0 ? 'border-amber-200 bg-amber-50' : 'border-emerald-200 bg-emerald-50'}`}><p className="text-sm font-semibold text-slate-800">Team formation plan</p><p className="mt-1 text-sm text-slate-700">{studentCount} students → {fullTeams} full team(s) of {studentsPerTeam}{remainder > 0 ? ` + 1 remainder team of ${remainder}` : ''} → {totalTeams} total team(s).</p>{remainder === 1 && <p className="mt-2 text-xs font-medium text-amber-800">The remainder team contains only one student. Staff should confirm that this exception is acceptable.</p>}</div>;
}
function OptimizerSummary({ result }) {
  const config = result.team_formation.team_configuration;
  const items = [
    ['Method', result.team_formation.optimizer.algorithm],
    ['Version', result.team_formation.optimizer.optimizer_version],
    ['Alternatives', result.team_formation.solution_count],
    ['Target team size', config?.target_team_size],
  ];
  return <dl className="grid overflow-hidden rounded-xl border border-slate-200 bg-white sm:grid-cols-2 lg:grid-cols-4">{items.map(([label, value], index) => <div key={label} className={`px-4 py-3 ${index ? 'border-t border-slate-100 sm:border-t-0 sm:border-l' : ''}`}><dt className="text-xs font-medium text-slate-500">{label}</dt><dd className="mt-1 text-sm font-semibold text-slate-900">{value ?? '—'}</dd></div>)}{config?.has_remainder_team && <div className="col-span-full border-t border-amber-100 bg-amber-50 px-4 py-2 text-xs text-amber-800">Remainder team: {config.remainder_students} student(s)</div>}</dl>;
}
function MetricStrip({ items, compact = false }) {
  return <dl className={`grid overflow-hidden rounded-xl border border-slate-200 bg-white ${compact ? 'grid-cols-2 md:grid-cols-5' : 'grid-cols-2 lg:grid-cols-4'}`}>{items.map(([label, value], index) => <div key={label} className={`px-4 py-3 ${index ? 'border-l border-slate-100' : ''}`}><dt className="text-xs text-slate-500">{label}</dt><dd className={`${compact ? 'text-xl' : 'text-lg'} mt-1 font-bold text-slate-900`}>{value ?? 0}</dd></div>)}</dl>;
}
function TeamCard({ team, teamNumber }) {
  return (
    <details className="group overflow-hidden rounded-xl border border-slate-200 bg-white">
      <summary className="flex cursor-pointer items-center justify-between gap-4 px-5 py-4 hover:bg-slate-50">
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-bold text-slate-700">Team {teamNumber}</span><span className="text-xs font-mono text-blue-700">{team.project_id}</span></div><h3 className="mt-2 truncate text-base font-bold text-slate-900">{team.project_title}</h3><p className="mt-1 text-xs text-slate-500">{team.team_size} students · {team.technical_status}</p></div>
        <div className="flex shrink-0 items-center gap-3"><div className="hidden text-right sm:block"><p className="text-xs text-slate-500">Technical coverage</p><p className="text-sm font-bold text-slate-900">{percent(team.technical_coverage)}</p></div><span className="text-slate-400 transition group-open:rotate-180">⌄</span></div>
      </summary>
      <div className="border-t border-slate-100 p-5">
        <div className="grid gap-5 xl:grid-cols-2">
          <div><h4 className="mb-3 text-sm font-semibold text-slate-800">Technical requirements</h4><div className="overflow-x-auto rounded-lg border border-slate-200"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs text-slate-600"><tr><th className="px-3 py-2">Technology</th><th className="px-3 py-2">Min</th><th className="px-3 py-2">Required</th><th className="px-3 py-2">Qualified</th><th className="px-3 py-2">Status</th></tr></thead><tbody>{team.requirements.map((requirement) => <tr key={requirement.technology} className="border-t border-slate-100"><td className="px-3 py-2 font-semibold text-slate-800">{requirement.technology}</td><td className="px-3 py-2 text-slate-700">{requirement.min_level}</td><td className="px-3 py-2 text-slate-700">{requirement.required_members}</td><td className="px-3 py-2 text-slate-700">{requirement.qualified_members}</td><td className="px-3 py-2"><StatusPill good={requirement.status === 'Covered'} text={requirement.status} /></td></tr>)}</tbody></table></div></div>
          <div><h4 className="mb-3 text-sm font-semibold text-slate-800">Preference summary</h4><dl className="grid grid-cols-3 overflow-hidden rounded-lg border border-slate-200"><SimpleStat label="First choices" value={team.preference_summary.first_choice_count} /><SimpleStat label="Ranked assignments" value={team.preference_summary.ranked_choice_count} bordered /><SimpleStat label="Avg. dissatisfaction" value={Number(team.preference_summary.average_dissatisfaction).toFixed(3)} bordered /></dl></div>
        </div>
        <h4 className="mb-3 mt-6 text-sm font-semibold text-slate-800">Assigned students</h4>
        <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs text-slate-600"><tr><th className="px-3 py-2">Student</th><th className="px-3 py-2">Preference rank</th><th className="px-3 py-2">Dissatisfaction</th><th className="px-3 py-2">Ranked projects</th><th className="px-3 py-2">Relevant skills</th></tr></thead><tbody>{team.students.map((student) => <tr key={student.student_id} className="border-t border-slate-100 align-top"><td className="px-3 py-3 font-mono font-semibold text-slate-900">{student.student_id}</td><td className="px-3 py-3 text-slate-700">{student.preference_rank ?? 'Unranked'}</td><td className="px-3 py-3 text-slate-700">{Number(student.dissatisfaction).toFixed(3)}</td><td className="px-3 py-3 text-xs text-slate-600">{student.ranked_projects?.map((projectId, index) => `${index + 1}. ${projectId}`).join(' · ') || '—'}</td><td className="px-3 py-3 text-xs text-slate-600">{Object.entries(student.relevant_skills || {}).map(([technology, level]) => `${technology}: ${level}`).join(' · ') || '—'}</td></tr>)}</tbody></table></div>
      </div>
    </details>
  );
}
function SimpleStat({ label, value, bordered }) { return <div className={`px-3 py-3 ${bordered ? 'border-l border-slate-100' : ''}`}><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 text-base font-bold text-slate-900">{value}</dd></div>; }
function StatusPill({ good, text }) { return <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${good ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{text}</span>; }
