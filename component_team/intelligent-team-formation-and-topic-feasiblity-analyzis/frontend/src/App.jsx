// import TeamOptimizer from './components/TeamOptimizer';
// import StudentOnboarding from './components/StudentOnboarding';
// // import FeasibilityPredictor from './components/FeasibilityPredictor'; // <-- Commented out!

// function App() {
//   return (
//    <div className="min-h-screen bg-[#1e293b] py-10">
//       <div className="max-w-6xl mx-auto px-4">
//         <h1 className="text-4xl font-extrabold text-center text-white mb-2">Intelligent Project Management</h1>
//         <p className="text-center text-slate-400 mb-10">Undergraduate Research Assistant Dashboard</p>
        
//         {/* Step 1: Student NLP Data Entry */}
//         <div className="mb-12">
//           <StudentOnboarding />
//         </div>

//         {/* Step 2: The standalone predictor is completely disabled 
//         <div className="mb-12">
//           <FeasibilityPredictor />
//         </div> 
//         */}

//         {/* Step 3: The Team Formation Component (Which now includes predictions!) */}
//         <div>
//           <TeamOptimizer />
//         </div>
        
//       </div>
//     </div>
//   );
// }

// export default App;

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