import { BarChart3 } from "lucide-react";

export default function ChartCard({ title, eyebrow, subtitle, footer, children, wide = false, icon: Icon = BarChart3 }) {
  return (
    <article className={`chart-card ${wide ? "wide" : ""}`}>
      <div className="chart-card-header">
        <div className="card-heading">
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {Icon && (
          <span className="chart-action-icon">
            <Icon size={18} />
          </span>
        )}
      </div>
      <div className="chart-card-body">{children}</div>
      {footer && <p className="chart-card-footer">{footer}</p>}
    </article>
  );
}
