import { useState } from 'react';
import axios from 'axios'; 

export default function StudentOnboarding() {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  
  // UPDATE: Replaced 'ethnicity' with the 3 new demographic fields
  const [formData, setFormData] = useState({
    studentId: '',
    gender: '',
    religion: '',
    livingCity: '',
    projectHistory: "During my previous semester, I worked as a full-stack developer on a university research project building an intelligent dashboard. I was responsible for the frontend, which I built entirely using React and styled with modern CSS frameworks. For the backend, I designed RESTful APIs using Node.js and Express, securely storing all our user data and logs in a MongoDB database. Recently, I have also been expanding my data science skills by writing microservices in Python to process and clean large datasets before they are sent to the client."
  });

  const handleInputChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setSuccess(false);
    
    try {
      // Send the text and new demographic data to the SBERT backend
      const response = await axios.post('http://127.0.0.1:8003/api/ml/extract-skills', formData);
      
      console.log("AI Extracted Vector:", response.data);
      
      const skills = response.data.extracted_skills;
      alert(`Success! AI mapped your text to:\n\nReact: ${skills.Skill_React}/5\nNodeJS: ${skills.Skill_NodeJS}/5\nPython: ${skills.Skill_Python}/5\nMongoDB: ${skills.Skill_MongoDB}/5`);
      
      setSuccess(true);
    } catch (error) {
      console.error("NLP Extraction failed:", error);
      alert("Failed to connect to the NLP engine. Make sure the FastAPI server is running!");
    }
    
    setLoading(false);
  };

  return (
    <div className="max-w-3xl mx-auto p-6 bg-slate-800 rounded-xl shadow-lg mt-10 border border-slate-700 text-slate-200">
      <h2 className="text-2xl font-bold text-white mb-2">Student Profile Setup</h2>
      <p className="text-sm text-slate-400 mb-6 border-b border-slate-600 pb-4">
        Our AI will automatically map your experience to the required project vectors.
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        
        {/* Basic Info Section */}
        <div className="space-y-4">
          <div className="md:w-1/2">
            <label className="text-sm font-semibold text-slate-300">Student ID</label>
            <input 
              type="text" 
              name="studentId" 
              required
              placeholder="e.g., STU-9921"
              value={formData.studentId} 
              onChange={handleInputChange} 
              className="w-full p-3 mt-1 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none"
            />
          </div>

          {/* NEW: Multi-Dimensional Demographics for Novelty Integration */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-300">Gender</label>
              <select 
                name="gender" 
                required
                value={formData.gender} 
                onChange={handleInputChange} 
                className="w-full p-3 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                <option value="" disabled>Select Gender...</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Non-binary">Non-binary</option>
                <option value="Prefer not to say">Prefer not to say</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-300">Religion</label>
              <select 
                name="religion" 
                required
                value={formData.religion} 
                onChange={handleInputChange} 
                className="w-full p-3 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                <option value="" disabled>Select Religion...</option>
                <option value="Buddhism">Buddhism</option>
                <option value="Hinduism">Hinduism</option>
                <option value="Islam">Islam</option>
                <option value="Christianity">Christianity</option>
                <option value="Other">Other</option>
                <option value="Prefer not to say">Prefer not to say</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-300">Living City</label>
              <input 
                type="text" 
                name="livingCity" 
                required
                placeholder="e.g., Colombo"
                value={formData.livingCity} 
                onChange={handleInputChange} 
                className="w-full p-3 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          </div>
        </div>

        {/* The SBERT NLP Input Section */}
        <div className="space-y-2 pt-2">
          <label className="text-sm font-semibold text-slate-300 flex justify-between">
            <span>Academic & Project History</span>
            <span className="text-xs text-indigo-400 font-mono">NLP Semantic Engine Active</span>
          </label>
          <p className="text-xs text-slate-400 mb-2">
            Describe your past projects, the technologies you used, and your role. Be as detailed as possible.
          </p>
          <textarea 
            name="projectHistory"
            required
            rows="6"
            value={formData.projectHistory}
            onChange={handleInputChange}
            className="w-full p-4 bg-slate-900 border border-slate-600 rounded-lg text-slate-300 leading-relaxed focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none"
          ></textarea>
        </div>

        {/* Submit Button */}
        <div className="pt-4">
          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-8 rounded-lg shadow-lg transition-all duration-200 disabled:opacity-50"
          >
            {loading ? 'Analyzing Semantics...' : 'Generate AI Skill Vector'}
          </button>
        </div>

        {success && (
          <div className="p-4 mt-4 bg-emerald-900/50 border border-emerald-500/50 text-emerald-400 rounded-lg text-center text-sm font-semibold">
            Profile processed! Your skill vectors have been extracted and saved.
          </div>
        )}
      </form>
    </div>
  );
}