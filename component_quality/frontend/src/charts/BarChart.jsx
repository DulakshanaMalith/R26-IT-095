import { Bar, BarChart as ReBarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { truncate } from "../utils";

export default function CommonResourcesBarChart({ resources = [] }) {
  const data = resources.slice(0, 5).map((resource) => ({
    name: truncate(resource.title || "Untitled resource", 34),
    fullName: resource.title || "Untitled resource",
    category: resource.category || "Resource",
    count: Number(resource.count) || 0,
  }));

  if (!data.length) {
    return (
      <div className="chart-empty-state">
        <strong>No analytics available yet.</strong>
        <span>Analyze at least one proposal to generate analytics.</span>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={Math.max(260, data.length * 48)}>
      <ReBarChart data={data} layout="vertical" margin={{ top: 12, right: 34, bottom: 8, left: 34 }}>
        <defs>
          <linearGradient id="resourceBarFill" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#4F46E5" stopOpacity={0.94} />
            <stop offset="100%" stopColor="#06B6D4" stopOpacity={0.92} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: "#64748b" }} />
        <YAxis type="category" dataKey="name" width={170} tick={{ fontSize: 12, fill: "#334155" }} />
        <Tooltip formatter={(value, name, item) => [`${value} recommendations`, item.payload.fullName]} labelFormatter={() => "Resource"} />
        <Bar dataKey="count" fill="url(#resourceBarFill)" radius={[0, 10, 10, 0]} isAnimationActive>
          <LabelList dataKey="count" position="right" style={{ fill: "#334155", fontSize: 12, fontWeight: 900 }} />
        </Bar>
      </ReBarChart>
    </ResponsiveContainer>
  );
}
