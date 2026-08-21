import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

export default function EmptyState({ icon: Icon, title, message, actionLabel, actionTo }) {
  return (
    <article className="empty-state polished-empty-state">
      {Icon && (
        <div className="empty-icon">
          <Icon size={24} />
        </div>
      )}
      <h3>{title}</h3>
      <p>{message}</p>
      {actionLabel && actionTo && (
        <Link className="primary-button empty-action" to={actionTo}>
          {actionLabel}
          <ArrowRight size={15} />
        </Link>
      )}
    </article>
  );
}
