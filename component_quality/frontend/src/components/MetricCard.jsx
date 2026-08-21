export default function MetricCard({ icon: Icon, label, value, detail, compact = false }) {
  const valueText = String(value ?? 0);
  const detailText = detail ? String(detail) : "";

  return (
    <article className={`metric-card ${compact ? "metric-card-compact" : ""}`}>
      {Icon && (
        <span className="metric-icon">
          <Icon size={20} />
        </span>
      )}
      <div className="metric-content">
        <span className="metric-label">{label}</span>
        <strong className="metric-value" title={valueText}>{valueText}</strong>
        {detail && <small className="metric-detail" title={detailText}>{detailText}</small>}
      </div>
    </article>
  );
}
