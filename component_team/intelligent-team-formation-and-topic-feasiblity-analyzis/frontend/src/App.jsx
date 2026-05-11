import FeasibilityPredictor from './components/FeasibilityPredictor';
import TeamOptimizer from './components/TeamOptimizer'; // Import the new component

function App() {
  return (
   <div className="min-h-screen bg-gray-100 py-10">
      <div className="max-w-6xl mx-auto px-4">
        <h1 className="text-4xl font-extrabold text-center text-blue-900 mb-2">Intelligent Project Management</h1>
        <p className="text-center text-gray-500 mb-10">Undergraduate Research Assistant Dashboard</p>
        
        {/* The Predictive Component */}
        <FeasibilityPredictor />

        {/* The Team Formation Component */}
        <TeamOptimizer />
        
      </div>
    </div>
  );
}

export default App;