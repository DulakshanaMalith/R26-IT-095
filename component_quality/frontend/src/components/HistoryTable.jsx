import { Eye, Trash2 } from "lucide-react";
import { truncate } from "../utils";

export default function HistoryTable({ records = [], onView, onDelete, deletingId = "", showActions = true }) {
  return (
    <article className="table-card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Student</th>
              <th>Student ID</th>
              <th>Filename</th>
              <th>Source</th>
              <th>Weakness Category</th>
              <th>Preview</th>
              {showActions && <th>View</th>}
              {showActions && <th>Delete</th>}
            </tr>
          </thead>
          <tbody>
            {records.length ? (
              records.map((record) => (
                <tr key={record.id || `${record.timestamp}-${record.input_preview}`}>
                  <td className="table-date">{record.timestamp || "-"}</td>
                  <td>{record.student_name || "Not provided"}</td>
                  <td>{record.student_id || "Not provided"}</td>
                  <td className="table-filename" title={record.filename || ""}>{record.filename || "-"}</td>
                  <td>{record.source || "unknown"}</td>
                  <td><span className="tag-pill">{record.predicted_tag || "-"}</span></td>
                  <td className="table-preview" title={record.input_preview || ""}>{truncate(record.input_preview, 80)}</td>
                  {showActions && (
                    <td>
                      <button className="icon-button" type="button" onClick={() => onView(record)}>
                        <Eye size={15} />
                      </button>
                    </td>
                  )}
                  {showActions && (
                    <td>
                      <button
                        className="icon-button danger-icon"
                        type="button"
                        onClick={() => onDelete?.(record)}
                        disabled={!record.id || deletingId === record.id}
                        title={record.id ? "Delete this analysis record" : "This legacy record has no analysis ID."}
                      >
                        <Trash2 size={15} />
                      </button>
                    </td>
                  )}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={showActions ? 9 : 7}>No proposal analyses saved yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </article>
  );
}
