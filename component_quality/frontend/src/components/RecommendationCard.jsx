import { ArrowUpRight } from "lucide-react";

export default function RecommendationCard({ resource }) {
  const resourceUrl = typeof resource.url === "string" ? resource.url.trim() : "";
  const hasUrl = /^https?:\/\//i.test(resourceUrl);

  return (
    <article className="recommendation-card">
      <span className="resource-badge">{resource.category || "Resource"}</span>
      <h3>{resource.title || "Untitled resource"}</h3>
      <p>{resource.description || "No description returned."}</p>
      {hasUrl ? (
        <a className="resource-button" href={resourceUrl} target="_blank" rel="noopener noreferrer">
          Open Resource <ArrowUpRight size={15} />
        </a>
      ) : (
        <span className="muted">Resource link unavailable</span>
      )}
    </article>
  );
}
