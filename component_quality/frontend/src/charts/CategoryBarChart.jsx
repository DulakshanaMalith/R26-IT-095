import { Bar, BarChart as ReBarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const CATEGORY_ORDER = ["Weakness", "Strength", "Other", "Highlight"];

export default function CategoryBarChart({ distribution = {} }) {
  const total = Object.values(distribution).reduce((sum, value) => sum + Number(value || 0), 0);
  const orderedNames = [
    ...CATEGORY_ORDER,
    ...Object.keys(distribution),
  ].filter((name, index, all) => all.indexOf(name) === index);
  const data = orderedNames.map((name) => {
    const count = Number(distribution[name] || 0);
    const percentage = total ? Math.round((count / total) * 1000) / 10 : 0;
    return {
      name,
      count,
      label: `${count} (${percentage}%)`,
      percentage,
    };
  }).filter((item) => item.count > 0).sort((a, b) => b.count - a.count);

  if (!total) {
    return (
      <div className="chart-empty-state">
        <strong>No analytics available yet.</strong>
        <span>Analyze at least one proposal to generate analytics.</span>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ReBarChart data={data} layout="vertical" margin={{ top: 12, right: 58, bottom: 8, left: 20 }}>
        <defs>
          <linearGradient id="categoryBarFill" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#10B981" stopOpacity={0.88} />
            <stop offset="100%" stopColor="#4F46E5" stopOpacity={0.88} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: "#64748b" }} />
        <YAxis type="category" dataKey="name" width={92} tick={{ fontSize: 12, fill: "#334155" }} />
        <Tooltip
          formatter={(value, name, item) => [`${value} reviews (${item.payload.percentage}%)`, "Count"]}
          labelFormatter={(label) => `Category: ${label}`}
        />
        <Bar dataKey="count" fill="url(#categoryBarFill)" radius={[0, 10, 10, 0]} isAnimationActive>
          <LabelList dataKey="label" position="right" style={{ fill: "#334155", fontSize: 12, fontWeight: 900 }} />
        </Bar>
      </ReBarChart>
    </ResponsiveContainer>
  );
}
