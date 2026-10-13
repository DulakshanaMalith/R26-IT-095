import { useMemo, useState } from "react";
import { GitCompareArrows, History } from "lucide-react";
import EmptyState from "../components/EmptyState";
import Loader from "../components/Loader";
import MetricCard from "../components/MetricCard";

function getRecordId(record) {
  return record.analysis_id || record.id || record.timestamp;
}

function missingSections(record) {
  return record.proposal_completeness?.missing_sections || record.missing_sections || [];
}

function formatList(items, empty = "None") {
  return items?.length ? items.join(", ") : empty;
}

function compareMissingSections(before, after) {
  const beforeSet = new Set(missingSections(before));
  const afterSet = new Set(missingSections(after));
  return {
    resolved: [...beforeSet].filter((section) => !afterSet.has(section)),
    newlyMissing: [...afterSet].filter((section) => !beforeSet.has(section)),
    stillMissing: [...afterSet].filter((section) => beforeSet.has(section)),
  };
}

export default function ImprovementTracking({ gradingHistory, loadingData }) {
  const [beforeId, setBeforeId] = useState("");
  const [afterId, setAfterId] = useState("");
  const [comparison, setComparison] = useState(null);

  const versions = useMemo(
    () =>
      [...(gradingHistory || [])]
        .sort((a, b) => new Date(a.timestamp || 0) - new Date(b.timestamp || 0))
        .map((record, index) => ({
          ...record,
          versionLabel: `Version ${index + 1}`,
        })),
    [gradingHistory],
  );

  const firstVersion = versions[0];
  const latestVersion = versions[versions.length - 1];
  const selectedBefore = versions.find((record) => getRecordId(record) === beforeId) || firstVersion;
  const selectedAfter = versions.find((record) => getRecordId(record) === afterId) || latestVersion;

  if (loadingData) {
    return <Loader />;
  }

  if (versions.length < 2) {
    return (
      <section className="page-stack">
        <div className="page-title">
          <div>
            <span className="eyebrow">Improvement Tracking</span>
            <h2>Version comparison</h2>
          </div>
        </div>
        <EmptyState
          icon={GitCompareArrows}
          title="Track improvement after at least two analyzed proposal versions."
          message="Version comparison focuses on missing sections and saved proposal evidence."
          actionLabel="Go to Analyzer"
          actionTo="/analyzer"
        />
      </section>
    );
  }

  function compareSelected() {
    setComparison({
      before: selectedBefore,
      after: selectedAfter,
      ...compareMissingSections(selectedBefore, selectedAfter),
    });
  }

  return (
    <section className="page-stack">
      <div className="page-title">
        <div>
          <span className="eyebrow">Improvement Tracking</span>
          <h2>Version comparison</h2>
          <p>Compare saved proposal versions by section coverage and revision evidence.</p>
        </div>
      </div>

      <div className="metric-grid">
        <MetricCard icon={History} label="Versions Analysed" value={versions.length} />
        <MetricCard icon={GitCompareArrows} label="Latest Missing Sections" value={missingSections(latestVersion).length} detail={formatList(missingSections(latestVersion))} />
      </div>

      <article className="selector-card">
        <label>
          Before version
          <select value={getRecordId(selectedBefore)} onChange={(event) => setBeforeId(event.target.value)}>
            {versions.map((record) => (
              <option key={getRecordId(record)} value={getRecordId(record)}>
                {record.versionLabel}
              </option>
            ))}
          </select>
        </label>
        <label>
          After version
          <select value={getRecordId(selectedAfter)} onChange={(event) => setAfterId(event.target.value)}>
            {versions.map((record) => (
              <option key={getRecordId(record)} value={getRecordId(record)}>
                {record.versionLabel}
              </option>
            ))}
          </select>
        </label>
        <button className="primary-button" type="button" onClick={compareSelected}>
          Compare Selected
        </button>
      </article>

      {comparison && (
        <article className="comparison-card">
          <div>
            <span>Resolved Sections</span>
            <strong>{comparison.resolved.length}</strong>
            <p>{formatList(comparison.resolved)}</p>
          </div>
          <div>
            <span>Newly Missing Sections</span>
            <strong>{comparison.newlyMissing.length}</strong>
            <p>{formatList(comparison.newlyMissing)}</p>
          </div>
          <div>
            <span>Still Missing</span>
            <strong>{comparison.stillMissing.length}</strong>
            <p>{formatList(comparison.stillMissing)}</p>
          </div>
        </article>
      )}

      <article className="table-card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Timestamp</th>
                <th>Filename</th>
                <th>Words</th>
                <th>Missing Sections</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((record) => (
                <tr key={getRecordId(record)}>
                  <td>{record.versionLabel}</td>
                  <td>{record.timestamp || "-"}</td>
                  <td>{record.filename || "-"}</td>
                  <td>{record.word_count || 0}</td>
                  <td>{formatList(missingSections(record), "None saved")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}
