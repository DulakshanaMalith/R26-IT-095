import { MessageSquareText } from "lucide-react";

export default function FeedbackCard({ item, index }) {
  return (
    <article className="feedback-card">
      <div className="feedback-top">
        <span>{String(index + 1).padStart(2, "0")}</span>
        <div>
          <strong>{item.tag || "Feedback"}</strong>
          <small>Retrieved feedback</small>
        </div>
      </div>
      <p className="matched-text">{item.annotated_text || "No matched annotation returned."}</p>
      <div className="feedback-note">
        <MessageSquareText size={16} />
        <p>{item.comment_text || item.feedback || "No feedback text returned."}</p>
      </div>
    </article>
  );
}
