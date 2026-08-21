import { GitBranch, SearchCheck, TriangleAlert } from "lucide-react";

export default function KnowledgeGraphSummary({ conceptCount, edgeCount, missingCount }) {
  const items = [
    { label: "Concepts", value: conceptCount, icon: SearchCheck },
    { label: "Relationships", value: edgeCount, icon: GitBranch },
    { label: "Missing", value: missingCount, icon: TriangleAlert },
  ];

  return (
    <div className="kg-summary-grid">
      {items.map(({ label, value, icon: Icon }) => (
        <article className="kg-summary-item" key={label}>
          <span>
            <Icon size={17} />
          </span>
          <div>
            <strong>{value}</strong>
            <small>{label}</small>
          </div>
        </article>
      ))}
    </div>
  );
}
