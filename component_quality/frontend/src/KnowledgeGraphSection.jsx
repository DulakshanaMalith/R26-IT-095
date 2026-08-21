import { useState } from "react";
import { GitBranch, LoaderCircle, TriangleAlert } from "lucide-react";
import KnowledgeGraphHistoryModal from "./KnowledgeGraphHistoryModal";
import KnowledgeGraphSummary from "./KnowledgeGraphSummary";

function BadgeList({ items, variant = "concept", emptyText, limit = 20, expandLabel = "View all" }) {
  const [expanded, setExpanded] = useState(false);

  if (!items?.length) {
    return <p className="empty-copy">{emptyText}</p>;
  }

  const visibleItems = expanded ? items : items.slice(0, limit);
  const hiddenCount = items.length - visibleItems.length;

  return (
    <>
      <div className={`kg-badge-list ${variant}`}>
        {visibleItems.map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
      {hiddenCount > 0 && (
        <button className="kg-more-button" type="button" onClick={() => setExpanded(true)}>
          {expandLabel} ({hiddenCount} more)
        </button>
      )}
    </>
  );
}

function EdgeList({ edges }) {
  const [expanded, setExpanded] = useState(false);
  const visibleEdges = expanded ? edges : edges.slice(0, 15);
  const hiddenCount = edges.length - visibleEdges.length;

  return (
    <>
      <div className="kg-edge-list">
        {visibleEdges.map((edge, index) => (
          <span key={`${edge.source}-${edge.target}-${index}`}>
            {edge.source} <strong>-&gt;</strong> {edge.target}
          </span>
        ))}
      </div>
      {hiddenCount > 0 && (
        <button className="kg-more-button" type="button" onClick={() => setExpanded(true)}>
          View more ({hiddenCount} more)
        </button>
      )}
    </>
  );
}

export default function KnowledgeGraphSection({
  graph,
  loading,
  error,
  historyItems,
  historyLoading,
  historyError,
  showHistory,
  onOpenHistory,
  onCloseHistory,
}) {
  const concepts = graph?.concepts || [];
  const edges = graph?.edges || [];
  const missingConcepts = graph?.missing_concepts || [];
  const implicitConcepts = graph?.implicit_concepts || [];

  if (!graph && !loading && !error) {
    return (
      <section className="kg-section">
        <article className="kg-empty-card">
          <GitBranch size={22} />
          <div>
            <span className="section-kicker">Knowledge Graph &amp; Concept Mapping</span>
            <h2>Analyze a proposal to generate a Knowledge Graph.</h2>
          </div>
        </article>
      </section>
    );
  }

  return (
    <section className="kg-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">Knowledge Graph &amp; Concept Mapping</span>
          <h2>AI-extracted concepts and detected research gaps.</h2>
        </div>
        <button className="payload-toggle" type="button" onClick={onOpenHistory}>
          View Concept History
        </button>
      </div>

      {loading && (
        <div className="kg-loading-card">
          <LoaderCircle className="spinner" size={18} />
          Building Knowledge Graph...
        </div>
      )}

      {error && (
        <div className="error-banner" role="alert">
          <TriangleAlert size={19} />
          <div>
            <strong>Knowledge graph unavailable</strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      {graph?.nlp_warning && (
        <div className="kg-warning" role="status">
          <TriangleAlert size={17} />
          <span>{graph.nlp_warning}</span>
        </div>
      )}

      {graph && (
        <div className="kg-grid">
          <article className="kg-card">
            <h3>Main Concepts</h3>
            <BadgeList items={concepts} emptyText="No concepts detected." />
          </article>

          <article className="kg-card">
            <h3>Concept Relationships</h3>
            {edges.length ? <EdgeList edges={edges} /> : <p className="empty-copy">No relationships detected.</p>}
          </article>

          <article className="kg-card">
            <h3>Missing Research Concepts</h3>
            <BadgeList items={missingConcepts} variant="warning" emptyText="All major concepts detected." />
          </article>
          
          {implicitConcepts.length > 0 && (
            <article className="kg-card">
              <h3>Could Be Clearer</h3>
              <BadgeList items={implicitConcepts} variant="warning" emptyText="None." />
            </article>
          )}

          <article className="kg-card">
            <h3>Graph Summary</h3>
            <KnowledgeGraphSummary
              conceptCount={concepts.length}
              edgeCount={edges.length}
              missingCount={missingConcepts.length}
            />
          </article>
        </div>
      )}

      {showHistory && (
        <KnowledgeGraphHistoryModal
          historyItems={historyItems}
          loading={historyLoading}
          error={historyError}
          onClose={onCloseHistory}
        />
      )}
    </section>
  );
}
