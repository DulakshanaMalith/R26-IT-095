import { AlertCircle, AlertTriangle, CheckCircle, Info, Quote } from "lucide-react";

export default function LLMIssueCard({ issue, index }) {
  const getSeverityIcon = () => {
    switch (issue.severity) {
      case "high":
        return <AlertCircle size={16} className="severity-high" />;
      case "medium":
        return <AlertTriangle size={16} className="severity-medium" />;
      case "low":
        return <Info size={16} className="severity-low" />;
      default:
        return <CheckCircle size={16} className="severity-strength" />;
    }
  };

  return (
    <article className="feedback-card llm-issue-card">
      <div className="feedback-top">
        <span>{String(index + 1).padStart(2, "0")}</span>
        <div>
          <strong>{issue.section || "General"} Issue</strong>
          <small>{issue.type} | Severity: {issue.severity}</small>
        </div>
        <div className="llm-severity-icon">
          {getSeverityIcon()}
        </div>
      </div>

      {issue.evidence_span && (
        <div className="feedback-note llm-evidence-note">
          <Quote size={14} />
          <p>"{issue.evidence_span}"</p>
        </div>
      )}

      <div className="llm-issue-body">
        <p>
          <strong>Reason: </strong>
          {issue.reason}
        </p>
        <p>
          <strong>Recommendation: </strong>
          {issue.recommendation}
        </p>
      </div>

      <div className="llm-issue-footer">
        <small>Criterion: {issue.criterion}</small>
      </div>
    </article>
  );
}
