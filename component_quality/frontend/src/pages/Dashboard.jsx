import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  ClipboardCheck,
  FileClock,
  FileText,
  LoaderCircle,
  RefreshCw,
  Sparkles,
  UsersRound,
} from "lucide-react";
import EmptyState from "../components/EmptyState";
import MetricCard from "../components/MetricCard";
import { getCurrentSupervisorDashboard } from "../api";

const EMPTY_SUMMARY = {
  assigned_students: 0,
  with_proposals: 0,
  analyzed_current_versions: 0,
  waiting_for_analysis: 0,
  revision_requested: 0,
  reviewed: 0,
  recent_proposals: [],
};

function formatDate(value) {
  if (!value) return "No upload yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

function reviewLabel(value) {
  if (value === "REVISION_REQUESTED" || value === "REQUEST_REVISION") return "Revision requested";
  if (value === "READY_FOR_PANEL") return "Ready for panel";
  if (value === "REVIEWED") return "Reviewed";
  if (value === "SEND_FEEDBACK") return "Feedback sent";
  return "Not reviewed";
}

function statusClass(value) {
  if (value === "Analyzed" || value === "REVIEWED" || value === "READY_FOR_PANEL") return "success";
  if (value === "Waiting for analysis" || value === "REVISION_REQUESTED" || value === "REQUEST_REVISION") return "warning";
  return "neutral";
}

export default function Dashboard({ backendOnline, currentSupervisor, requireAuth = false, notify }) {
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      if (!backendOnline) {
        setLoading(false);
        setError("Backend is unavailable. Start FastAPI to load supervisor dashboard data.");
        return;
      }
      setLoading(true);
      setError("");
      try {
        const payload = await getCurrentSupervisorDashboard();
        if (!cancelled) setSummary({ ...EMPTY_SUMMARY, ...payload });
      } catch (dashboardError) {
        if (!cancelled) {
          const message = requireAuth && dashboardError.message === "Authentication required."
            ? "Your supervisor session has expired. Please sign in again."
            : "Could not load supervisor dashboard data.";
          setError(message);
          notify?.(message, "error");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadDashboard();
    return () => {
      cancelled = true;
    };
  }, [backendOnline, notify]);

  const hasStudents = summary.assigned_students > 0;
  const hasProposals = summary.with_proposals > 0;
  const hasWaitingWork = summary.waiting_for_analysis > 0;
  const recentProposals = summary.recent_proposals || [];

  return (
    <section className="page-stack">
      <div className="dashboard-hero">
        <div>
          <span className="eyebrow">Supervisor Dashboard</span>
          <h2>{currentSupervisor?.name ? `Welcome, ${currentSupervisor.name}` : "Supervisor Workload"}</h2>
          <p>Track assigned students, proposal analysis progress, and human review attention from one supervisor-scoped view.</p>
        </div>
        <Sparkles size={34} />
      </div>

      {loading ? (
        <section className="loader-card">
          <LoaderCircle className="spin" size={18} />
          Loading supervisor dashboard...
        </section>
      ) : error ? (
        <article className="empty-state">
          <h3>{error}</h3>
          <p className="muted">
            {requireAuth
              ? "Dashboard data is loaded from the authenticated supervisor session."
              : "Dashboard data is loaded from the configured local prototype supervisor."}
          </p>
          {requireAuth ? (
            <Link className="primary-button compact-button" to="/login">Return to Login</Link>
          ) : (
            <Link className="primary-button compact-button" to="/students">View My Students</Link>
          )}
        </article>
      ) : (
        <>
          <div className="metric-grid dashboard-metric-grid">
            <MetricCard icon={UsersRound} label="Assigned Students" value={summary.assigned_students} detail="Active students assigned to this supervisor" />
            <MetricCard icon={FileText} label="With Proposals" value={summary.with_proposals} detail="Assigned students with at least one proposal" />
            <MetricCard icon={CheckCircle2} label="Analyzed Current Versions" value={summary.analyzed_current_versions} detail="Current versions with linked analysis" />
            <MetricCard icon={FileClock} label="Waiting For Analysis" value={summary.waiting_for_analysis} detail="Current versions without linked analysis" />
            <MetricCard icon={RefreshCw} label="Revision Requested" value={summary.revision_requested} detail="Latest human review requests revision" />
            <MetricCard icon={ClipboardCheck} label="Reviewed" value={summary.reviewed} detail="Current versions with a supervisor review" />
          </div>

          {!hasStudents && (
            <EmptyState
              icon={UsersRound}
              title="No students are currently assigned."
              message="Use My Students when you are ready to add or assign students."
              actionLabel="View My Students"
              actionTo="/students"
            />
          )}

          {hasStudents && !hasProposals && (
            <EmptyState
              icon={FileText}
              title="No proposals uploaded yet."
              message="Open My Students to select a student and start a proposal record."
              actionLabel="View My Students"
              actionTo="/students"
            />
          )}

          {hasProposals && !hasWaitingWork && (
            <article className="info-strip">No proposals are waiting for analysis.</article>
          )}

          <article className="workspace-panel dashboard-activity-panel">
            <div className="workspace-panel-header">
              <div>
                <span className="eyebrow">Recent Activity</span>
                <strong>Student proposal activity</strong>
              </div>
              <div className="supervisor-action-row compact-actions">
                <Link className="primary-button compact-button" to="/students">View My Students</Link>
                <Link className="secondary-button compact-button" to="/analytics">View Analytics</Link>
              </div>
            </div>

            {recentProposals.length ? (
              <div className="dashboard-activity-list">
                {recentProposals.map((item) => (
                  <Link
                    className="dashboard-activity-item"
                    key={`${item.proposal_id}-${item.current_version_id || "no-version"}`}
                    to={`/students/${item.student_id}/analyze`}
                  >
                    <div className="dashboard-activity-main">
                      <span className="eyebrow">{item.academic_student_id}</span>
                      <strong>{item.student_name}</strong>
                      <p>{item.proposal_title}</p>
                    </div>
                    <div className="dashboard-activity-meta">
                      <span>Version {item.current_version_number || "none"}</span>
                      <span>{formatDate(item.last_upload)}</span>
                    </div>
                    <div className="dashboard-status-row">
                      <span className={`dashboard-status ${statusClass(item.analysis_state)}`}>{item.analysis_state}</span>
                      <span className={`dashboard-status ${statusClass(item.supervisor_review_state)}`}>{reviewLabel(item.supervisor_review_state)}</span>
                    </div>
                    <span className="secondary-button compact-button">Analyze / Review Proposal</span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="muted">No recent proposal activity.</p>
            )}
          </article>
        </>
      )}
    </section>
  );
}
