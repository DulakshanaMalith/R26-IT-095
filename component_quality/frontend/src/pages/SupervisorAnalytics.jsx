import { useEffect, useState } from "react";
import { BarChart3, BookOpenCheck, CalendarClock, FileText, History, MessageSquareText, Target } from "lucide-react";
import ChartCard from "../components/ChartCard";
import EmptyState from "../components/EmptyState";
import Loader from "../components/Loader";
import MetricCard from "../components/MetricCard";
import CommonResourcesBarChart from "../charts/BarChart";
import CategoryBarChart from "../charts/CategoryBarChart";
import AnalysesLineChart from "../charts/LineChart";
import WeaknessPieChart from "../charts/PieChart";
import { getSupervisorAnalytics } from "../api";
import { truncate } from "../utils";

const FEEDBACK_CATEGORIES = ["Weakness", "Strength", "Other", "Highlight"];

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function getDominantTag(distribution = {}) {
  return Object.entries(distribution).reduce(
    (best, [name, count]) => (Number(count) > best.count ? { name, count: Number(count) } : best),
    { name: "None", count: 0 },
  );
}

function getMostRecommendedResource(resources = []) {
  return resources[0] || null;
}

function buildKeyInsights(analytics) {
  const insights = [];
  const dominantTag = getDominantTag(analytics?.tag_distribution || {});
  const topResource = getMostRecommendedResource(analytics?.common_resources || []);
  const totalAnalyses = Number(analytics?.total_analyses || 0);

  if (dominantTag.count > 0) {
    insights.push(`Most reviewed proposals need support with ${dominantTag.name}.`);
  }
  if (topResource) {
    insights.push(`Students most frequently receive recommendations related to ${topResource.category}.`);
  }
  insights.push(`${totalAnalyses} proposal${totalAnalyses === 1 ? " has" : "s have"} been reviewed so far.`);
  return insights;
}

function normalizeDistribution(distribution = {}) {
  return FEEDBACK_CATEGORIES.reduce(
    (result, category) => ({
      ...result,
      [category]: Number(distribution[category] || 0),
    }),
    {},
  );
}

function getTodayKey() {
  return new Date().toISOString().slice(0, 10);
}

function getTodayOrLatest(items = [], valueKey) {
  if (!items.length) return null;
  const todayItem = items.find((item) => item.date === getTodayKey());
  return todayItem || items[items.length - 1];
}

function RecentProposalAnalysesTable({ records = [] }) {
  return (
    <article className="table-card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Student</th>
              <th>Student ID</th>
              <th>Filename</th>
              <th>Source</th>
              <th>Weakness Category</th>
              <th>Preview</th>
            </tr>
          </thead>
          <tbody>
            {records.length ? (
              records.map((record) => (
                <tr key={record.id || `${record.timestamp}-${record.filename}`}>
                  <td className="table-date">{formatDate(record.timestamp)}</td>
                  <td>{record.student_name || "Not provided"}</td>
                  <td>{record.student_id || "Not provided"}</td>
                  <td className="table-filename" title={record.filename || ""}>{record.filename || "-"}</td>
                  <td>{record.source || "unknown"}</td>
                  <td><span className="tag-pill">{record.predicted_tag || "-"}</span></td>
                  <td className="table-preview" title={record.input_preview || ""}>{truncate(record.input_preview, 80)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7}>No proposal analyses saved yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </article>
  );
}

export default function SupervisorAnalytics({ analytics, loadingData }) {
  const [supervisorAnalytics, setSupervisorAnalytics] = useState(analytics || null);
  const [analyticsLoading, setAnalyticsLoading] = useState(!analytics);
  const activeAnalytics = supervisorAnalytics || analytics;
  const hasData = (activeAnalytics?.total_analyses || 0) > 0;
  const dominantTag = getDominantTag(activeAnalytics?.tag_distribution || {});
  const topResource = getMostRecommendedResource(activeAnalytics?.common_resources || []);
  const latestSubmission = activeAnalytics?.recent_analyses?.[0] || null;
  const keyInsights = buildKeyInsights(activeAnalytics);
  const feedbackDistribution = normalizeDistribution(activeAnalytics?.tag_distribution || {});
  const reviewActivity = activeAnalytics?.daily_review_count || activeAnalytics?.daily_counts || [];
  const todayReviews = getTodayOrLatest(reviewActivity, "count");
  const allStrength = hasData
    && Number(feedbackDistribution.Strength || 0) === Number(activeAnalytics?.total_analyses || 0);

  useEffect(() => {
    let cancelled = false;

    async function loadSupervisorAnalytics() {
      setAnalyticsLoading(true);
      try {
        const data = await getSupervisorAnalytics();
        if (!cancelled) {
          setSupervisorAnalytics(data);
        }
      } catch (error) {
        console.error("Could not load supervisor analytics", error);
      } finally {
        if (!cancelled) {
          setAnalyticsLoading(false);
        }
      }
    }

    loadSupervisorAnalytics();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="page-stack">
      <div className="page-title">
        <div>
          <span className="eyebrow">Supervisor Analytics</span>
          <h2>Supervisor Analytics Dashboard</h2>
          <p>Real-time overview of student proposal analyses, detected weaknesses, feedback patterns, and learning resources.</p>
        </div>
      </div>

      {loadingData || analyticsLoading ? (
        <Loader />
      ) : !hasData ? (
        <EmptyState
          icon={BarChart3}
          title="No analytics available yet."
          message="Analyze proposals to generate supervisor insights."
          actionLabel="Go to Analyzer"
          actionTo="/analyzer"
        />
      ) : (
        <>
          <div className="metric-grid insight-summary-grid">
            <MetricCard icon={History} label="Total Proposals Reviewed" value={activeAnalytics.total_analyses} />
            <MetricCard icon={Target} label="Dominant Feedback Category" value={dominantTag.name} detail={`${dominantTag.count} proposal${dominantTag.count === 1 ? "" : "s"}`} />
            <MetricCard compact icon={BookOpenCheck} label="Most Recommended Resource" value={topResource?.category || "None"} detail={topResource?.title || "No resource recommendations yet"} />
            <MetricCard compact icon={CalendarClock} label="Latest Submission" value={latestSubmission ? formatDate(latestSubmission.timestamp) : "-"} detail={latestSubmission?.filename || "No submission yet"} />
          </div>

          <article className="insight-panel">
            <div className="section-title compact">
              <div>
                <span className="eyebrow">Key Insights</span>
                <h2>What supervisors should notice</h2>
              </div>
            </div>
            <div className="insight-list">
              {keyInsights.map((insight) => (
                <p key={insight}>{insight}</p>
              ))}
            </div>
          </article>

          <div className="metric-grid">
            <MetricCard icon={FileText} label="Reviewed Proposals" value={activeAnalytics.total_analyses} />
            <MetricCard icon={Target} label="Dominant Category" value={activeAnalytics.most_common_tag || "None"} />
            <MetricCard icon={MessageSquareText} label="Feedback Retrieved" value={activeAnalytics.feedback_count_total} />
            <MetricCard icon={BookOpenCheck} label="Resources Suggested" value={activeAnalytics.resource_count_total} />
          </div>

          <div className="chart-grid">
            <ChartCard title="Feedback Category Distribution" eyebrow="Detected categories">
              {allStrength && (
                <p className="chart-note">
                  Current records mostly show Strength feedback. More proposal analyses are needed for a broader weakness distribution.
                </p>
              )}
              <WeaknessPieChart distribution={feedbackDistribution} />
            </ChartCard>
            <ChartCard title="Weakness Distribution Breakdown" eyebrow="Count and percentage">
              <CategoryBarChart distribution={feedbackDistribution} />
            </ChartCard>
            <ChartCard title="Proposal Review Activity" eyebrow="Daily review count">
              <div className="chart-stat-row">
                <article>
                  <span>Today's Reviews</span>
                  <strong>{todayReviews?.count ?? 0}</strong>
                </article>
              </div>
              <AnalysesLineChart
                data={reviewActivity}
                dataKey="count"
                yAxisLabel="Review Count"
                seriesName="Review Count"
                emptyMessage="No analytics data available"
              />
            </ChartCard>
            <ChartCard title="Most Recommended Learning Resources" eyebrow="Top recommended resources" wide>
              <CommonResourcesBarChart resources={activeAnalytics.common_resources} />
            </ChartCard>
          </div>

          <article className="insight-panel">
            <div className="section-title compact">
              <div>
                <span className="eyebrow">Common Feedback Themes</span>
                <h2>Feedback and resource patterns</h2>
              </div>
            </div>
            <div className="theme-grid">
              <article>
                <span>Dominant tag</span>
                <strong>{dominantTag.name}</strong>
                <p>{dominantTag.count} of {activeAnalytics.total_analyses} reviewed proposals</p>
              </article>
              <article>
                <span>Feedback retrieved</span>
                <strong>{activeAnalytics.feedback_count_total}</strong>
                <p>Feedback comments retrieved across recent analyses</p>
              </article>
              <article>
                <span>Resource recommendations</span>
                <strong>{activeAnalytics.resource_count_total}</strong>
                <p>Learning resources recommended to students</p>
              </article>
            </div>
          </article>

          <div className="section-title compact">
            <div>
              <span className="eyebrow">Recent Proposal Analyses</span>
              <h2>Latest reviewed submissions</h2>
            </div>
          </div>
          <RecentProposalAnalysesTable records={activeAnalytics.recent_analyses || []} />
        </>
      )}

    </section>
  );
}
