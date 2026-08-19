import StaffTeamFormation from './components/StaffTeamFormation';

function App() {
  return (
    <div className="min-h-screen bg-slate-950 py-10">
      <div className="max-w-7xl mx-auto px-4">
        <header className="mb-10 border-b border-slate-800 pb-6">
          <p className="text-sm uppercase tracking-widest text-indigo-400 font-semibold">
            Intelligent Project Management System
          </p>

          <h1 className="text-4xl font-extrabold text-white mt-2">
            Team Formation & Topic Feasibility
          </h1>

          <p className="text-slate-400 mt-2">
            Academic Staff Decision-Support Workspace
          </p>
        </header>

        <StaffTeamFormation />
      </div>
    </div>
  );
}

export default App;