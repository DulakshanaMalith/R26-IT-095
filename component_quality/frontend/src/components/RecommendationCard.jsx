import { ArrowUpRight, Target } from "lucide-react";

export default function RecommendationCard({ resource }) {
  const resourceUrl = typeof resource.url === "string" ? resource.url.trim() : "";
  const hasUrl = /^https?:\/\//i.test(resourceUrl);
  
  const statusColor = resource.status === 'insufficient' ? '#f59e0b' : resource.status === 'missing' ? '#ef4444' : 'var(--primary)';

  return (
    <article className="recommendation-card" style={{
      display: 'flex', flexDirection: 'column', height: '100%', gap: '12px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="resource-badge" style={{ 
          backgroundColor: statusColor, 
          color: '#fff',
          padding: '4px 10px',
          borderRadius: '12px',
          fontSize: '0.75rem',
          fontWeight: '700',
          letterSpacing: '0.05em',
          textTransform: 'uppercase'
        }}>
          {resource.area || resource.category || "Resource"} {resource.status ? `(${resource.status})` : ""}
        </span>
      </div>
      
      <h3 style={{ margin: '0', fontSize: '1.05rem', fontWeight: '600', color: 'var(--text-main)', lineHeight: '1.4' }}>
        {resource.title || "Untitled resource"}
      </h3>
      
      <p style={{ margin: '0', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: '1.5', flexGrow: 1 }}>
        {resource.description || "No description returned."}
      </p>
      
      {resource.reason && (
        <div style={{ 
          display: 'flex', gap: '8px', alignItems: 'flex-start',
          padding: '10px 12px', backgroundColor: '#f8fafc', 
          borderLeft: `3px solid ${statusColor}`, borderRadius: '4px',
          fontSize: '0.8rem', color: '#334155', margin: '4px 0'
        }}>
          <Target size={14} style={{ marginTop: '2px', color: statusColor, flexShrink: 0 }} />
          <span><strong>Target Need:</strong> {resource.reason}</span>
        </div>
      )}
      
      <div style={{ marginTop: 'auto', paddingTop: '4px' }}>
        {hasUrl ? (
          <a className="resource-button" href={resourceUrl} target="_blank" rel="noopener noreferrer" style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '8px 16px', backgroundColor: 'var(--primary)', color: '#fff',
            textDecoration: 'none', borderRadius: '6px', fontSize: '0.85rem',
            fontWeight: '600', transition: 'background-color 0.2s ease', width: 'fit-content'
          }}>
            Open Resource <ArrowUpRight size={15} />
          </a>
        ) : (
          <span className="muted" style={{ fontSize: '0.85rem' }}>Resource link unavailable</span>
        )}
      </div>
    </article>
  );
}
