
import { GitBranch, TriangleAlert } from "lucide-react";

function ChipList({ items, tone = "default", limit = 20 }) {
  const visible = (items || []).slice(0, limit);
  const hidden = Math.max((items || []).length - visible.length, 0);
  if (!visible.length) return <p className="muted">No records returned.</p>;

  return (
    <div className={`chip-list ${tone}`}>
      {visible.map((item) => (
        <span key={item}>{item}</span>
      ))}
      {hidden > 0 && <span>+{hidden} more</span>}
    </div>
  );
}

export default function KnowledgeGraph({ graph, loading, error }) {

  if (loading) {
    return (
      <article className="kg-card">
        <GitBranch size={18} />
        <strong>Building knowledge graph...</strong>
      </article>
    );
  }

  if (error) {
    return (
      <article className="error-card">
        <TriangleAlert size={18} />
        <span>{error}</span>
      </article>
    );
  }

  if (!graph) return null;

  const concepts = graph.concepts || [];
  const edges = graph.edges || [];
  const missing = graph.missing_concepts || [];

  return (
    <section className="knowledge-panel">
      <div className="section-title compact">
        <div>
          <span className="eyebrow">Knowledge Graph</span>
          <h2>Concept Mapping</h2>
        </div>
        <div className="kg-stats">
          <span>{concepts.length} concepts</span>
          <span>{edges.length} relationships</span>
          <span>{missing.length} missing</span>
        </div>
      </div>
      {graph.nlp_warning && (
        <div className="warning-strip">
          <TriangleAlert size={16} />
          <span>{graph.nlp_warning}</span>
        </div>
      )}
      <div className="kg-grid">
        <article>
          <h3>Main Concepts</h3>
          <ChipList items={concepts} />
        </article>
        <article>
          <h3>Missing Concepts</h3>
          <ChipList items={missing} tone="warning" />
        </article>
      </div>
    </section>
  );
}
