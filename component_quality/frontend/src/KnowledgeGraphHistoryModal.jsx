import { X } from "lucide-react";

export default function KnowledgeGraphHistoryModal({
  historyItems,
  loading,
  error,
  onClose,
}) {
  return (
    <div className="kg-modal-backdrop" role="presentation">
      <section className="kg-modal" role="dialog" aria-modal="true" aria-labelledby="kg-history-title">
        <div className="kg-modal-header">
          <div>
            <span className="section-kicker">Knowledge Graph History</span>
            <h2 id="kg-history-title">Previous concept maps</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close concept history">
            <X size={18} />
          </button>
        </div>

        {loading && <p className="empty-copy">Loading concept history...</p>}
        {error && <p className="kg-warning">{error}</p>}

        {!loading && !error && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Filename</th>
                  <th>Concept Count</th>
                  <th>Missing Concept Count</th>
                </tr>
              </thead>
              <tbody>
                {historyItems.length ? (
                  historyItems.map((item, index) => (
                    <tr key={`${item.timestamp}-${index}`}>
                      <td>{item.timestamp}</td>
                      <td>{item.filename || "-"}</td>
                      <td>{item.concept_count ?? 0}</td>
                      <td>{item.missing_concepts?.length ?? 0}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="4">No concept maps generated yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
