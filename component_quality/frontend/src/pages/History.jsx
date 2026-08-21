import { useMemo, useState } from "react";
import { FileText, Trash2 } from "lucide-react";
import EmptyState from "../components/EmptyState";
import FeedbackCard from "../components/FeedbackCard";
import HistoryTable from "../components/HistoryTable";
import Loader from "../components/Loader";
import Modal from "../components/Modal";
import RecommendationCard from "../components/RecommendationCard";
import { clearAnalysisHistory, deleteAnalysisHistoryRecord } from "../api";

function GraphSummary({ record, graphHistory }) {
  const match = findGraphForRecord(record, graphHistory);
  if (!match) return <p className="muted">Knowledge graph summary is not saved for this history record.</p>;
  return (
    <div className="result-summary">
      <article><span>Concepts</span><strong>{match.concepts?.length || 0}</strong></article>
      <article><span>Relationships</span><strong>{match.edges?.length || 0}</strong></article>
      <article><span>Missing Concepts</span><strong>{match.missing_concepts?.length || 0}</strong></article>
    </div>
  );
}

function findGraphForRecord(record, graphHistory = []) {
  if (record?.analysis_id) {
    return graphHistory.find((item) => item.analysis_id === record.analysis_id) || null;
  }
  // Legacy fallback for records saved before graph history carried analysis_id.
  const filenameMatch = graphHistory.find((item) => item.filename && record.filename && item.filename === record.filename);
  if (filenameMatch) return filenameMatch;
  const recordTime = new Date(record.timestamp || 0).getTime();
  if (!recordTime) return null;
  return graphHistory.find((item) => {
    const graphTime = new Date(item.timestamp || 0).getTime();
    return graphTime >= recordTime && graphTime - recordTime <= 5 * 60 * 1000;
  }) || null;
}

export default function History({ history, graphHistory, loadingData, refreshData, notify }) {
  const [selected, setSelected] = useState(null);
  const [clearing, setClearing] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const records = useMemo(() => history || [], [history]);

  function getGraphForRecord(record) {
    return findGraphForRecord(record, graphHistory || []) || {};
  }

  function closeSelected() {
    setSelected(null);
  }

  async function clearAll() {
    if (!window.confirm("Clear all proposal analysis history?")) return;
    setClearing(true);
    try {
      await clearAnalysisHistory();
      setSelected(null);
      await refreshData();
    } finally {
      setClearing(false);
    }
  }

  async function deleteOne(record) {
    if (!record?.id) return;
    const label = record.filename || record.proposal_title || record.input_preview || record.id;
    if (!window.confirm(`Delete this proposal analysis record?\n\n${label}`)) return;
    setDeletingId(record.id);
    try {
      await deleteAnalysisHistoryRecord(record.id);
      if (selected?.id === record.id) {
        setSelected(null);
      }
      await refreshData();
      notify?.("Analysis history record deleted.", "success");
    } catch (error) {
      console.error("Could not delete analysis history record.", error);
      notify?.(error.message || "Could not delete this analysis history record.", "error");
    } finally {
      setDeletingId("");
    }
  }

  return (
    <section className="page-stack">
      <div className="page-title">
        <div>
          <span className="eyebrow">History</span>
          <h2>Proposal Analysis History</h2>
          <p>Saved records from the real /analysis-history endpoint.</p>
        </div>
        <button className="danger-button" type="button" onClick={clearAll} disabled={!records.length || clearing}>
          <Trash2 size={16} />
          Clear Proposal History
        </button>
      </div>

      {loadingData ? (
        <Loader />
      ) : records.length ? (
        <HistoryTable records={records} onView={setSelected} onDelete={deleteOne} deletingId={deletingId} />
      ) : (
        <EmptyState
          icon={FileText}
          title="No proposals analysed yet."
          message="Upload or paste a proposal to start building your analysis history."
          actionLabel="Go to Analyzer"
          actionTo="/analyzer"
        />
      )}

      <Modal title="Saved proposal analysis" eyebrow="History record" onClose={closeSelected}>
        {selected && (
          <div className="modal-stack">
            <div className="result-summary">
              <article><span>Timestamp</span><strong>{selected.timestamp || "-"}</strong></article>
              <article><span>Student</span><strong>{selected.student_name || "Not provided"}</strong></article>
              <article><span>Student ID</span><strong>{selected.student_id || "Not provided"}</strong></article>
              <article><span>Filename</span><strong>{selected.filename || "-"}</strong></article>
              <article><span>Weakness Category</span><strong>{selected.predicted_tag || "-"}</strong></article>
            </div>
            <article className="detail-card">
              <h3>Preview</h3>
              <p>{selected.input_preview || "No preview saved."}</p>
            </article>
            <article className="detail-card">
              <h3>Full feedback</h3>
              <div className="feedback-grid">
                {(selected.retrieved_feedback || []).map((item, index) => (
                  <FeedbackCard key={`${index}-${item.comment_text}`} item={item} index={index} />
                ))}
              </div>
              {!(selected.retrieved_feedback || []).length && <p className="muted">No feedback saved for this record.</p>}
            </article>
            <article className="detail-card">
              <h3>Resources</h3>
              <div className="recommendation-grid">
                {(selected.recommended_resources || []).map((resource, index) => (
                  <RecommendationCard key={`${index}-${resource.title}`} resource={resource} />
                ))}
              </div>
              {!(selected.recommended_resources || []).length && <p className="muted">No resources saved for this record.</p>}
            </article>
            <article className="detail-card">
              <h3>Knowledge Graph Summary</h3>
              <GraphSummary record={selected} graphHistory={graphHistory || []} />
            </article>
          </div>
        )}
      </Modal>
    </section>
  );
}
