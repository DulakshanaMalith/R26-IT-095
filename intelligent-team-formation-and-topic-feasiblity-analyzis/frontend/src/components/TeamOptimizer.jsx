import { useState } from 'react';
import axios from 'axios';

export default function TeamOptimizer() {
  const [formData, setFormData] = useState({
    team_size: 4,
    total_students: 12,
    Skill_React: 4,
    Skill_NodeJS: 3,
    Skill_Python: 2,
    Skill_MongoDB: 4
  });

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: parseInt(e.target.value) || 0
    });
  };

  const optimizeTeams = async () => {
    setLoading(true);
    
    // Format the payload to match the FastAPI Pydantic schema
    const payload = {
      team_size: formData.team_size,
      total_students: formData.total_students,
      topic_requirements: {
        Skill_React: formData.Skill_React,
        Skill_NodeJS: formData.Skill_NodeJS,
        Skill_Python: formData.Skill_Python,
        Skill_MongoDB: formData.Skill_MongoDB
      }
    };

    try {
      const response = await axios.post('http://127.0.0.1:8000/api/ml/optimize-teams', payload);
      setResult(response.data);
    } catch (error) {
      console.error("Error optimizing teams:", error);
      alert("Failed to connect to the ML engine. Check your total students limit!");
    }
    setLoading(false);
  };

  return (
    <div className="max-w-6xl mx-auto p-6 bg-white rounded-xl shadow-lg mt-10 mb-20">
      <h2 className="text-2xl font-bold text-gray-800 mb-6 border-b pb-2">
        Multi-Objective Team Formation
      </h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Class Configuration */}
        <div className="space-y-4 bg-blue-50 p-5 rounded-lg border border-blue-100">
          <h3 className="font-semibold text-blue-800">Class constraints</h3>
          <div className="flex justify-between items-center">
            <label className="text-sm font-medium text-gray-700">Total Students to Group</label>
            <input type="number" name="total_students" value={formData.total_students} onChange={handleInputChange} className="w-20 p-2 border rounded text-right focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="flex justify-between items-center">
            <label className="text-sm font-medium text-gray-700">Target Team Size</label>
            <input type="number" name="team_size" value={formData.team_size} onChange={handleInputChange} className="w-20 p-2 border rounded text-right focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>

        {/* Project Requirements */}
        <div className="space-y-4 bg-gray-50 p-5 rounded-lg border border-gray-100">
          <h3 className="font-semibold text-gray-700">Project Tech Requirements (1-5)</h3>
          <div className="grid grid-cols-2 gap-4">
            {['Skill_React', 'Skill_NodeJS', 'Skill_Python', 'Skill_MongoDB'].map((field) => (
              <div key={field} className="flex justify-between items-center">
                <label className="text-xs font-medium text-gray-600">{field.replace('Skill_', '')}</label>
                <input type="number" min="1" max="5" name={field} value={formData[field]} onChange={handleInputChange} className="w-16 p-1 border rounded text-center focus:ring-2 focus:ring-blue-500" />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-8 text-center">
        <button 
          onClick={optimizeTeams} disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-8 rounded-lg shadow transition-all duration-200 disabled:opacity-50"
        >
          {loading ? 'Running Genetic Draft...' : 'Generate Optimal Teams'}
        </button>
      </div>

      {/* Visualizer Dashboard */}
      {result && (
        <div className="mt-10 animate-fade-in-up">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-xl font-bold text-gray-800">Generated Roster</h3>
            <span className="bg-indigo-100 text-indigo-800 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wide">
              {result.algorithm}
            </span>
          </div>
          
          {/* Team Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {result.teams.map((team, index) => (
              <div key={index} className="bg-white border-2 border-slate-100 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow">
                {/* Card Header */}
                <div className="bg-slate-800 text-white p-4 flex justify-between items-center">
                  <h4 className="font-bold text-lg">{team.team_id}</h4>
                  <div className="text-right">
                    <p className="text-xs text-slate-400">Avg Power</p>
                    <p className="font-mono font-bold text-emerald-400">{team.stats.avg_power}</p>
                  </div>
                </div>
                
                {/* Team Members */}
                <div className="p-4 space-y-3">
                  {team.members.map((member, mIdx) => (
                    <div key={mIdx} className="flex justify-between items-center p-2 bg-slate-50 rounded border border-slate-100">
                      <span className="font-mono text-sm text-slate-600">{member.student_id}</span>
                      <span className="font-mono text-sm font-bold text-indigo-600">{member.power_score}</span>
                    </div>
                  ))}
                </div>
                
                {/* Aggregate Skills Footer */}
                <div className="bg-slate-100 p-3 flex justify-around text-xs font-mono text-slate-500 border-t border-slate-200">
                  <span>Re:{team.stats.total_react}</span>
                  <span>No:{team.stats.total_node}</span>
                  <span>Py:{team.stats.total_python}</span>
                  <span>Mo:{team.stats.total_mongo}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}