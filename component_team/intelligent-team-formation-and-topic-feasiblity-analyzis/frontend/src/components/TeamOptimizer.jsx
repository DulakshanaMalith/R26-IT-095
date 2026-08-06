import { useState } from 'react';
import axios from 'axios';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts';

export default function TeamOptimizer() {
  const [formData, setFormData] = useState({
    max_team_size: 4, 
    max_groups: 3,    
    total_students: 12
  });

  // NEW: Dynamic Tech Stack State
  const [techList, setTechList] = useState([
    { category: 'Frontend', tech: 'React', score: 4 },
    { category: 'Backend', tech: 'NodeJS', score: 3 },
    { category: 'Data/ML', tech: 'Python', score: 2 },
    { category: 'Database', tech: 'MongoDB', score: 4 }
  ]);

  const [selectedCategory, setSelectedCategory] = useState('Database');
  const [selectedTech, setSelectedTech] = useState('MySQL');
  const [selectedScore, setSelectedScore] = useState(3);

  // Pre-configured options based on the panel's request
  const techCategories = {
    'Frontend': ['React', 'HTML/CSS', 'Angular', 'Vue'],
    'Backend': ['NodeJS', 'Express', 'Java', 'PHP', 'FastAPI'],
    'Database': ['MongoDB', 'MySQL', 'PostgreSQL', 'Firebase'],
    'Data/ML': ['Python', 'TensorFlow', 'Pandas']
  };

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: parseInt(e.target.value) || 0
    });
  };

  const handleCategoryChange = (e) => {
    const category = e.target.value;
    setSelectedCategory(category);
    setSelectedTech(techCategories[category][0]); // Reset tech to first item in new category
  };

  const handleAddTech = () => {
    if (techList.find(t => t.tech === selectedTech)) {
      alert(`${selectedTech} is already in the requirements list!`);
      return;
    }
    setTechList([...techList, { category: selectedCategory, tech: selectedTech, score: selectedScore }]);
  };

  const handleRemoveTech = (techToRemove) => {
    setTechList(techList.filter(t => t.tech !== techToRemove));
  };

  const optimizeTeams = async () => {
    setLoading(true);

    // Safely map the required core skills to the backend payload
    const reactSkill = techList.find(t => t.tech === 'React')?.score || 0;
    const nodeSkill = techList.find(t => t.tech === 'NodeJS')?.score || 0;
    const pySkill = techList.find(t => t.tech === 'Python')?.score || 0;
    const mongoSkill = techList.find(t => t.tech === 'MongoDB')?.score || 0;

    const payload = {
      max_team_size: formData.max_team_size, 
      max_groups: formData.max_groups,       
      total_students: formData.total_students,
      topic_requirements: {
        Skill_React: reactSkill,
        Skill_NodeJS: nodeSkill,
        Skill_Python: pySkill,
        Skill_MongoDB: mongoSkill
      }
    };

    try {
      const response = await axios.post('http://127.0.0.1:8003/api/ml/optimize-teams', payload);
      setResult(response.data);
    } catch (error) {
      console.error("Error optimizing teams:", error);
      alert("Failed to connect to the ML engine.");
    }
    setLoading(false);
  };

  return (
    <div className="max-w-6xl mx-auto p-6 bg-slate-800 rounded-xl shadow-lg mt-10 mb-20 text-slate-200 border border-slate-700">
      <h2 className="text-2xl font-bold text-white mb-6 border-b border-slate-600 pb-2">
        Multi-Objective Team Formation
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Class Constraints */}
        <div className="space-y-4 bg-slate-900 p-5 rounded-lg border border-slate-700">
          <h3 className="font-semibold text-indigo-400">Class constraints</h3>
          
          <div className="flex justify-between items-center">
            <label className="text-sm font-medium text-slate-300">Total Students to Group</label>
            <input type="number" name="total_students" value={formData.total_students} onChange={handleInputChange} className="w-20 p-2 bg-slate-800 border border-slate-600 text-white rounded text-right focus:ring-2 focus:ring-indigo-500 outline-none" />
          </div>
          
          <div className="flex justify-between items-center">
            <label className="text-sm font-medium text-slate-300">Maximum Team Size</label>
            <input type="number" name="max_team_size" value={formData.max_team_size} onChange={handleInputChange} className="w-20 p-2 bg-slate-800 border border-slate-600 text-white rounded text-right focus:ring-2 focus:ring-indigo-500 outline-none" />
          </div>

          <div className="flex justify-between items-center">
            <label className="text-sm font-medium text-slate-300">Maximum Number of Groups</label>
            <input type="number" name="max_groups" value={formData.max_groups} onChange={handleInputChange} className="w-20 p-2 bg-slate-800 border border-slate-600 text-white rounded text-right focus:ring-2 focus:ring-indigo-500 outline-none" />
          </div>
        </div>

        {/* Dynamic Project Tech Requirements */}
        <div className="space-y-4 bg-slate-900 p-5 rounded-lg border border-slate-700">
          <h3 className="font-semibold text-emerald-400">Project Tech Requirements (1-5)</h3>
          
          {/* Active Requirements List */}
          <div className="space-y-2 mb-4 max-h-32 overflow-y-auto pr-2">
            {techList.map((item, idx) => (
              <div key={idx} className="flex justify-between items-center bg-slate-800 p-2 rounded border border-slate-700 text-sm">
                <div className="flex items-center space-x-2">
                  <span className="text-xs text-slate-400 font-mono w-20">{item.category}</span>
                  <span className="font-semibold text-slate-200">{item.tech}</span>
                </div>
                <div className="flex items-center space-x-3">
                  <span className="bg-indigo-900 text-indigo-300 px-2 py-1 rounded text-xs font-bold">Lvl {item.score}</span>
                  <button onClick={() => handleRemoveTech(item.tech)} className="text-red-400 hover:text-red-300 font-bold">×</button>
                </div>
              </div>
            ))}
          </div>

          {/* Add New Tech Controls */}
          <div className="flex space-x-2 pt-2 border-t border-slate-700">
            <select value={selectedCategory} onChange={handleCategoryChange} className="w-1/3 p-2 bg-slate-800 border border-slate-600 text-white rounded text-xs outline-none">
              {Object.keys(techCategories).map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
            
            <select value={selectedTech} onChange={(e) => setSelectedTech(e.target.value)} className="w-1/3 p-2 bg-slate-800 border border-slate-600 text-white rounded text-xs outline-none">
              {techCategories[selectedCategory].map(tech => (
                <option key={tech} value={tech}>{tech}</option>
              ))}
            </select>
            
            <input type="number" min="1" max="5" value={selectedScore} onChange={(e) => setSelectedScore(parseInt(e.target.value) || 1)} className="w-16 p-2 bg-slate-800 border border-slate-600 text-white rounded text-center text-xs outline-none" />
            
            <button onClick={handleAddTech} className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded">
              + Add
            </button>
          </div>
        </div>
      </div>

      <div className="mt-8 text-center">
        <button
          onClick={optimizeTeams} disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-3 px-8 rounded-lg shadow-lg transition-all duration-200 disabled:opacity-50"
        >
          {loading ? 'Running Genetic Draft...' : 'Generate Optimal Teams'}
        </button>
      </div>

      {result && (
        <div className="mt-10 animate-fade-in-up">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-xl font-bold text-white">Generated Roster</h3>
            <span className="bg-indigo-900/50 text-indigo-300 border border-indigo-500/50 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wide">
              {result.algorithm}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {result.teams.map((team, index) => {

              const chartData = [
                { subject: 'React', value: team.stats.total_react },
                { subject: 'NodeJS', value: team.stats.total_node },
                { subject: 'Python', value: team.stats.total_python },
                { subject: 'MongoDB', value: team.stats.total_mongo },
              ];

              return (
                <div key={index} className="bg-slate-900 border-2 border-slate-700 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow">

                  <div className="bg-slate-800 text-white p-4 flex flex-col space-y-3">
                    <div className="flex justify-between items-center">
                      <h4 className="font-bold text-lg">{team.team_id}</h4>
                      <div className="flex space-x-4 text-right">
                        <div>
                          <p className="text-xs text-slate-400">Diversity</p>
                          <p className="font-mono font-bold text-blue-400">{team.stats.diversity_score}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-400">Avg Power</p>
                          <p className="font-mono font-bold text-emerald-400">{team.stats.avg_power}</p>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex justify-between items-center bg-slate-900 rounded p-2 border border-slate-700">
                      <span className="text-xs font-semibold text-slate-300">Project Feasibility</span>
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-sm font-bold text-white">{team.stats.feasibility_score}%</span>
                        <span className={`text-[10px] uppercase font-bold px-2 py-1 rounded tracking-wide ${
                          team.stats.risk_level === 'Low Risk' ? 'bg-emerald-900/80 text-emerald-400 border border-emerald-500/50' : 
                          team.stats.risk_level === 'Medium Risk' ? 'bg-amber-900/80 text-amber-400 border border-amber-500/50' : 
                          'bg-red-900/80 text-red-400 border border-red-500/50'
                        }`}>
                          {team.stats.risk_level}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="h-48 w-full bg-slate-800 border-b border-slate-700 p-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
                        <PolarGrid stroke="#475569" />
                        <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 11, fontWeight: 600 }} />
                        <Radar name="Skills" dataKey="value" stroke="#6366f1" fill="#4f46e5" fillOpacity={0.5} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="p-4 space-y-3 max-h-48 overflow-y-auto bg-slate-900">
                    {team.members.map((member, mIdx) => (
                      <div key={mIdx} className="flex justify-between items-center p-2 bg-slate-800 rounded border border-slate-700 shadow-sm">
                        <div className="flex flex-col">
                          <span className="font-mono text-sm text-slate-300">{member.student_id}</span>
                          <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                            {member.ethnicity}
                          </span>
                        </div>
                        <span className="font-mono text-sm font-bold text-indigo-400">{member.power_score}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}