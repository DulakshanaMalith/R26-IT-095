import { useState } from 'react';
import axios from 'axios';

export default function FeasibilityPredictor() {
  const [formData, setFormData] = useState({
    Hours_Studied: 20,
    Attendance: 85,
    Previous_Scores: 75,
    Motivation_Level: 4,
    Skill_React: 3,
    Skill_NodeJS: 3,
    Skill_Python: 3,
    Skill_MongoDB: 3
  });

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: parseFloat(e.target.value)
    });
  };

  const analyzeFeasibility = async () => {
    setLoading(true);
    try {
      // Hit your FastAPI Python server!
      const response = await axios.post('http://127.0.0.1:8003/api/ml/feasibility-score', formData);
      setResult(response.data);
    } catch (error) {
      console.error("Error fetching prediction:", error);
      alert("Failed to connect to the ML engine.");
    }
    setLoading(false);
  };

  return (
    <div className="max-w-4xl mx-auto p-6 bg-white rounded-xl shadow-lg mt-10">
      <h2 className="text-2xl font-bold text-gray-800 mb-6 border-b pb-2">
        Topic Feasibility & Risk Analysis
      </h2>
      
      <div className="grid grid-cols-2 gap-6">
        {/* Academic Inputs */}
        <div className="space-y-4 bg-gray-50 p-4 rounded-lg border border-gray-100">
          <h3 className="font-semibold text-gray-700">Academic History</h3>
          {['Hours_Studied', 'Attendance', 'Previous_Scores', 'Motivation_Level'].map((field) => (
            <div key={field} className="flex justify-between items-center">
              <label className="text-sm font-medium text-gray-600">{field.replace('_', ' ')}</label>
              <input 
                type="number" 
                name={field}
                value={formData[field]} 
                onChange={handleInputChange}
                className="w-24 p-2 border rounded text-right focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          ))}
        </div>

        {/* Technical Inputs */}
        <div className="space-y-4 bg-gray-50 p-4 rounded-lg border border-gray-100">
          <h3 className="font-semibold text-gray-700">Technical Vector (1-5)</h3>
          {['Skill_React', 'Skill_NodeJS', 'Skill_Python', 'Skill_MongoDB'].map((field) => (
            <div key={field} className="flex justify-between items-center">
              <label className="text-sm font-medium text-gray-600">{field.replace('_', ' ')}</label>
              <input 
                type="number" 
                min="1" max="5"
                name={field}
                value={formData[field]} 
                onChange={handleInputChange}
                className="w-24 p-2 border rounded text-right focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          ))}
        </div>
      </div>

      <div className="mt-8 text-center">
        <button 
          onClick={analyzeFeasibility}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-8 rounded-lg shadow transition-all duration-200 disabled:opacity-50"
        >
          {loading ? 'Running AI Analysis...' : 'Predict Project Success'}
        </button>
      </div>

      {/* Results Dashboard */}
      {result && (
        <div className="mt-8 p-6 bg-slate-800 text-white rounded-xl shadow-inner animate-fade-in-up">
          <h3 className="text-xl font-semibold mb-4 text-slate-200">AI Assessment Results</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
             <div className="p-4 bg-slate-700 rounded-lg">
                <p className="text-sm text-slate-400 uppercase tracking-wider">Predicted Score</p>
                <p className="text-3xl font-bold text-blue-400">{result.predicted_score}</p>
             </div>
             <div className="p-4 bg-slate-700 rounded-lg">
                <p className="text-sm text-slate-400 uppercase tracking-wider">Feasibility</p>
                <p className="text-3xl font-bold text-emerald-400">{result.feasibility_percentage}%</p>
             </div>
             <div className={`p-4 rounded-lg border-2 ${
               result.risk_assessment.includes('Low') ? 'border-emerald-500 bg-emerald-900/30' : 
               result.risk_assessment.includes('Medium') ? 'border-amber-500 bg-amber-900/30' : 
               'border-red-500 bg-red-900/30'
             }`}>
                <p className="text-sm uppercase tracking-wider mb-1 opacity-80">Risk Level</p>
                <p className="text-lg font-bold">{result.risk_assessment}</p>
             </div>
          </div>
        </div>
      )}
    </div>
  );
}