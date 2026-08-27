export function versionLabel(version) {
  return version?.version_label || (version?.version_number ? `V${version.version_number}` : "Version");
}

export function bestVersionViewModel(improvement) {
  const best = improvement?.best_version || null;
  const latest = improvement?.latest_version || null;
  const versions = improvement?.versions || [];
  const comparisons = improvement?.comparisons || [];
  const regressions = improvement?.regressions_after_best || [];
  if (!best) {
    return {
      hasBest: false,
      message: versions.some((version) => version.analyzed)
        ? "No analyzed version has enough saved evidence for best-version selection."
        : "Analyze at least one saved version to select a Best Available Version.",
    };
  }

  const bestSnapshot = versions.find((version) => version.version_id === best.version_id) || null;
  const latestIsBest = Boolean(improvement?.latest_is_best);
  const directLatestComparison = latest && comparisons.find(
    (comparison) => comparison.from_version_id === best.version_id && comparison.to_version_id === latest.version_id,
  );
  return {
    hasBest: true,
    best,
    latest,
    bestSnapshot,
    latestIsBest,
    title: `Best Available Version: ${best.version_label}`,
    basis: "Based on currently saved analysis evidence",
    reasons: best.reasons || [],
    regressions,
    compareHref: directLatestComparison ? `#comparison-${directLatestComparison.from_version_id}-${directLatestComparison.to_version_id}` : "",
    showCompareWithLatest: Boolean(!latestIsBest && directLatestComparison),
    latestLabel: latest?.version_label || "Latest Version",
  };
}

export function snapshotBadges(version, improvement) {
  const badges = [];
  if (improvement?.best_version?.version_id === version?.version_id) {
    badges.push({ label: "Best Version", tone: "best" });
  }
  if (improvement?.latest_version?.version_id === version?.version_id) {
    badges.push({ label: "Latest Version", tone: "latest" });
  }
  return badges;
}
