import { useState } from 'react';
import axios from 'axios';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend } from 'recharts';

export default function TeamOptimizer() {
  const [formData, setFormData] = useState({ max_team_size: 4, max_groups: 3, total_students: 12 });
  const [techList, setTechList] = useState([
    { category: 'Frontend', tech: 'React', score: 4 },
    { category: 'Backend', tech: 'NodeJS', score: 3 },
    { category: 'Data/ML', tech: 'Python', score: 2 },
    { category: 'Database', tech: 'MongoDB', score: 4 }
  ]);
  const [selectedCategory, setSelectedCategory] = useState('Database');
  const [selectedTech, setSelectedTech] = useState('MySQL');
  const [selectedScore, setSelectedScore] = useState(3);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const techCategories = {
    Frontend: ['React', 'HTML/CSS', 'Angular', 'Vue'],
    Backend: ['NodeJS', 'Express', 'Java', 'PHP', 'FastAPI'],
    Database: ['MongoDB', 'MySQL', 'PostgreSQL', 'Firebase'],
    'Data/ML': ['Python', 'TensorFlow', 'Pandas']
  };

  const handleInputChange = (e) => setFormData({ ...formData, [e.target.name]: parseInt(e.target.value) || 0 });

  const handleCategoryChange = (e) => {
    const category = e.target.value;
    setSelectedCategory(category);
    setSelectedTech(techCategories[category][0]);
  };

  const handleAddTech = () => {
    if (techList.some((item) => item.tech === selectedTech)) {
      alert(`${selectedTech} is already in the requirements list!`);
      return;
    }
    setTechList([...techList, { category: selectedCategory, tech: selectedTech, score: selectedScore }]);
  };

  const handleRemoveTech = (tech) => setTechList(techList.filter((item) => item.tech !== tech));

  const optimizeTeams = async () => {
    if (techList.length === 0) {
      alert('Add at least one project technology requirement.');
      return;
    }

    setLoading(true);
    const topic_requirements = {};
    techList.forEach((item) => {
      topic_requirements[item.tech] = item.score;
    });

    try {
      const response = await axios.post('http://127.0.0.1:8003/api/ml/optimize-teams', {
        ...formData,
        topic_requirements
      });
      setResult(response.data);
    } catch (error) {
      console.error('Error optimizing teams:', error);
      const detail = error.response?.data?.detail;
      const message = typeof detail === 'string'
        ? detail
        : detail?.message || 'Failed to connect to the ML engine.';
      alert(message);
    } finally {
      setLoading(false);
    }
  };

  const technicalStyle = (fit) => {
    if (fit === 'High') return 'bg-emerald-900/60 text-emerald-300 border-emerald-500/50';
    if (fit === 'Moderate') return 'bg-amber-900/60 text-amber-300 border-amber-500/50';
    return 'bg-red-900/60 text-red-300 border-red-500/50';
  };

  const academicStyle = (level) => {
    if (level === 'High') return 'text-emerald-400';
    if (level === 'Moderate') return 'text-amber-400';
    return 'text-red-400';
  };

  return (
    <div className="max-w-6xl mx-auto p-6 bg-slate-800 rounded-xl shadow-lg mt-10 mb-20 text-slate-200 border border-slate-700">
      <h2 className="text-2xl font-bold text-white mb-2">Multi-Objective Team Formation</h2>
      <p className="text-sm text-slate-400 mb-6 border-b border-slate-600 pb-4">
        NSGA-II balances technical coverage, skill complementarity, academic preparedness and demographic diversity.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4 bg-slate-900 p-5 rounded-lg border border-slate-700">
          <h3 className="font-semibold text-indigo-400">Class Constraints</h3>

          {[
            ['total_students', 'Total Students to Group'],
            ['max_team_size', 'Maximum Team Size'],
            ['max_groups', 'Maximum Number of Groups']
          ].map(([name, label]) => (
            <div key={name} className="flex justify-between items-center">
              <label className="text-sm font-medium text-slate-300">{label}</label>
              <input
                type="number"
                min="1"
                name={name}
                value={formData[name]}
                onChange={handleInputChange}
                className="w-20 p-2 bg-slate-800 border border-slate-600 text-white rounded text-right focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          ))}
        </div>

        <div className="space-y-4 bg-slate-900 p-5 rounded-lg border border-slate-700">
          <h3 className="font-semibold text-emerald-400">Project Tech Requirements (1-5)</h3>

          <div className="space-y-2 mb-4 max-h-32 overflow-y-auto pr-2">
            {techList.map((item) => (
              <div key={item.tech} className="flex justify-between items-center bg-slate-800 p-2 rounded border border-slate-700 text-sm">
                <div className="flex items-center space-x-2">
                  <span className="text-xs text-slate-400 font-mono w-20">{item.category}</span>
                  <span className="font-semibold text-slate-200">{item.tech}</span>
                </div>

                <div className="flex items-center space-x-3">
                  <span className="bg-indigo-900 text-indigo-300 px-2 py-1 rounded text-xs font-bold">
                    Lvl {item.score}
                  </span>

                  <button
                    type="button"
                    onClick={() => handleRemoveTech(item.tech)}
                    className="text-red-400 hover:text-red-300 font-bold"
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="flex space-x-2 pt-2 border-t border-slate-700">
            <select
              value={selectedCategory}
              onChange={handleCategoryChange}
              className="w-1/3 p-2 bg-slate-800 border border-slate-600 text-white rounded text-xs outline-none"
            >
              {Object.keys(techCategories).map((category) => (
                <option key={category} value={category}>{category}</option>
              ))}
            </select>

            <select
              value={selectedTech}
              onChange={(e) => setSelectedTech(e.target.value)}
              className="w-1/3 p-2 bg-slate-800 border border-slate-600 text-white rounded text-xs outline-none"
            >
              {techCategories[selectedCategory].map((tech) => (
                <option key={tech} value={tech}>{tech}</option>
              ))}
            </select>

            <input
              type="number"
              min="1"
              max="5"
              value={selectedScore}
              onChange={(e) => setSelectedScore(Math.min(5, Math.max(1, parseInt(e.target.value) || 1)))}
              className="w-16 p-2 bg-slate-800 border border-slate-600 text-white rounded text-center text-xs outline-none"
            />

            <button
              type="button"
              onClick={handleAddTech}
              className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded"
            >
              + Add
            </button>
          </div>
        </div>
      </div>

      <div className="mt-8 text-center">
        <button
          onClick={optimizeTeams}
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-3 px-8 rounded-lg shadow-lg transition-all duration-200 disabled:opacity-50"
        >
          {loading ? 'Running NSGA-II Optimization...' : 'Generate Optimal Teams'}
        </button>
      </div>

      {result && (
        <div className="mt-10 animate-fade-in-up">
          <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-3 mb-5">
            <div>
              <h3 className="text-xl font-bold text-white">Generated Roster</h3>
              <p className="text-xs text-slate-400 mt-1">
                Technical topic feasibility and academic preparedness are reported separately.
              </p>
            </div>

            <span className="bg-indigo-900/50 text-indigo-300 border border-indigo-500/50 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wide">
              {result.algorithm}
            </span>
          </div>

          {result.optimization && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
                <p className="text-xs text-slate-500">Population</p>
                <p className="text-lg font-bold text-white">{result.optimization.population_size}</p>
              </div>

              <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
                <p className="text-xs text-slate-500">Generations</p>
                <p className="text-lg font-bold text-white">{result.optimization.generations}</p>
              </div>

              <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
                <p className="text-xs text-slate-500">Pareto Solutions</p>
                <p className="text-lg font-bold text-indigo-400">{result.optimization.pareto_front_size}</p>
              </div>

              <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
                <p className="text-xs text-slate-500">Academic Imbalance</p>
                <p className="text-lg font-bold text-emerald-400">
                  {result.optimization.recommended_objectives?.academic_imbalance}
                </p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {result.teams.map((team) => {
              const coverage = team.stats.technical_coverage || [];

              const chartData = techList.map((item) => {
                const skill = coverage.find((entry) => entry.skill === item.tech);

                return {
                  subject: item.tech,
                  teamAverage: skill?.team_average ?? 0,
                  required: item.score
                };
              });

              return (
                <div
                  key={team.team_id}
                  className="bg-slate-900 border-2 border-slate-700 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="bg-slate-800 text-white p-4 space-y-3">
                    <div className="flex justify-between items-start">
                      <h4 className="font-bold text-lg">{team.team_id}</h4>

                      <div className="flex gap-4 text-right">
                        <div>
                          <p className="text-[10px] uppercase text-slate-500">Diversity</p>
                          <p className="font-mono font-bold text-blue-400">{team.stats.diversity_score}</p>
                        </div>

                        <div>
                          <p className="text-[10px] uppercase text-slate-500">Redundancy</p>
                          <p className="font-mono font-bold text-violet-400">{team.stats.skill_redundancy}</p>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
                        <p className="text-[10px] uppercase tracking-wide text-slate-400">
                          Technical Topic Feasibility
                        </p>

                        <p className="text-2xl font-bold text-white mt-1">
                          {team.stats.technical_topic_feasibility}%
                        </p>

                        <span
                          className={`inline-block mt-2 text-[10px] uppercase font-bold px-2 py-1 rounded border ${technicalStyle(team.stats.technical_fit)}`}
                        >
                          {team.stats.technical_fit} Technical Fit
                        </span>
                      </div>

                      <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
                        <p className="text-[10px] uppercase tracking-wide text-slate-400">
                          Academic Preparedness
                        </p>

                        <p className={`text-2xl font-bold mt-1 ${academicStyle(team.stats.academic_preparedness_level)}`}>
                          {team.stats.academic_preparedness}%
                        </p>

                        <p className="text-[10px] text-slate-500 mt-2">
                          XGBoost: {team.stats.academic_preparedness_level}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="h-52 w-full bg-slate-800 border-b border-slate-700 p-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart cx="50%" cy="50%" outerRadius="68%" data={chartData}>
                        <PolarGrid stroke="#475569" />
                        <PolarAngleAxis
                          dataKey="subject"
                          tick={{ fill: '#94a3b8', fontSize: 10, fontWeight: 600 }}
                        />
                        <PolarRadiusAxis domain={[0, 5]} tick={false} axisLine={false} />

                        <Radar
                          name="Team Average"
                          dataKey="teamAverage"
                          stroke="#6366f1"
                          fill="#4f46e5"
                          fillOpacity={0.45}
                        />

                        <Radar
                          name="Required"
                          dataKey="required"
                          stroke="#f59e0b"
                          fill="#f59e0b"
                          fillOpacity={0.08}
                        />

                        <Legend wrapperStyle={{ fontSize: 10 }} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="p-4 space-y-2 max-h-56 overflow-y-auto bg-slate-900">
                    {team.members.map((member) => (
                      <div
                        key={member.student_id}
                        className="flex justify-between items-center p-2 bg-slate-800 rounded border border-slate-700 shadow-sm"
                      >
                        <div className="min-w-0 pr-3">
                          <p className="font-mono text-sm text-slate-300">
                            {member.student_id}
                          </p>

                          <p className="text-[10px] uppercase font-bold text-slate-500 tracking-wider truncate">
                            {member.demographics}
                          </p>

                          <p className="text-[10px] text-slate-500">
                            {member.profile_source}
                          </p>
                        </div>

                        <div className="text-right shrink-0">
                          <p className="font-mono text-sm font-bold text-amber-400">
                            {member.academic_preparedness}%
                          </p>

                          <p className="text-[9px] uppercase text-slate-500">
                            Academic
                          </p>
                        </div>
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