import MetricCard from "./MetricCard";
import { Activity, ArrowUpRight, FileStack, Target } from "lucide-react";

export default function ProgressCards({ metrics }) {
  return (
    <div className="metric-grid">
      <MetricCard icon={FileStack} label="Versions Analysed" value={metrics.versions} />
      <MetricCard icon={ArrowUpRight} label="Overall Change" value={metrics.overallChange} detail="Real feedback/resource count delta" />
      <MetricCard icon={Target} label="Weakest Topic" value={metrics.weakestTopic} />
      <MetricCard icon={Activity} label="Most Improved Topic" value={metrics.mostImprovedTopic} />
    </div>
  );
}
