import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft, Crown, ExternalLink, LoaderCircle, RefreshCw, TriangleAlert
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis
} from "recharts";
import Loader from "../components/Loader";
import MetricCard from "../components/MetricCard";
import { getAnalytics, getProject } from "../api";

const REFRESH_SECONDS = 60;

function riskTone(status) {
  if (status === "High Risk") return "danger";
  if (status === "Medium Risk") return "warning";
  if (status === "Low Risk") return "success";
  return "";
}

function ScoreRow({ name, value, sub, leader }) {
  const width = Math.max(Math.min(Number(value) || 0, 100), 0);
  return (
    <div className="score-row">
      <div className="score-head">
        <span className="score-name">
          {name}
          {leader && <Crown size={13} className="leader-icon" />}
        </span>
        <span className="score-value">
          {value} {sub && <em>{sub}</em>}
        </span>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

export default function ProjectAnalytics() {
  const { projectId } = useParams();
  const [detail, setDetail] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const timerRef = useRef(null);

  const loadAnalytics = useCallback(async (force) => {
    setRefreshing(true);
    try {
      const data = await getAnalytics(projectId, force);
      if (data.error && !data.risk_status) {
        setError(data.error);
      } else {
        setAnalytics(data);
        setError("");
      }
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setRefreshing(false);
    }
  }, [projectId]);

  useEffect(() => {
    setDetail(null);
    setAnalytics(null);
    setError("");

    getProject(projectId)
      .then(setDetail)
      .catch((loadError) => setError(loadError.message));
    loadAnalytics(false);

    timerRef.current = window.setInterval(() => loadAnalytics(false), REFRESH_SECONDS * 1000);
    return () => window.clearInterval(timerRef.current);
  }, [projectId, loadAnalytics]);

  const commitData = useMemo(() => {
    const weeks = analytics?.github?.weekly_activity || [];
    return weeks.map((week) => ({
      week: new Date(week.week * 1000).toISOString().slice(5, 10),
      commits: week.total
    }));
  }, [analytics]);

  const taskSegments = useMemo(() => {
    const delivery = analytics?.delivery;
    if (!delivery || !delivery.total_tasks) return [];
    return [
      { label: "Done", value: delivery.completed_tasks, color: "#4f46e5" },
      { label: "In Progress", value: delivery.in_progress_tasks, color: "#818cf8" },
      { label: "To Do", value: delivery.todo_tasks, color: "#e2e8f0" }
    ];
  }, [analytics]);

  if (error && !analytics) {
    return (
      <main className="page">
        <Link to="/projects" className="back-link"><ArrowLeft size={15} /> Back to projects</Link>
        <div className="error-card"><TriangleAlert size={18} /><span>{error}</span></div>
      </main>
    );
  }

  if (!analytics) {
    return (
      <main className="page">
        <Loader label="Fetching live GitHub and Jira data (10-20 s)..." />
      </main>
    );
  }

  const { delivery, github, team, members = [], jira_members: jiraMembers = [], alerts = [], warnings = [] } = analytics;
  const project = detail?.project;
  const leaders = new Set(
    (detail?.members || []).filter((m) => m.is_leader).map((m) => m.github_login)
  );

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <Link to="/projects" className="back-link"><ArrowLeft size={15} /> Back to projects</Link>
          <h2>{project ? project.name : analytics.repo}</h2>
          <div className="head-meta">
            {project && <span className="muted">Team {project.team_id}</span>}
            {detail?.supervisor && <span className="muted">Supervisor: {detail.supervisor}</span>}
            {analytics.repo && (
              <a href={`https://github.com/${analytics.repo}`} target="_blank" rel="noreferrer" className="muted repo-anchor">
                {analytics.repo} <ExternalLink size={12} />
              </a>
            )}
          </div>
        </div>
        <div className="head-actions">
          <span className="muted">
            Updated {analytics.generated_at} {analytics.cached ? "(cached)" : "(live)"} · auto-refresh {REFRESH_SECONDS}s
          </span>
          <button type="button" className="primary-button" onClick={() => loadAnalytics(true)} disabled={refreshing}>
            {refreshing ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}
            Refresh Now
          </button>
        </div>
      </div>

      {analytics.risk_status && (
        <div className={`risk-banner ${riskTone(analytics.risk_status)}`}>
          <strong>{analytics.risk_status}</strong>
          <span>ML prediction from live GitHub activity, Jira delivery data and team contribution scores.</span>
        </div>
      )}

      {alerts.length > 0 && (
        <div className="alert-stack">
          {alerts.map((alert, index) => (
            <div key={index} className={`alert-item ${alert.level}`}>
              <span className="alert-dot" />
              {alert.message}
            </div>
          ))}
        </div>
      )}

      <div className="metric-grid">
        <MetricCard label="Progress" value={`${delivery.progress_percentage}%`} />
        <MetricCard label="Task Completion" value={`${delivery.task_completion_rate}%`} />
        <MetricCard label="Overdue Tasks" value={delivery.overdue_tasks} tone={delivery.overdue_tasks > 0 ? "warn" : ""} />
        <MetricCard label="Delays" value={delivery.delay_count} tone={delivery.delay_count > 0 ? "warn" : ""} />
        <MetricCard label="Weekly Commits" value={github.weekly_commits} />
        <MetricCard label="Inactive Days" value={github.inactive_days} tone={github.inactive_days > 14 ? "warn" : ""} />
        <MetricCard label="Team Avg CI" value={team.average_ci} />
        <MetricCard label="Contributors" value={team.member_count} />
      </div>

      <div className="chart-row">
        <section className="card">
          <h3>Task Status <span className="muted">Jira</span></h3>
          {taskSegments.length === 0 ? (
            <p className="muted">No Jira task data available.</p>
          ) : (
            <>
              <div className="stack-bar">
                {taskSegments.filter((s) => s.value > 0).map((segment) => (
                  <div
                    key={segment.label}
                    className="stack-seg"
                    title={`${segment.label}: ${segment.value}`}
                    style={{
                      width: `${(segment.value / delivery.total_tasks) * 100}%`,
                      background: segment.color
                    }}
                  />
                ))}
              </div>
              <div className="chart-legend">
                {taskSegments.map((segment) => (
                  <span key={segment.label} className="legend-item">
                    <span className="legend-swatch" style={{ background: segment.color }} />
                    {segment.label} <strong>{segment.value}</strong>
                  </span>
                ))}
              </div>
            </>
          )}
        </section>

        <section className="card">
          <h3>Commit Activity <span className="muted">last 52 weeks</span></h3>
          {commitData.length === 0 ? (
            <p className="muted">GitHub is still preparing commit statistics — refresh in a moment.</p>
          ) : (
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={commitData} margin={{ top: 6, right: 4, bottom: 0, left: -22 }}>
                <CartesianGrid vertical={false} stroke="#eef2f7" />
                <XAxis dataKey="week" tick={{ fontSize: 10, fill: "#64748b" }} interval={12} tickLine={false} axisLine={{ stroke: "#e2e8f0" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: "rgba(79, 70, 229, 0.06)" }} />
                <Bar dataKey="commits" fill="#4f46e5" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </section>
      </div>

      <div className="chart-row">
        <section className="card">
          <h3>Top Contributors <span className="muted">Contribution Index</span></h3>
          {members.length === 0 ? (
            <p className="muted">No contributor data available.</p>
          ) : (
            members.slice(0, 8).map((member) => (
              <ScoreRow
                key={member.login}
                name={member.login}
                value={member.ci}
                sub={`${member.share}% share`}
                leader={leaders.has(member.login)}
              />
            ))
          )}
        </section>

        <section className="card">
          <h3>Task Contribution <span className="muted">Jira assignees</span></h3>
          {jiraMembers.length === 0 ? (
            <p className="muted">No Jira task data available.</p>
          ) : (
            jiraMembers.slice(0, 8).map((member) => (
              <ScoreRow
                key={member.name}
                name={member.name}
                value={member.task_score}
                sub={`${member.stats.completed}/${member.stats.assigned} done · ${member.on_time_rate}% on time`}
              />
            ))
          )}
        </section>
      </div>

      {detail?.members?.length > 0 && (
        <section className="card">
          <h3>Team Members <span className="muted">registered in IPMS</span></h3>
          <div className="member-grid">
            {detail.members.map((member) => (
              <div key={member.id} className="member-chip">
                <strong>
                  {member.full_name}
                  {member.is_leader && <span className="risk-pill success">Leader</span>}
                </strong>
                <span className="muted">{member.email}</span>
                <span className="muted">
                  {member.it_number || "—"} · GitHub: {member.github_login || "—"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {warnings.length > 0 && (
        <div className="warning-stack">
          {warnings.map((warning, index) => (
            <div key={index} className="warning-item">
              <TriangleAlert size={15} />
              {warning}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
