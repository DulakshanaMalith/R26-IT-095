import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronRight, Download, FilePlus2, FileSpreadsheet, FolderGit2,
  LoaderCircle, TriangleAlert, Upload, Users
} from "lucide-react";
import { Link } from "react-router-dom";
import Loader from "../components/Loader";
import { createProject, getProjects, TEMPLATE_URL, uploadTeams } from "../api";

function riskTone(status) {
  if (status === "High Risk") return "danger";
  if (status === "Medium Risk") return "warning";
  if (status === "Low Risk") return "success";
  return "";
}

const EMPTY_FORM = { name: "", team_id: "", github_url: "", jira_project_key: "" };

export default function Projects({ user }) {
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState("");

  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createdMessage, setCreatedMessage] = useState("");

  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [report, setReport] = useState(null);

  const isSupervisor = user.role === "supervisor";

  const loadProjects = useCallback(() => {
    getProjects()
      .then((data) => setProjects(data.projects))
      .catch((loadError) => setError(loadError.message));
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const setField = (field) => (event) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  async function submitCreate(event) {
    event.preventDefault();
    setCreating(true);
    setCreateError("");
    setCreatedMessage("");
    try {
      const data = await createProject(form);
      setForm(EMPTY_FORM);
      setCreatedMessage(`Project "${data.project.name}" created.`);
      loadProjects();
    } catch (submitError) {
      setCreateError(submitError.message);
    } finally {
      setCreating(false);
    }
  }

  async function submitUpload(event) {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setUploadError("Choose a .xlsx file first.");
      return;
    }
    setUploading(true);
    setUploadError("");
    setReport(null);
    try {
      const data = await uploadTeams(file);
      setReport(data);
      if (fileRef.current) fileRef.current.value = "";
      loadProjects();
    } catch (submitError) {
      setUploadError(submitError.message);
    } finally {
      setUploading(false);
    }
  }

  if (error) {
    return (
      <main className="page">
        <div className="error-card">
          <TriangleAlert size={18} />
          <span>{error}</span>
        </div>
      </main>
    );
  }

  if (!projects) {
    return (
      <main className="page">
        <Loader label="Loading projects..." />
      </main>
    );
  }

  return (
    <main className="page">
      {projects.length === 0 ? (
        <section className="card empty-card">
          <FolderGit2 size={34} />
          <h2>No projects yet</h2>
          <p>
            {isSupervisor
              ? "Create your first project below, or upload an Excel team file to create many at once."
              : "You have not been added to a project team yet. Ask your supervisor to add you."}
          </p>
        </section>
      ) : (
        <div className="project-grid">
          {projects.map((project) => (
            <Link key={project.id} to={`/projects/${project.id}`} className="card project-card">
              <div className="project-card-head">
                <div>
                  <strong>{project.name}</strong>
                  <span className="muted">Team {project.team_id}</span>
                </div>
                {project.last_risk_status && (
                  <span className={`risk-pill ${riskTone(project.last_risk_status)}`}>
                    {project.last_risk_status}
                  </span>
                )}
              </div>
              <div className="project-card-meta">
                <span className="muted">
                  <Users size={14} /> {project.member_count ?? 0} member(s)
                </span>
                {project.jira_project_key && (
                  <span className="muted">Jira: {project.jira_project_key}</span>
                )}
              </div>
              <span className="muted repo-line">{project.github_url || "No repository set"}</span>
              <span className="open-link">
                View analytics <ChevronRight size={15} />
              </span>
            </Link>
          ))}
        </div>
      )}

      {isSupervisor && (
        <div className="chart-row">
          <section className="card">
            <h3><FilePlus2 size={16} /> Create a Project</h3>
            {createError && (
              <div className="error-card"><TriangleAlert size={16} /><span>{createError}</span></div>
            )}
            {createdMessage && <div className="alert-item ok"><span className="alert-dot" />{createdMessage}</div>}
            <form className="login-form panel-form" onSubmit={submitCreate}>
              <div className="form-grid">
                <label>
                  Project Name
                  <input type="text" value={form.name} onChange={setField("name")} required />
                </label>
                <label>
                  Team ID
                  <input type="text" value={form.team_id} onChange={setField("team_id")}
                    placeholder="TEAM-101" required />
                </label>
                <label>
                  GitHub Repository URL
                  <input type="url" value={form.github_url} onChange={setField("github_url")}
                    placeholder="https://github.com/user/repo" />
                </label>
                <label>
                  Jira Project Key (optional)
                  <input type="text" value={form.jira_project_key}
                    onChange={setField("jira_project_key")} placeholder="IPMS" />
                </label>
              </div>
              <button className="primary-button" type="submit" disabled={creating}>
                {creating ? <LoaderCircle className="spin" size={15} /> : <FilePlus2 size={15} />}
                Create Project
              </button>
            </form>
          </section>

          <section className="card">
            <h3><FileSpreadsheet size={16} /> Bulk Upload Teams (Excel)</h3>
            <p className="muted upload-note">
              One row per member: Project ID, Project Name, Team Leader, Member Name, IT Number,
              IT Email, GitHub Username, Repo URL, Jira Key. Student accounts are created
              automatically — first password is the IT number.
            </p>
            {uploadError && (
              <div className="error-card"><TriangleAlert size={16} /><span>{uploadError}</span></div>
            )}
            <form className="login-form panel-form" onSubmit={submitUpload}>
              <label>
                Excel File (.xlsx)
                <input ref={fileRef} type="file" accept=".xlsx" required />
              </label>
              <div className="button-row">
                <button className="primary-button" type="submit" disabled={uploading}>
                  {uploading ? <LoaderCircle className="spin" size={15} /> : <Upload size={15} />}
                  Upload &amp; Create Teams
                </button>
                <a className="ghost-link" href={TEMPLATE_URL}>
                  <Download size={14} /> Download Template
                </a>
              </div>
            </form>

            {report && (
              <div className="upload-report">
                <div className="chart-legend">
                  <span className="legend-item">Created <strong>{report.projects_created}</strong></span>
                  <span className="legend-item">Updated <strong>{report.projects_updated}</strong></span>
                  <span className="legend-item">Members <strong>{report.members_added}</strong></span>
                  <span className="legend-item">Accounts <strong>{report.accounts_created}</strong></span>
                </div>
                {report.errors.map((message, index) => (
                  <div key={index} className="warning-item">
                    <TriangleAlert size={14} />{message}
                  </div>
                ))}
                {report.entries.map((entry) => (
                  <div key={entry.team_id} className="report-entry">
                    <strong>{entry.name} ({entry.team_id}) — {entry.status}</strong>
                    <span className="muted">
                      {entry.members_added} member(s) linked
                      {entry.accounts_created.length > 0 &&
                        ` · new accounts: ${entry.accounts_created.join(", ")}`}
                    </span>
                    {entry.problems.map((problem, index) => (
                      <span key={index} className="muted problem-line">⚠ {problem}</span>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
