import {
  Area,
  CartesianGrid,
  LabelList,
  Line,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export default function AnalysesLineChart({
  data = [],
  dataKey = "count",
  xKey = "date",
  yAxisLabel = "",
  valueSuffix = "",
  emptyMessage = "No analytics data available",
  seriesName = "Value",
}) {
  if (!data.length) return <p className="muted">{emptyMessage}</p>;

  const hasSinglePoint = data.length === 1;
  const singleValue = hasSinglePoint ? Number(data[0]?.[dataKey] || 0) : null;
  const singleLabel = hasSinglePoint ? data[0]?.[xKey] : null;
  const formatValue = (value) => `${value}${valueSuffix}`;

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 22, right: 26, bottom: 18, left: 8 }}>
        <defs>
          <linearGradient id={`lineFill-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#06B6D4" stopOpacity={0.26} />
            <stop offset="95%" stopColor="#06B6D4" stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
        <XAxis
          dataKey={xKey}
          tick={{ fontSize: 11 }}
          label={{ value: "Date", position: "insideBottom", offset: -10, fontSize: 11, fill: "#64748b" }}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fontSize: 11 }}
          label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: "insideLeft", fontSize: 11, fill: "#64748b" } : undefined}
        />
        <Tooltip
          cursor={{ stroke: "#cbd5e1", strokeWidth: 1 }}
          formatter={(value) => [formatValue(value), seriesName]}
          labelFormatter={(label) => `Date: ${label}`}
        />
        {hasSinglePoint && <ReferenceLine y={singleValue} stroke="#bae6fd" strokeWidth={2} strokeDasharray="4 4" />}
        {hasSinglePoint && <ReferenceLine x={singleLabel} stroke="#c7d2fe" strokeWidth={2} strokeDasharray="4 4" />}
        <Area
          type="monotone"
          dataKey={dataKey}
          fill={`url(#lineFill-${dataKey})`}
          stroke="none"
          isAnimationActive
        />
        <Line
          type="monotone"
          dataKey={dataKey}
          name={seriesName}
          stroke="#06b6d4"
          strokeWidth={3}
          dot={{ r: 6, fill: "#4f46e5", stroke: "#ffffff", strokeWidth: 2 }}
          activeDot={{ r: 8, fill: "#06b6d4", stroke: "#ffffff", strokeWidth: 2 }}
          isAnimationActive={false}
        >
          <LabelList dataKey={dataKey} position="top" formatter={formatValue} style={{ fill: "#334155", fontSize: 12, fontWeight: 800 }} />
        </Line>
      </ComposedChart>
    </ResponsiveContainer>
  );
}
