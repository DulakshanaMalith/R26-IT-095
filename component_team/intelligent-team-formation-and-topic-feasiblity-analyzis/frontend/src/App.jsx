import TeamOptimizer from './components/TeamOptimizer';
import StudentOnboarding from './components/StudentOnboarding';
// import FeasibilityPredictor from './components/FeasibilityPredictor'; // <-- Commented out!

function App() {
  return (
   <div className="min-h-screen bg-[#1e293b] py-10">
      <div className="max-w-6xl mx-auto px-4">
        <h1 className="text-4xl font-extrabold text-center text-white mb-2">Intelligent Project Management</h1>
        <p className="text-center text-slate-400 mb-10">Undergraduate Research Assistant Dashboard</p>
        
        {/* Step 1: Student NLP Data Entry */}
        <div className="mb-12">
          <StudentOnboarding />
        </div>

        {/* Step 2: The standalone predictor is completely disabled 
        <div className="mb-12">
          <FeasibilityPredictor />
        </div> 
        */}

        {/* Step 3: The Team Formation Component (Which now includes predictions!) */}
        <div>
          <TeamOptimizer />
        </div>
        
      </div>
    </div>
  );
}

export default App;