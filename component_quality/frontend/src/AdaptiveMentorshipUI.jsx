import { useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

export default function AdaptiveMentorshipUI() {
  const [studentId, setStudentId] = useState("");
  const [version, setVersion] = useState("Version 1");
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiData, setApiData] = useState(null);
  const [error, setError] = useState("");
  const [exportingPdf, setExportingPdf] = useState(false);

  const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8001";

  const readErrorMessage = async (response) => {
    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
      try {
        const payload = await response.json();

        if (typeof payload?.detail === "string") return payload.detail;
        if (typeof payload?.error === "string") return payload.error;
        if (Array.isArray(payload?.detail)) {
          return payload.detail
            .map((item) => item?.msg || item?.message || JSON.stringify(item))
            .join("; ");
        }
        if (typeof payload?.message === "string") return payload.message;

        return JSON.stringify(payload);
      } catch (parseError) {
        console.error("Failed to parse JSON error response:", parseError);
      }
    }

    try {
      const text = await response.text();
      return text || `Request failed with status ${response.status}`;
    } catch (textError) {
      console.error("Failed to read error response text:", textError);
      return `Request failed with status ${response.status}`;
    }
  };

  const detectStudentId = async (file) => {
    if (!file) return null;
    try {
      const formData = new FormData();
      formData.append("file", file);

      const resp = await fetch(`${API_BASE_URL}/detect-student-id`, {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) return null;
      const payload = await resp.json();
      return payload?.detected_student_id || null;
    } catch (err) {
      console.error("Student ID detection failed:", err);
      return null;
    }
  };

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
    if (!file) return;

    // Try to auto-detect student ID on upload for convenience.
    try {
      const detected = await detectStudentId(file);
      if (detected) setStudentId(detected);
    } catch (err) {
      console.warn("ID auto-detection failed on upload.", err);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      setError("Please choose a PDF report first.");
      return;
    }

    if (!studentId || !String(studentId).trim()) {
      setError("Please enter or confirm Student ID before analysis.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("student_id", studentId);
      formData.append("version", version);

      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const backendError = await readErrorMessage(response);
        console.error("Backend analysis error:", {
          status: response.status,
          statusText: response.statusText,
          backendError,
        });
        throw new Error(
          `Analysis failed (${response.status} ${response.statusText}): ${backendError}`
        );
      }

      const data = await response.json();
      setApiData(data);

      // If backend detected a student id and frontend field is empty,
      // auto-fill it while keeping the field editable for corrections.
      if (data?.detected_student_id && (!studentId || !String(studentId).trim())) {
        setStudentId(data.detected_student_id);
      }
    } catch (err) {
      console.error("Analyze request failed:", err);

      if (err instanceof TypeError) {
        setError(
          `Unable to reach ${API_BASE_URL}/analyze. ${
            err.message || "A network or CORS error occurred."
          }`
        );
      } else {
        setError(err.message || "Something went wrong while analyzing the report.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleExportTxt = () => {
    if (!apiData?.text) return;

    const blob = new Blob([apiData.text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "feedback_report.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportPdf = async () => {
    setError("");

    if (!apiData) {
      setError("Please analyze a report before exporting PDF.");
      return;
    }

    setExportingPdf(true);

    try {
      const response = await fetch(`${API_BASE_URL}/export-report`, {
        method: "GET",
      });

      if (!response.ok) {
        const backendError = await readErrorMessage(response);
        throw new Error(
          `Export failed (${response.status} ${response.statusText}): ${backendError}`
        );
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "feedback_report.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export report failed:", err);
      setError(err.message || "Failed to export PDF report.");
    } finally {
      setExportingPdf(false);
    }
  };

  const sectionScores = apiData?.score_summary?.section_scores || [];
  const weaknesses = apiData?.weaknesses || [];
  const recommendations = apiData?.recommendations || {};
  const modelMetrics = apiData?.model_metrics || {
    mae: 0.5827,
    rmse: 0.72,
    r2_score: 0.5003,
    model_type: "Random Forest Regressor",
    dataset: "ASAP 2.0",
  };
  const progress = apiData?.progress_result || null;

  const overall = {
    score: Number(apiData?.hybrid_result?.final_score ?? 0),
    grade: apiData?.hybrid_result?.grade ?? "-",
    status: apiData?.hybrid_result?.status ?? "Waiting",
    semantic: Number(apiData?.score_summary?.overall_score ?? 0),
    ml: Number(apiData?.ml_result?.normalized_ml_score ?? 0),
  };

  const strongestSection = useMemo(() => {
    if (!sectionScores.length) return null;
    return [...sectionScores].sort((a, b) => (b?.raw_score ?? 0) - (a?.raw_score ?? 0))[0];
  }, [sectionScores]);

  const weakestSection = useMemo(() => {
    if (!sectionScores.length) return null;
    return [...sectionScores].sort((a, b) => (a?.raw_score ?? 0) - (b?.raw_score ?? 0))[0];
  }, [sectionScores]);

  const complianceStats = useMemo(() => {
    if (!sectionScores.length) return { good: 0, adequate: 0, poor: 0 };
    return sectionScores.reduce(
      (acc, item) => {
        const level = String(item?.compliance_level || "").toLowerCase();
        if (level === "good" || level === "excellent" || level === "strong") acc.good += 1;
        else if (level === "adequate") acc.adequate += 1;
        else acc.poor += 1;
        return acc;
      },
      { good: 0, adequate: 0, poor: 0 }
    );
  }, [sectionScores]);

  const sectionChartData = useMemo(
    () =>
      sectionScores.map((item) => ({
        name:
          String(item?.criterion || "N/A").length > 15
            ? `${String(item?.criterion).slice(0, 15)}...`
            : String(item?.criterion || "N/A"),
        raw: Number(item?.raw_score ?? 0),
        weighted: Number(item?.weighted_score ?? 0),
      })),
    [sectionScores]
  );

  const scoreComparisonData = useMemo(
    () => [
      { name: "Semantic", score: overall.semantic },
      { name: "ML", score: overall.ml },
      { name: "Final", score: overall.score },
    ],
    [overall.semantic, overall.ml, overall.score]
  );

  const complianceChartData = useMemo(
    () => [
      { name: "Good/Strong", value: complianceStats.good, color: "#10b981" },
      { name: "Adequate", value: complianceStats.adequate, color: "#3b82f6" },
      { name: "Poor/Missing", value: complianceStats.poor, color: "#f59e0b" },
    ],
    [complianceStats]
  );

  const progressDisplay = useMemo(() => {
    if (!progress || progress.previous_score == null) {
      return {
        improvement: 0,
        improvementStatus: "First Submission",
        previousScore: 0,
        latestScore: Number(progress?.latest_score ?? overall.score ?? 0),
        message: "No previous version to compare.",
        hasComparison: false,
      };
    }

    const improvement = Number(progress.improvement ?? 0);
    const hasComparison = progress.previous_score != null;

    return {
      improvement: improvement,
      improvementStatus:
        improvement > 0 ? "Improvement Detected" : improvement < 0 ? "Score Changed" : "Similar Performance",
      previousScore: Number(progress.previous_score ?? 0),
      latestScore: Number(progress.latest_score ?? overall.score ?? 0),
      message: progress.message || "Score compared against previous submission.",
      hasComparison: hasComparison,
    };
  }, [progress]);

  const improvement = progressDisplay.improvement;
  const improvementStatus = progressDisplay.improvementStatus;
  const previousScore = progressDisplay.previousScore.toFixed(2);
  const latestScore = progressDisplay.latestScore.toFixed(2);

  const executiveSummary = useMemo(() => {
    if (!apiData) {
      return "Analyze a report to generate an executive summary of academic performance, strengths, and priority improvements.";
    }

    return `This submission achieved a final hybrid score of ${overall.score.toFixed(2)}/100 (${overall.grade}, ${overall.status}). Semantic evaluation is ${overall.semantic.toFixed(
      2
    )}, ML prediction is ${overall.ml.toFixed(2)}. Focus on weaker rubric sections to improve research quality.`;
  }, [apiData, overall.score, overall.grade, overall.status, overall.semantic, overall.ml]);

  const nextSteps = useMemo(() => {
    if (Array.isArray(apiData?.report?.improvement_plan) && apiData.report.improvement_plan.length) {
      return apiData.report.improvement_plan;
    }

    return [
      {
        week: "Week 1",
        action: `Improve ${weakestSection?.criterion || "the weakest section"} with clearer structure and rubric-aligned evidence.`,
      },
      {
        week: "Week 2",
        action: "Strengthen methodology rationale, validity discussion, and citation quality.",
      },
      {
        week: "Week 3",
        action: "Re-run analysis and address remaining high-priority weaknesses.",
      },
    ];
  }, [apiData, weakestSection]);

  const normalizePriority = (weakness) => {
    if (weakness?.priority) return weakness.priority;

    const score = Number(weakness?.score ?? 0);
    if (score > 0 && score <= 1) {
      if (score < 0.4) return "High Priority";
      if (score < 0.6) return "Medium Priority";
      return "Low Priority";
    }

    if (score < 40) return "High Priority";
    if (score < 60) return "Medium Priority";
    return "Low Priority";
  };

  const getBadgeStyle = (value) => {
    if (
      value === "Poor" ||
      value === "Missing Section" ||
      value === "Needs Work" ||
      value === "Attention" ||
      String(value).toLowerCase().includes("high")
    ) {
      return "bg-amber-100 text-amber-700";
    }
    if (value === "Excellent" || value === "Strong" || value === "Good") {
      return "bg-emerald-100 text-emerald-700";
    }
    return "bg-blue-100 text-blue-700";
  };

  const renderResourceItem = (resource, key) => {
    if (typeof resource === "string") {
      return (
        <li
          key={key}
          className="rounded-xl bg-white px-3 py-3 text-sm text-slate-700 shadow-sm ring-1 ring-slate-200"
        >
          {resource}
        </li>
      );
    }

    if (resource && typeof resource === "object") {
      const title = resource.title || resource.name || "Resource";
      const type = resource.type || "resource";
      const url = resource.url || "";

      return (
        <li
          key={key}
          className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200"
        >
          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-2">
              {url ? (
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-blue-700 hover:underline"
                >
                  {title}
                </a>
              ) : (
                <span className="font-medium text-slate-800">{title}</span>
              )}
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
                {type}
              </span>
            </div>

            {url ? (
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="text-xs break-all text-slate-500 hover:text-blue-700 hover:underline"
              >
                {url}
              </a>
            ) : null}
          </div>
        </li>
      );
    }

    return null;
  };

  return (
    <div className="min-h-screen w-full bg-slate-100 text-slate-900">
      {/* Main Container */}
      <div className="mx-auto w-full max-w-[1500px] px-4 py-6 sm:px-6 md:px-8 md:py-8 lg:max-w-[1600px] lg:px-10 lg:py-10">
        
        {/* HEADER SECTION - COMPACT & PROFESSIONAL */}
        <header className="mb-6 rounded-3xl bg-white p-6 shadow-md ring-1 ring-slate-200 md:p-7 lg:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            {/* Left: Title & Description */}
            <div className="flex-1">
              <p className="mb-1 text-xs font-semibold uppercase tracking-[0.15em] text-slate-500 sm:text-sm">
                Adaptive Mentorship System
              </p>
              <h1 className="text-3xl font-bold leading-tight tracking-tight md:text-4xl lg:text-4xl">
                Automated Quality Assessment
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-base">
                Intelligent rubric evaluation, semantic grading, and adaptive mentorship feedback.
              </p>
            </div>

            {/* Right: Score Cards */}
            <div className="grid w-full gap-3 sm:grid-cols-2 lg:w-auto lg:grid-cols-2">
              <div className="flex flex-col justify-center rounded-2xl bg-slate-900 p-5 text-white shadow-md lg:p-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Overall Score</p>
                <p className="mt-1 text-3xl font-bold md:text-3xl lg:text-4xl">{overall.score.toFixed(1)}</p>
              </div>
              <div className="flex flex-col justify-center rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:p-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Grade</p>
                <p className="mt-1 text-2xl font-bold text-slate-900 lg:text-3xl">{overall.grade}</p>
              </div>
              <div className="flex flex-col justify-center rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:p-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Semantic</p>
                <p className="mt-1 text-2xl font-bold text-slate-900 lg:text-3xl">{overall.semantic.toFixed(1)}</p>
              </div>
              <div className="flex flex-col justify-center rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:p-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">ML Score</p>
                <p className="mt-1 text-2xl font-bold text-slate-900 lg:text-3xl">{overall.ml.toFixed(1)}</p>
              </div>
            </div>
          </div>
        </header>

        {/* MAIN GRID LAYOUT - 4 COL LEFT, 8 COL RIGHT */}
        <div className="grid w-full grid-cols-1 gap-6 md:gap-7 lg:grid-cols-12 lg:gap-8">
          
          {/* LEFT COLUMN - UPLOAD & ANALYTICS */}
          <section className="space-y-6 lg:col-span-4 md:space-y-7 order-2 lg:order-1">
            
            {/* Upload Panel - COMPACT */}
            <div className="rounded-3xl bg-white p-6 shadow-md ring-1 ring-slate-200 md:p-7 lg:p-8">
              <h2 className="text-lg font-semibold md:text-xl lg:text-lg">Upload Report</h2>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">
                Submit PDF for analysis
              </p>

              {/* File Upload Box - Compact */}
              <div className="mt-5 flex min-h-[160px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center sm:min-h-[160px]">
                <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
                  <span className="text-2xl font-bold text-slate-600">PDF</span>
                </div>
                <p className="text-sm font-semibold text-slate-800">
                  {selectedFile ? selectedFile.name : "Choose PDF"}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">Max 20MB</p>

                <input
                  type="file"
                  accept=".pdf"
                  className="mt-4 block text-xs"
                  onChange={handleFileSelect}
                />
              </div>

              {/* Form Fields - Compact */}
                <div className="mt-6 space-y-3">
                  <div>
                    <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-700">
                      Student ID
                    </label>
                    <input
                      value={studentId}
                      onChange={(e) => setStudentId(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-500"
                      placeholder="Enter Student ID e.g., IT22101624"
                    />
                  </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-700">
                    Version
                  </label>
                  <select
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-500"
                  >
                    <option>Version 1</option>
                    <option>Version 2</option>
                    <option>Version 3</option>
                  </select>
                </div>

                <button
                  onClick={handleAnalyze}
                  disabled={loading}
                  className="w-full rounded-lg bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white shadow-md transition hover:opacity-90 disabled:opacity-60"
                >
                  {loading ? "Analyzing..." : "Analyze"}
                </button>

                {error && (
                  <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
                    {error}
                  </p>
                )}
              </div>
            </div>

            {/* Analytics Overview - Dark Theme */}
            <div className="rounded-3xl bg-slate-900 p-6 text-white shadow-md md:p-7 lg:p-8">
              <h2 className="text-lg font-semibold md:text-xl lg:text-lg">Analytics</h2>
              <p className="mt-1 text-xs leading-relaxed text-slate-400 md:text-sm">
                Quick evaluation summary
              </p>

              {/* Progress Bars */}
              <div className="mt-6 space-y-5">
                <div>
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <p className="text-xs font-medium text-slate-300">Semantic</p>
                    <p className="text-xs font-semibold text-white">{overall.semantic.toFixed(1)}%</p>
                  </div>
                  <div className="h-2 rounded-full bg-slate-700">
                    <div
                      className="h-2 rounded-full bg-blue-500 transition-all"
                      style={{ width: `${Math.max(0, Math.min(100, overall.semantic))}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <p className="text-xs font-medium text-slate-300">ML Score</p>
                    <p className="text-xs font-semibold text-white">{overall.ml.toFixed(1)}%</p>
                  </div>
                  <div className="h-2 rounded-full bg-slate-700">
                    <div
                      className="h-2 rounded-full bg-emerald-400 transition-all"
                      style={{ width: `${Math.max(0, Math.min(100, overall.ml))}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <p className="text-xs font-medium text-slate-300">Final Score</p>
                    <p className="text-xs font-semibold text-white">{overall.score.toFixed(1)}%</p>
                  </div>
                  <div className="h-2 rounded-full bg-slate-700">
                    <div
                      className="h-2 rounded-full bg-indigo-500 transition-all"
                      style={{ width: `${Math.max(0, Math.min(100, overall.score))}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Info Cards */}
              <div className="mt-6 space-y-3">
                <div className="rounded-lg bg-slate-800 p-3 ring-1 ring-slate-700">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Strongest</p>
                  <p className="mt-1 text-xs font-medium leading-tight text-white truncate">
                    {strongestSection?.criterion || "N/A"}
                  </p>
                </div>

                <div className="rounded-lg bg-slate-800 p-3 ring-1 ring-slate-700">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Weakest</p>
                  <p className="mt-1 text-xs font-medium leading-tight text-white truncate">
                    {weakestSection?.criterion || "N/A"}
                  </p>
                </div>

                <div className="rounded-2xl bg-white/10 p-5 ring-1 ring-white/10">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-slate-300">Progress Tracking</p>
                      <p className="mt-1 text-2xl font-bold text-white">
                        {progressDisplay.improvement > 0
                          ? `+${progressDisplay.improvement.toFixed(1)}%`
                          : `${progressDisplay.improvement.toFixed(1)}%`}
                      </p>
                    </div>

                    <span
                      className={`rounded-full px-3 py-1 text-xs font-semibold ${
                        progressDisplay.improvement > 0
                          ? "bg-emerald-100 text-emerald-700"
                          : progressDisplay.improvement < 0
                          ? "bg-red-100 text-red-700"
                          : "bg-slate-200 text-slate-700"
                      }`}
                    >
                      {progressDisplay.improvementStatus}
                    </span>
                  </div>

                  <p className="mt-3 text-sm leading-6 text-slate-300">
                    {progress?.message || "No previous submission found for comparison."}
                  </p>

                  <div className="mt-5 space-y-4">
                    <div>
                      <div className="mb-2 flex items-center justify-between text-sm">
                        <span className="text-slate-300">Previous Version</span>
                        <span className="font-semibold text-white">
                          {progressDisplay.previousScore.toFixed(2)}
                        </span>
                      </div>
                      <div className="h-3 rounded-full bg-slate-700">
                        <div
                          className="h-3 rounded-full bg-slate-400"
                          style={{ width: `${Math.min(progressDisplay.previousScore, 100)}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="mb-2 flex items-center justify-between text-sm">
                        <span className="text-slate-300">Latest Version</span>
                        <span className="font-semibold text-white">
                          {progressDisplay.latestScore.toFixed(2)}
                        </span>
                      </div>
                      <div className="h-3 rounded-full bg-slate-700">
                        <div
                          className="h-3 rounded-full bg-emerald-400"
                          style={{ width: `${Math.min(progressDisplay.latestScore, 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="rounded-2xl bg-white/10 p-5 ring-1 ring-white/10">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-slate-300">Model Performance</p>
                      <p className="mt-1 text-xl font-bold text-white">
                        {modelMetrics.model_type}
                      </p>
                    </div>

                    <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700">
                      {modelMetrics.dataset}
                    </span>
                  </div>

                  <div className="mt-5 grid grid-cols-3 gap-3">
                    <div className="rounded-xl bg-slate-900/80 p-4 ring-1 ring-slate-700">
                      <p className="text-xs uppercase tracking-wide text-slate-400">MAE</p>
                      <p className="mt-2 text-2xl font-bold text-white">
                        {modelMetrics.mae}
                      </p>
                    </div>

                    <div className="rounded-xl bg-slate-900/80 p-4 ring-1 ring-slate-700">
                      <p className="text-xs uppercase tracking-wide text-slate-400">RMSE</p>
                      <p className="mt-2 text-2xl font-bold text-white">
                        {modelMetrics.rmse}
                      </p>
                    </div>

                    <div className="rounded-xl bg-slate-900/80 p-4 ring-1 ring-slate-700">
                      <p className="text-xs uppercase tracking-wide text-slate-400">R²</p>
                      <p className="mt-2 text-2xl font-bold text-white">
                        {modelMetrics.r2_score}
                      </p>
                    </div>
                  </div>

                  <p className="mt-4 text-sm leading-6 text-slate-300">
                    The ML model is evaluated using regression metrics because it predicts a numeric score rather than a class label.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* RIGHT COLUMN - MAIN DASHBOARD */}
          <section className="space-y-6 lg:col-span-8 md:space-y-7 order-1 lg:order-2">
            
            {/* Rubric Evaluation Table */}
            <div className="rounded-3xl bg-white p-6 shadow-md ring-1 ring-slate-200 md:p-7 lg:p-8">
              <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold md:text-xl lg:text-xl">Rubric Evaluation</h2>
                  <p className="mt-1 text-xs leading-relaxed text-slate-600 sm:text-sm">
                    Semantic scores, raw/weighted contributions, compliance levels
                  </p>
                </div>
                <span className="inline-block rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                  {sectionScores.length} Criteria
                </span>
              </div>

              <div className="overflow-hidden rounded-2xl border border-slate-200 shadow-sm">
                <div className="grid grid-cols-12 gap-2 bg-slate-100 px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-700 sm:text-xs">
                  <div className="col-span-5">Criterion</div>
                  <div className="col-span-2 text-center">Similarity</div>
                  <div className="col-span-2 text-center">Raw</div>
                  <div className="col-span-2 text-center">Weighted</div>
                  <div className="col-span-1 text-center">Level</div>
                </div>

                {sectionScores.length > 0 ? (
                  sectionScores.map((item) => (
                    <div
                      key={item?.criterion || Math.random()}
                      className="grid grid-cols-12 items-center gap-2 border-t border-slate-200 px-4 py-3 text-xs sm:text-sm hover:bg-slate-50 transition"
                    >
                      <div className="col-span-5 font-medium text-slate-800 truncate">
                        {item?.criterion || "N/A"}
                      </div>
                      <div className="col-span-2 text-center text-slate-600">
                        {Number(item?.similarity_score ?? 0).toFixed(3)}
                      </div>
                      <div className="col-span-2 text-center font-semibold text-slate-700">
                        {Number(item?.raw_score ?? 0).toFixed(1)}
                      </div>
                      <div className="col-span-2 text-center font-semibold text-slate-700">
                        {Number(item?.weighted_score ?? 0).toFixed(1)}
                      </div>
                      <div className="col-span-1 text-center">
                        <span
                          className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-bold sm:text-xs ${getBadgeStyle(
                            item?.compliance_level || "-"
                          )}`}
                        >
                          {item?.compliance_level || "-"}
                        </span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="px-4 py-6 text-sm text-slate-500">No analysis yet.</div>
                )}
              </div>
            </div>

            {/* MENTORSHIP REPORT - Academic Layout */}
            <div className="rounded-3xl bg-white p-6 shadow-md ring-1 ring-slate-200 md:p-7 lg:p-8">
              <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-5">
                <div>
                  <h2 className="text-lg font-semibold md:text-xl lg:text-xl">Mentorship Report</h2>
                  <p className="mt-1 text-xs leading-relaxed text-slate-600 sm:text-sm">
                    Academic evaluation with structured feedback and recommendations
                  </p>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={handleExportTxt}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    TXT
                  </button>
                  <button
                    onClick={handleExportPdf}
                    disabled={exportingPdf}
                    className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
                  >
                    {exportingPdf ? "PDF..." : "PDF"}
                  </button>
                </div>
              </div>

              {/* Executive Summary */}
              <div className="mb-6 rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200">
                <h3 className="text-sm font-bold uppercase tracking-wide text-slate-700">Executive Summary</h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-700">
                  {executiveSummary}
                </p>
              </div>

              {/* Score Dashboard Table */}
              <div className="mb-6 overflow-hidden rounded-2xl border border-slate-200 shadow-sm">
                <div className="grid grid-cols-1 gap-px bg-slate-200 sm:grid-cols-3 lg:grid-cols-5">
                  <div className="bg-slate-900 p-4 text-center text-white">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-300">Final</p>
                    <p className="mt-2 text-2xl font-bold">{overall.score.toFixed(1)}</p>
                  </div>
                  <div className="bg-white p-4 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-600">Grade</p>
                    <p className="mt-2 text-2xl font-bold text-slate-900">{overall.grade}</p>
                  </div>
                  <div className="bg-white p-4 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-600">Semantic</p>
                    <p className="mt-2 text-2xl font-bold text-slate-900">{overall.semantic.toFixed(1)}</p>
                  </div>
                  <div className="bg-white p-4 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-600">ML</p>
                    <p className="mt-2 text-2xl font-bold text-slate-900">{overall.ml.toFixed(1)}</p>
                  </div>
                  <div className="bg-slate-100 p-4 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-600">Status</p>
                    <p className="mt-2 text-sm font-bold text-slate-900">{overall.status}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-[28px] bg-white p-6 shadow-sm ring-1 ring-slate-200 lg:p-8">
                <h2 className="text-2xl font-semibold">Student Progress</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600 sm:text-base">
                  Tracks improvement between multiple report submissions.
                </p>

                <div className="mt-6 grid gap-4 sm:grid-cols-3">
                  <div className="rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200">
                    <p className="text-sm text-slate-500">Previous Score</p>
                    <p className="mt-2 text-3xl font-bold text-slate-900">
                      {previousScore}
                    </p>
                  </div>

                  <div className="rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200">
                    <p className="text-sm text-slate-500">Latest Score</p>
                    <p className="mt-2 text-3xl font-bold text-slate-900">
                      {latestScore}
                    </p>
                  </div>

                  <div className="rounded-2xl bg-slate-950 p-5 text-white">
                    <p className="text-sm text-slate-300">Improvement</p>
                    <p className="mt-2 text-3xl font-bold">
                      {improvement > 0 ? `+${improvement.toFixed(1)}%` : `${improvement.toFixed(1)}%`}
                    </p>
                  </div>
                </div>

                <div className="mt-6 rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200">
                  <p className="text-sm leading-6 text-slate-700">
                    {progress?.message || "Upload Version 1 and Version 2 using the same Student ID to calculate improvement."}
                  </p>
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      improvement > 0
                        ? "bg-emerald-100 text-emerald-700"
                        : improvement < 0
                        ? "bg-red-100 text-red-700"
                        : "bg-slate-200 text-slate-700"
                    }`}
                  >
                    {improvementStatus}
                  </span>
                  <span className="text-xs text-slate-500">
                    Version comparison is automatically tracked by student ID.
                  </span>
                </div>
              </div>

              {/* Version Comparison Chart */}
              {progress && (
                <div className="rounded-[28px] bg-white p-6 shadow-sm ring-1 ring-slate-200 lg:p-8">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold">Version Comparison</h3>
                      <p className="mt-1 text-sm text-slate-600">Visual progress between submissions</p>
                    </div>
                    <span
                      className={`rounded-full px-4 py-2 text-sm font-bold ${
                        improvement > 0
                          ? "bg-emerald-100 text-emerald-700"
                          : improvement < 0
                          ? "bg-red-100 text-red-700"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {improvement > 0 ? `+${improvement.toFixed(2)}%` : `${improvement.toFixed(2)}%`}
                    </span>
                  </div>

                  <div className="mt-6 h-[280px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={[
                          {
                            name: "Version 1",
                            score: Number(previousScore),
                            fill: "#94a3b8",
                          },
                          {
                            name: "Version 2",
                            score: Number(latestScore),
                            fill: improvement > 0 ? "#10b981" : improvement < 0 ? "#ef4444" : "#3b82f6",
                          },
                        ]}
                        margin={{ top: 20, right: 30, left: 0, bottom: 20 }}
                      >
                        <CartesianGrid strokeDasharray="2 2" stroke="#e2e8f0" />
                        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#f8fafc",
                            border: "1px solid #cbd5e1",
                            borderRadius: "8px",
                            padding: "8px 12px",
                          }}
                          labelStyle={{ color: "#0f172a", fontSize: 12, fontWeight: "600" }}
                          formatter={(value) => `${value.toFixed(2)}`}
                        />
                        <Bar dataKey="score" radius={[8, 8, 0, 0]}>
                          <Cell fill="#94a3b8" />
                          <Cell fill={improvement > 0 ? "#10b981" : improvement < 0 ? "#ef4444" : "#3b82f6"} />
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="mt-5 grid grid-cols-2 gap-4">
                    <div className="rounded-lg bg-slate-50 p-3 text-center">
                      <p className="text-xs font-semibold text-slate-600">Version 1</p>
                      <p className="mt-1 text-lg font-bold text-slate-900">{previousScore}</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3 text-center">
                      <p className="text-xs font-semibold text-slate-600">Version 2</p>
                      <p className="mt-1 text-lg font-bold text-slate-900">{latestScore}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Charts Side by Side */}
              <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
                {/* Section Score Chart */}
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">Section Scores</h4>
                  <div className="mt-3 h-[300px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={sectionChartData} margin={{ top: 5, right: 5, left: -20, bottom: 50 }}>
                        <CartesianGrid strokeDasharray="2 2" stroke="#e2e8f0" />
                        <XAxis
                          dataKey="name"
                          angle={-25}
                          textAnchor="end"
                          height={80}
                          interval={0}
                          tick={{ fontSize: 11 }}
                        />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#f8fafc",
                            border: "1px solid #cbd5e1",
                            borderRadius: "8px",
                          }}
                          labelStyle={{ color: "#0f172a", fontSize: 12 }}
                        />
                        <Legend />
                        <Bar dataKey="raw" fill="#3b82f6" name="Raw" radius={[6, 6, 0, 0]} />
                        <Bar dataKey="weighted" fill="#10b981" name="Weighted" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Score Comparison Chart */}
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">Score Comparison</h4>
                  <div className="mt-3 h-[300px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={scoreComparisonData} margin={{ top: 5, right: 5, left: -20, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="2 2" stroke="#e2e8f0" />
                        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#f8fafc",
                            border: "1px solid #cbd5e1",
                            borderRadius: "8px",
                          }}
                          labelStyle={{ color: "#0f172a", fontSize: 12 }}
                        />
                        <Bar dataKey="score" fill="#2563eb" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Section-wise Evaluation */}
              {sectionScores.length > 0 && (
                <div className="mb-6">
                  <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-700">
                    Section-wise Evaluation
                  </h3>
                  <div className="space-y-3">
                    {sectionScores.map((item, idx) => (
                      <div
                        key={`${item?.criterion || "section"}-${idx}`}
                        className="rounded-lg bg-slate-50 p-4 ring-1 ring-slate-200 hover:ring-slate-300 transition"
                      >
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <p className="text-xs font-bold text-slate-800">{item?.criterion || "N/A"}</p>
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${getBadgeStyle(
                              item?.compliance_level || "-"
                            )}`}
                          >
                            {item?.compliance_level || "-"}
                          </span>
                        </div>
                        <p className="text-xs text-slate-600">
                          Sim: {Number(item?.similarity_score ?? 0).toFixed(3)} | Raw: {Number(item?.raw_score ?? 0).toFixed(1)} | Weighted: {Number(item?.weighted_score ?? 0).toFixed(1)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Weakness Analysis & Next Steps */}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                {/* Weakness Analysis */}
                <div>
                  <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-700">
                    Weakness Analysis
                  </h3>
                  {weaknesses.length ? (
                    <div className="space-y-2">
                      {weaknesses.slice(0, 5).map((item, idx) => {
                        const priority = normalizePriority(item);
                        return (
                          <div key={`${item?.criterion || "weak"}-${idx}`} className="rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200">
                            <div className="flex items-start justify-between gap-2 mb-1">
                              <p className="text-xs font-semibold text-slate-800">
                                {item?.criterion || "Unknown"}
                              </p>
                              <span
                                className={`text-[10px] font-bold px-1 py-0.5 rounded whitespace-nowrap ${getBadgeStyle(
                                  priority
                                )}`}
                              >
                                {priority.split(" ")[0]}
                              </span>
                            </div>
                            <p className="text-xs text-slate-600">
                              {item?.issue || "Weak alignment detected."}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">No weaknesses detected.</p>
                  )}
                </div>

                {/* Recommended Next Steps */}
                <div>
                  <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-700">
                    Recommended Next Steps
                  </h3>
                  <div className="space-y-2">
                    {nextSteps.map((step, idx) => (
                      <div
                        key={`${step?.week || "step"}-${idx}`}
                        className="rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200"
                      >
                        <p className="text-xs font-bold text-slate-800">{step?.week || `Step ${idx + 1}`}</p>
                        <p className="mt-1 text-xs text-slate-600">{step?.action || "Continue improvement."}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Compliance Snapshot */}
            <div className="rounded-3xl bg-white p-6 shadow-md ring-1 ring-slate-200 md:p-7 lg:p-8">
              <h2 className="text-lg font-semibold md:text-xl">Compliance Snapshot</h2>
              <p className="mt-1 text-xs leading-relaxed text-slate-600 sm:text-sm">
                Rubric compliance distribution across criteria
              </p>

              <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={complianceChartData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={90}
                        label={{ fontSize: 12 }}
                      >
                        {complianceChartData.map((entry) => (
                          <Cell key={entry.name} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                <div className="space-y-3">
                  <div className="rounded-lg bg-slate-50 p-4 ring-1 ring-slate-200">
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-600">Research Readiness</p>
                    <p className="mt-2 text-lg font-bold text-slate-900">{overall.status}</p>
                    <p className="mt-1 text-xs text-slate-600">
                      Status based on rubric compliance and scoring.
                    </p>
                  </div>

                  <div className="rounded-lg bg-slate-50 p-4 ring-1 ring-slate-200">
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-600">Compliance Summary</p>
                    <div className="mt-2 space-y-1.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-600">Good/Strong:</span>
                        <span className="font-bold text-emerald-700">{complianceStats.good}</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-600">Adequate:</span>
                        <span className="font-bold text-blue-700">{complianceStats.adequate}</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-600">Poor/Missing:</span>
                        <span className="font-bold text-amber-700">{complianceStats.poor}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Adaptive Recommendations */}
              {Object.keys(recommendations).length > 0 && (
                <div className="mt-6">
                  <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-700">
                    Adaptive Learning Pathway
                  </h3>
                  <div className="space-y-3">
                    {Object.entries(recommendations)
                      .slice(0, 3)
                      .map(([criterion, resources]) => {
                        const isGroupedResources =
                          resources && typeof resources === "object" && !Array.isArray(resources);

                        const categories = [
                          ["guides", "Guides"],
                          ["videos", "Videos"],
                          ["articles", "Articles"],
                        ];

                        return (
                          <div
                            key={criterion}
                            className="rounded-lg bg-slate-50 p-4 ring-1 ring-slate-200"
                          >
                            <h4 className="text-xs font-bold text-slate-800">{criterion}</h4>

                            {isGroupedResources ? (
                              <div className="mt-2 space-y-1.5">
                                {categories.map(([key, label]) => {
                                  const items = Array.isArray(resources[key])
                                    ? resources[key]
                                    : [];
                                  if (!items.length) return null;

                                  return (
                                    <div key={key}>
                                      <p className="text-[10px] font-bold uppercase text-slate-500">
                                        {label}
                                      </p>
                                      <ul className="mt-1 space-y-1">
                                        {items
                                          .slice(0, 2)
                                          .map((resource, idx) =>
                                            renderResourceItem(
                                              resource,
                                              `${criterion}-${key}-${idx}`
                                            )
                                          )}
                                      </ul>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : Array.isArray(resources) ? (
                              <ul className="mt-2 space-y-1">
                                {resources.slice(0, 2).map((resource, idx) =>
                                  renderResourceItem(resource, `${criterion}-${idx}`)
                                )}
                              </ul>
                            ) : (
                              <p className="mt-1 text-xs text-slate-500">No resources.</p>
                            )}
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}
            </div>

            {/* Mentorship Insight */}
            <div className="rounded-3xl bg-white p-6 shadow-md ring-1 ring-slate-200 md:p-7 lg:p-8">
              <h2 className="text-lg font-semibold md:text-xl">Mentorship Insight</h2>
              <p className="mt-1 text-xs leading-relaxed text-slate-600 sm:text-sm">
                Personalized academic feedback narrative
              </p>
              <div className="mt-5 max-h-[300px] overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-xs leading-relaxed text-slate-700 sm:text-sm ring-1 ring-slate-200">
                {apiData?.text || "Analyze a report to view personalized feedback here."}
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
