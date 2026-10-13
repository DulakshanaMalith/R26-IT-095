import StaffTeamFormation from './components/StaffTeamFormation';
function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700">Intelligent Project Management System</p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">Team Formation & Topic Feasibility</h1>
            <p className="mt-1 text-sm text-slate-600">Academic staff decision-support workspace</p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-800">
            <span className="h-2 w-2 rounded-full bg-blue-600" />
            Staff Workspace
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <StaffTeamFormation />
      </main>
    </div>
  );
}
export default App;
