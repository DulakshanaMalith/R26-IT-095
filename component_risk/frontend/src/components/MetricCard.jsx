export default function MetricCard({ label, value, tone = "" }) {
  return (
    <div className={`metric-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
