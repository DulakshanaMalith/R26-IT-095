import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, GitCompareArrows } from "lucide-react";
import EmptyState from "../components/EmptyState";
import Loader from "../components/Loader";
import MetricCard from "../components/MetricCard";
import { getProposalImprovement, getStudent, getVersionSupervisorReviews } from "../api";
import { bestVersionViewModel, snapshotBadges } from "./proposalImprovementViewModel";

function formatList(items, empty = "None") {
  return items?.length ? items.join(", ") : empty;
}

function supervisorDecisionLabel(decision) {
  if (decision === "REQUEST_REVISION" || decision === "REVISION_REQUESTED") return "Revision Requested";
  if (decision === "READY_FOR_PANEL") return "Ready for Panel";
  if (decision === "REVIEWED") return "Reviewed";
  return "No decision saved";
}

function workflowStatusClass(value) {
  if (value === "Analyzed" || value === "Reviewed" || value === "Ready for Panel") return "success";
  if (value === "Awaiting analysis" || value === "Revision Requested") return "warning";
  return "neutral";
}

export default function ProposalImprovement({ backendOnline, backendChecked, currentSupervisor, notify }) {
  const { studentId, proposalId } = useParams();
  const [student, setStudent] = useState(null);
  const [improvement, setImprovement] = useState(null);
  const [versionReviews, setVersionReviews] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const versions = improvement?.versions || [];
  const comparisons = improvement?.comparisons || [];
  const readyComparisons = comparisons.filter((comparison) => comparison.overall_direction !== "INSUFFICIENT_DATA");
  const bestVersionPanel = bestVersionViewModel(improvement);

  const loadImprovement = useCallback(async ({ silent = false } = {}) => {
    if (!backendOnline || !proposalId) return;
    if (!silent) setLoading(true);
    setError("");
    try {
      const [studentPayload, improvementPayload] = await Promise.all([
        studentId ? getStudent(studentId) : Promise.resolve(null),
        getProposalImprovement(proposalId),
      ]);
      const reviewPairs = await Promise.all(
        (improvementPayload.versions || []).map(async (version) => [
          version.version_id,
          await getVersionSupervisorReviews(version.version_id),
        ]),
      );
      setStudent(studentPayload);
      setImprovement(improvementPayload);
      setVersionReviews(Object.fromEntries(reviewPairs));
    } catch (loadError) {
      const message = loadError.message || "Could not load proposal improvement.";
      setError(message);
      notify?.(message, "error");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [backendOnline, notify, proposalId, studentId]);

  useEffect(() => {
    let cancelled = false;
    if (backendChecked && backendOnline) {
      loadImprovement().then(() => {
        if (cancelled) return;
      });
    }
    return () => {
      cancelled = true;
    };
  }, [backendChecked, backendOnline, loadImprovement]);

  if (loading) return <Loader />;

  return (
    <section className="page-stack">
      <div className="page-title">
        <div>
          <span className="eyebrow">Proposal Improvement</span>
          <h2>{improvement?.proposal_title || "Version comparison"}</h2>
          <p>
            {student
              ? `${student.full_name} | ${student.academic_student_id}`
              : "Proposal-scoped comparison from saved version analyses."}
          </p>
        </div>
        <Link className="secondary-button" to={studentId ? `/students/${studentId}/analyze` : "/students"}>
          <ArrowLeft size={16} />
          Back to Analyzer
        </Link>
      </div>

      {!backendOnline && backendChecked && (
        <article className="error-card">Backend is offline. Start FastAPI with APP_DATABASE_PATH configured.</article>
      )}
      {error && <article className="error-card">{error}</article>}

      {improvement ? (
        <>
          <div className="metric-grid">
            <MetricCard icon={GitCompareArrows} label="Saved Versions" value={versions.length} detail="Proposal-scoped records" />
            <MetricCard icon={GitCompareArrows} label="Analyzed Versions" value={versions.filter((version) => version.analyzed).length} detail="Linked SQLite analyses" />
          </div>

          <article className="workspace-panel best-version-panel">
            <div className="workspace-panel-header">
              <div>
                <span className="eyebrow">Best Available Version</span>
                <strong>{bestVersionPanel.hasBest ? bestVersionPanel.title : "Best Available Version unavailable"}</strong>
                <p>Based on currently saved analysis evidence</p>
              </div>
            </div>
            {bestVersionPanel.hasBest ? (
              <>
                <div className="best-version-grid">
                  <div>
                    <span className="eyebrow">Why this version?</span>
                    <ul className="best-version-reasons">
                      {bestVersionPanel.reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="best-version-latest">
                    <span>Latest Version</span>
                    <strong>{bestVersionPanel.latestLabel}</strong>
                    {bestVersionPanel.latestIsBest ? (
                      <p>Latest version is also the Best Available Version.</p>
                    ) : (
                      <p>Latest version is not automatically treated as best.</p>
                    )}
                    {bestVersionPanel.regressions.map((regression) => (
                      <p className="best-version-regression" key={`${regression.section}-${regression.message}`}>
                        Regression detected: {regression.message}
                      </p>
                    ))}
                  </div>
                </div>
                <div className="supervisor-action-row compact-actions">
                  {bestVersionPanel.showCompareWithLatest && (
                    <a
                      className="secondary-button"
                      href={bestVersionPanel.compareHref}
                      aria-label={`Compare ${bestVersionPanel.best.version_label} with ${bestVersionPanel.latestLabel}`}
                    >
                      Compare {bestVersionPanel.best.version_label} with {bestVersionPanel.latestLabel}
                    </a>
                  )}
                  {!bestVersionPanel.showCompareWithLatest && (
                    <span className="muted">Selection is based on saved analysis evidence.</span>
                  )}
                </div>
              </>
            ) : (
              <p className="muted">{bestVersionPanel.message}</p>
            )}
          </article>

          <article className="workspace-panel">
            <div className="workspace-panel-header">
              <div>
                <span className="eyebrow">Version Snapshots</span>
                <strong>Saved analysis state</strong>
              </div>
            </div>
            <div className="workspace-version-strip">
              {versions.map((version) => (
                <article className="detail-card" id={`version-${version.version_id}`} key={version.version_id}>
                  <div className="version-card-heading">
                    <h3>V{version.version_number}</h3>
                    <div className="version-card-badges">
                      {snapshotBadges(version, improvement).map((badge) => (
                        <span className={`workflow-status ${badge.tone === "best" ? "warning" : "neutral"}`} key={badge.label}>
                          {badge.label}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="result-summary">
                    <article>
                      <span>Analysis</span>
                      <strong className={`workflow-status ${workflowStatusClass(version.analyzed ? "Analyzed" : "Awaiting analysis")}`}>{version.analyzed ? "Analyzed" : "Awaiting analysis"}</strong>
                    </article>
                    <article>
                      <span>Supervisor Decision</span>
                      <strong
                        className={`workflow-status ${workflowStatusClass(supervisorDecisionLabel(
                          (versionReviews[version.version_id] || []).find(
                            (review) => review.supervisor_id === currentSupervisor?.supervisor_id,
                          )?.decision || (versionReviews[version.version_id] || []).at(-1)?.decision,
                        ))}`}
                      >
                        {supervisorDecisionLabel(
                          (versionReviews[version.version_id] || []).find(
                            (review) => review.supervisor_id === currentSupervisor?.supervisor_id,
                          )?.decision || (versionReviews[version.version_id] || []).at(-1)?.decision,
                        )}
                      </strong>
                    </article>
                  </div>
                  <div className="missing-section-list">
                    {version.missing_sections?.length ? (
                      version.missing_sections.map((section) => <span key={section}>Missing: {section}</span>)
                    ) : (
                      <span>{version.grading_history_available ? "No missing sections saved." : "Missing sections unavailable."}</span>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </article>

          {!versions.length && (
            <EmptyState
              icon={GitCompareArrows}
              title="No proposal versions saved yet."
              message="Save a proposal version from the supervisor Analyzer before tracking improvement."
            />
          )}

          {versions.length === 1 && (
            <EmptyState
              icon={GitCompareArrows}
              title="No revised analyzed version is available yet."
              message="A satisfactory V1 does not require comparison. Improvement comparison becomes available after a revised proposal is saved and analyzed."
            />
          )}

          {versions.length > 1 && !readyComparisons.length && (
            <EmptyState
              icon={GitCompareArrows}
              title="Comparison is not ready yet."
              message="At least two adjacent versions need linked grading history before improvement can be compared."
            />
          )}

          {readyComparisons.length > 0 && (
            <article className="workspace-panel">
              <div className="workspace-panel-header">
                <div>
                  <span className="eyebrow">Sequential Comparisons</span>
                  <strong>Revision-by-revision evidence</strong>
                </div>
              </div>
              <div className="workspace-comparison-list">
                {readyComparisons.map((comparison) => (
                  <article
                    className="comparison-card"
                    id={`comparison-${comparison.from_version_id}-${comparison.to_version_id}`}
                    key={`${comparison.from_version_id}-${comparison.to_version_id}`}
                  >
                    <div>
                      <span>{`V${comparison.from_version} -> V${comparison.to_version}`}</span>
                      <strong>{comparison.resolved_missing_sections?.length || 0}</strong>
                      <p>Resolved: {formatList(comparison.resolved_missing_sections)}</p>
                    </div>
                    <div>
                      <span>Newly Missing Sections</span>
                      <strong>{comparison.newly_missing_sections?.length || 0}</strong>
                      <p>{formatList(comparison.newly_missing_sections)}</p>
                    </div>
                    <div>
                      <span>Still Missing</span>
                      <strong>{comparison.still_missing_sections?.length || 0}</strong>
                      <p>{formatList(comparison.still_missing_sections)}</p>
                    </div>
                  </article>
                ))}
              </div>
            </article>
          )}
        </>
      ) : (
        !error && (
          <EmptyState
            icon={GitCompareArrows}
            title="Proposal improvement is unavailable."
            message="Open a saved proposal from My Students to view proposal-scoped improvement."
          />
        )
      )}
    </section>
  );
}
