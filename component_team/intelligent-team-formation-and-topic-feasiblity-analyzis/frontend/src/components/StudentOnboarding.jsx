import { useState } from 'react';
import axios from 'axios';

export default function StudentOnboarding() {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const [formData, setFormData] = useState({
    studentId: 'STU-0001',
    gender: 'Male',
    religion: 'Buddhism',
    livingCity: 'Colombo',
    Hours_Studied: '20',
    Attendance: '90',
    Previous_Scores: '85',
    Motivation_Level: 'High',
    projectHistory:
      'Developed a MERN stack web application using React, Node.js, Express and MongoDB. Implemented REST APIs, authentication, database operations and frontend user interfaces. Also worked with Python and PostgreSQL in previous academic projects.'
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;

    setFormData((previousData) => ({
      ...previousData,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setSuccess(false);

    try {
      const response = await axios.post(
        'http://127.0.0.1:8003/api/ml/extract-skills',
        formData
      );

      console.log('AI Extracted Vector:', response.data);

      const skills = response.data.extracted_skills;

      let alertMessage =
        'Success! AI mapped your text to the following skill levels:\n\n';

      Object.keys(skills).forEach((key) => {
        const cleanName = key.replace('Skill_', '');
        alertMessage += `${cleanName}: ${skills[key]}/5\n`;
      });

      alert(alertMessage);
      setSuccess(true);
    } catch (error) {
      console.error('NLP Extraction failed:', error);

      if (
        error.response &&
        error.response.data &&
        error.response.data.detail
      ) {
        const detail = error.response.data.detail;

        if (typeof detail === 'string') {
          alert(detail);
        } else {
          alert(
            'The profile could not be processed. Please check the entered information.'
          );
        }
      } else {
        alert(
          'Failed to connect to the NLP engine. Make sure the FastAPI server is running!'
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 bg-slate-800 rounded-xl shadow-lg mt-10 border border-slate-700 text-slate-200">
      <h2 className="text-2xl font-bold text-white mb-2">
        Student Profile Setup
      </h2>

      <p className="text-sm text-slate-400 mb-6 border-b border-slate-600 pb-4">
        Create your student profile and allow the semantic engine to identify
        your technical competencies from your previous project experience.
      </p>

      <form onSubmit={handleSubmit} className="space-y-8">
        <div className="bg-slate-900 border border-slate-700 rounded-lg p-5 space-y-4">
          <h3 className="font-semibold text-indigo-400 border-b border-slate-700 pb-2">
            Student Information
          </h3>

          <div className="md:w-1/2">
            <label className="text-sm font-semibold text-slate-300">
              Student ID
            </label>

            <input
              type="text"
              name="studentId"
              required
              placeholder="e.g. STU-0001"
              value={formData.studentId}
              onChange={handleInputChange}
              className="w-full p-3 mt-1 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none"
            />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-700 rounded-lg p-5 space-y-4">
          <h3 className="font-semibold text-blue-400 border-b border-slate-700 pb-2">
            Diversity Information
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-300">
                Gender
              </label>

              <select
                name="gender"
                required
                value={formData.gender}
                onChange={handleInputChange}
                className="w-full p-3 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Non-binary">Non-binary</option>
                <option value="Prefer not to say">Prefer not to say</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-300">
                Religion
              </label>

              <select
                name="religion"
                required
                value={formData.religion}
                onChange={handleInputChange}
                className="w-full p-3 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                <option value="Buddhism">Buddhism</option>
                <option value="Hinduism">Hinduism</option>
                <option value="Islam">Islam</option>
                <option value="Christianity">Christianity</option>
                <option value="Other">Other</option>
                <option value="Prefer not to say">Prefer not to say</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-300">
                Living City
              </label>

              <input
                type="text"
                name="livingCity"
                required
                placeholder="e.g. Colombo"
                value={formData.livingCity}
                onChange={handleInputChange}
                className="w-full p-3 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-700 rounded-lg p-5 space-y-4">
          <div>
            <h3 className="font-semibold text-emerald-400">
              Academic Information
            </h3>

            <p className="text-xs text-slate-400 mt-1">
              These values are used by the academic balance and prediction
              components.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-300">
                Study Hours per Week
              </label>

              <input
                type="number"
                name="Hours_Studied"
                required
                min="0"
                max="100"
                step="1"
                placeholder="e.g. 20"
                value={formData.Hours_Studied}
                onChange={handleInputChange}
                className="w-full p-3 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-emerald-500 outline-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-300">
                Attendance (%)
              </label>

              <input
                type="number"
                name="Attendance"
                required
                min="0"
                max="100"
                step="1"
                placeholder="e.g. 85"
                value={formData.Attendance}
                onChange={handleInputChange}
                className="w-full p-3 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-emerald-500 outline-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-300">
                Previous Academic Score (%)
              </label>

              <input
                type="number"
                name="Previous_Scores"
                required
                min="0"
                max="100"
                step="1"
                placeholder="e.g. 75"
                value={formData.Previous_Scores}
                onChange={handleInputChange}
                className="w-full p-3 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-emerald-500 outline-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-sm font-semibold text-slate-300">
                Motivation Level
              </label>

              <select
                name="Motivation_Level"
                required
                value={formData.Motivation_Level}
                onChange={handleInputChange}
                className="w-full p-3 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-emerald-500 outline-none"
              >
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
              </select>
            </div>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-700 rounded-lg p-5 space-y-2">
          <label className="text-sm font-semibold text-slate-300 flex flex-col md:flex-row md:justify-between gap-1">
            <span>Previous Project / Technical Experience</span>

            <span className="text-xs text-indigo-400 font-mono">
              SBERT Semantic Engine
            </span>
          </label>

          <p className="text-xs text-slate-400 mb-2">
            Describe or paste information about projects you have previously
            completed, the technologies you used, and the work you performed.
          </p>

          <textarea
            name="projectHistory"
            required
            rows="6"
            value={formData.projectHistory}
            onChange={handleInputChange}
            className="w-full p-4 bg-slate-800 border border-slate-600 rounded-lg text-slate-300 leading-relaxed focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none"
          />
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-8 rounded-lg shadow-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Analyzing Semantics...' : 'Generate AI Skill Vector'}
          </button>
        </div>

        {success && (
          <div className="p-4 mt-4 bg-emerald-900/50 border border-emerald-500/50 text-emerald-400 rounded-lg text-center text-sm font-semibold">
            Profile processed successfully. Your technical skill vector has been
            extracted.
          </div>
        )}
      </form>
    </div>
  );
}