export default function VersionComparison({ versionA, versionB }) {
  if (!versionA || !versionB) return null;

  return (
    <article className="comparison-card">
      <div>
        <span>Version A</span>
        <strong>{versionA.filename || versionA.source || "Earlier proposal"}</strong>
        <p>{versionA.filename || versionA.source || "Earlier proposal"}</p>
      </div>
      <div>
        <span>Version B</span>
        <strong>{versionB.filename || versionB.source || "Later proposal"}</strong>
        <p>{versionB.filename || versionB.source || "Later proposal"}</p>
      </div>
    </article>
  );
}
