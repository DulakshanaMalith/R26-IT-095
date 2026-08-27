import assert from "node:assert/strict";
import test from "node:test";

import {
  bestVersionViewModel,
  snapshotBadges,
} from "../src/pages/proposalImprovementViewModel.js";

const improvement = {
  versions: [
    { version_id: "v1", version_number: 1, analyzed: true },
    { version_id: "v2", version_number: 2, analyzed: true },
    { version_id: "v3", version_number: 3, analyzed: true },
  ],
  comparisons: [
    { from_version_id: "v1", to_version_id: "v2" },
    { from_version_id: "v2", to_version_id: "v3" },
  ],
  best_version: {
    version_id: "v2",
    version_number: 2,
    version_label: "V2",
    reasons: [
      "No missing sections",
      "Resolved Abstract, Introduction and Literature Review",
      "No structural regressions",
      "Supervisor revision is still requested",
    ],
  },
  latest_version: {
    version_id: "v3",
    version_label: "V3",
  },
  latest_is_best: false,
  regressions_after_best: [
    { section: "Abstract", message: "Abstract became missing in V3" },
  ],
};

test("Best Available Version card view model renders V2 and required basis text", () => {
  const model = bestVersionViewModel(improvement);

  assert.equal(model.hasBest, true);
  assert.equal(model.title, "Best Available Version: V2");
  assert.equal(model.basis, "Based on currently saved analysis evidence");
  assert.deepEqual(model.reasons, improvement.best_version.reasons);
});

test("snapshot badges distinguish best version from latest version", () => {
  assert.deepEqual(snapshotBadges(improvement.versions[1], improvement), [
    { label: "Best Version", tone: "best" },
  ]);
  assert.deepEqual(snapshotBadges(improvement.versions[2], improvement), [
    { label: "Latest Version", tone: "latest" },
  ]);
});

test("latest-versus-best distinction and regression warning are exposed", () => {
  const model = bestVersionViewModel(improvement);

  assert.equal(model.latestIsBest, false);
  assert.equal(model.latestLabel, "V3");
  assert.deepEqual(model.regressions, [
    { section: "Abstract", message: "Abstract became missing in V3" },
  ]);
});

test("Compare action uses the selected best version and latest version", () => {
  const model = bestVersionViewModel(improvement);

  assert.equal(model.showCompareWithLatest, true);
  assert.equal(model.compareHref, "#comparison-v2-v3");
});

test("Compare with Latest is hidden when best version is latest", () => {
  const model = bestVersionViewModel({
    ...improvement,
    latest_version: { version_id: "v2", version_label: "V2" },
    latest_is_best: true,
    regressions_after_best: [],
  });

  assert.equal(model.showCompareWithLatest, false);
});

test("empty and partial states return safe messages", () => {
  assert.equal(bestVersionViewModel({ versions: [] }).hasBest, false);
  assert.equal(
    bestVersionViewModel({ versions: [{ analyzed: false }] }).message,
    "Analyze at least one saved version to select a Best Available Version.",
  );
  assert.equal(
    bestVersionViewModel({ versions: [{ analyzed: true }] }).message,
    "No analyzed version has enough saved evidence for best-version selection.",
  );
});
