import { useMemo, useState } from "react";
import { Cell, Pie, PieChart as RePieChart, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = ["#4f46e5", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#64748b"];

export default function WeaknessPieChart({ distribution = {} }) {
  const [hidden, setHidden] = useState([]);
  const rawData = useMemo(
    () =>
      Object.entries(distribution)
        .map(([name, value]) => ({
          name,
          value: Number(value) || 0,
        }))
        .filter((item) => item.value > 0),
    [distribution],
  );
  const visibleData = rawData.filter((item) => !hidden.includes(item.name));
  const total = rawData.reduce((sum, item) => sum + item.value, 0);

  function toggleLegend(name) {
    setHidden((current) => (current.includes(name) ? current.filter((item) => item !== name) : [...current, name]));
  }

  if (!rawData.length) {
    return (
      <div className="chart-empty-state">
        <strong>No analytics available yet.</strong>
        <span>Analyze at least one proposal to generate analytics.</span>
      </div>
    );
  }

  return (
    <div className="donut-chart-wrap">
      <ResponsiveContainer width="100%" height={270}>
        <RePieChart>
          <Pie
            data={visibleData}
            dataKey="value"
            nameKey="name"
            innerRadius={64}
            outerRadius={94}
            paddingAngle={4}
            isAnimationActive
          >
            {visibleData.map((item, index) => (
              <Cell key={item.name} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => {
              const percent = total ? Math.round((Number(value) / total) * 1000) / 10 : 0;
              return [`${value} (${percent}%)`, name];
            }}
          />
        </RePieChart>
      </ResponsiveContainer>
      <div className="donut-center" aria-hidden="true">
        <strong>{total}</strong>
        <span>Total Reviews</span>
      </div>
      <div className="donut-legend" aria-label="Toggle chart categories">
        {rawData.map((item, index) => {
          const percent = total ? Math.round((item.value / total) * 1000) / 10 : 0;
          const isHidden = hidden.includes(item.name);
          return (
            <button
              className={isHidden ? "muted-legend" : ""}
              key={item.name}
              type="button"
              onClick={() => toggleLegend(item.name)}
            >
              <i style={{ background: COLORS[index % COLORS.length] }} />
              <span>{item.name}</span>
              <strong>{percent}%</strong>
            </button>
          );
        })}
      </div>
    </div>
  );
}
