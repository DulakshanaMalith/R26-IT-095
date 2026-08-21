import { Area, AreaChart as ReAreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function TrackingAreaChart({ data = [], dataKey = "value" }) {
  if (!data.length) return <p className="muted">Analyze at least two proposals to show this trend.</p>;

  return (
    <ResponsiveContainer width="100%" height={240}>
      <ReAreaChart data={data} margin={{ top: 10, right: 16, bottom: 4, left: -18 }}>
        <defs>
          <linearGradient id="trackingFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#0f766e" stopOpacity={0.28} />
            <stop offset="95%" stopColor="#0f766e" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
        <Tooltip />
        <Area type="monotone" dataKey={dataKey} stroke="#0f766e" fill="url(#trackingFill)" strokeWidth={3} />
      </ReAreaChart>
    </ResponsiveContainer>
  );
}
