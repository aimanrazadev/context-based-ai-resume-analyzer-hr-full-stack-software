import "./Dashboard.css";
import { useEffect, useState } from "react";
import { jobAPI } from "../utils/api";
import { PageTransition, SkeletonBlock, SkeletonText } from "../components/ui";

const pctChange = (current, previous) => {
  const cur = Number(current) || 0;
  const prev = Number(previous) || 0;
  if (prev === 0) return cur === 0 ? 0 : 100;
  return ((cur - prev) / prev) * 100;
};

const metricFromServer = (metric, rangeLabel) => {
  const current = Number(metric?.current) || 0;
  const previous = Number(metric?.previous) || 0;
  return {
    current,
    previous,
    change: pctChange(current, previous),
    rangeLabel,
  };
};

const EMPTY_METRICS = {
  newApplicants: { current: 0, previous: 0, change: 0, rangeLabel: "vs yesterday" },
  applications: { current: 0, previous: 0, change: 0, rangeLabel: "vs last week" },
  notReviewed: { current: 0, previous: 0, change: 0, rangeLabel: "vs last month" },
  shortlisted: { current: 0, previous: 0, change: 0, rangeLabel: "vs last month" },
  onHold: { current: 0, previous: 0, change: 0, rangeLabel: "vs last month" },
  rejected: { current: 0, previous: 0, change: 0, rangeLabel: "vs last month" },
};

const useDashboardCounts = () => {
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState(EMPTY_METRICS);
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        setLoading(true);
        const dashboardRes = await jobAPI.recruiterDashboard();
        if (!alive) return;

        const serverMetrics = dashboardRes?.metrics || {};
        setMetrics({
          newApplicants: metricFromServer(serverMetrics.new_applicants, "vs yesterday"),
          applications: metricFromServer(serverMetrics.applications, "vs last week"),
          notReviewed: metricFromServer(serverMetrics.not_reviewed, "vs last month"),
          shortlisted: metricFromServer(serverMetrics.shortlisted, "vs last month"),
          onHold: metricFromServer(serverMetrics.on_hold, "vs last month"),
          rejected: metricFromServer(serverMetrics.rejected, "vs last month"),
        });
        setRecent(Array.isArray(dashboardRes?.recent_candidates) ? dashboardRes.recent_candidates : []);
      } catch {
        if (!alive) return;
        setMetrics(EMPTY_METRICS);
        setRecent([]);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return { metrics, recent, loading };
};

export default function Dashboard({ onNavigate }) {
  const { metrics, recent, loading } = useDashboardCounts();

  const handleCardClick = (view, options = {}) => {
    onNavigate?.(view, options);
  };

  const renderChange = (change, rangeLabel) => {
    const value = Math.round(change || 0);
    const sign = value > 0 ? "+" : "";
    const cls = value >= 0 ? "summary-change positive" : "summary-change negative";
    return <div className={cls}>{`${sign}${value}% ${rangeLabel}`}</div>;
  };

  const renderMetricCard = ({ className, title, label, metric, statusFilter }) => (
    <div
      className={`summary-card ${className} clickable-card`}
      onClick={() => handleCardClick("candidates", { statusFilter })}
      title={title}
    >
      <div className="summary-label">{label}</div>
      <div className="summary-value">{metric.current ?? "-"}</div>
      {renderChange(metric.change, metric.rangeLabel)}
      <div className="card-hover-effect">View Details {">"}</div>
    </div>
  );

  const renderMetricSkeletons = () => (
    <div className="summary-cards" aria-label="Loading dashboard metrics">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="summary-card dashboard-skeleton-card">
          <SkeletonText lines={1} className="dashboard-skeleton-label" />
          <SkeletonBlock className="dashboard-skeleton-number" />
          <SkeletonText lines={1} className="dashboard-skeleton-change" />
        </div>
      ))}
    </div>
  );

  return (
    <PageTransition className="dashboard-container">
      {loading ? renderMetricSkeletons() : (
        <div className="summary-cards">
          {renderMetricCard({
            className: "new-applicants",
            title: "View new applicants",
            label: "New Applicants",
            metric: metrics.newApplicants,
          })}
          {renderMetricCard({
            className: "applications",
            title: "View all applications",
            label: "Applications",
            metric: metrics.applications,
          })}
          {renderMetricCard({
            className: "not-reviewed",
            title: "View not reviewed candidates",
            label: "Not Reviewed",
            metric: metrics.notReviewed,
            statusFilter: "not-reviewed",
          })}
          {renderMetricCard({
            className: "shortlisted",
            title: "View shortlisted candidates",
            label: "Shortlisted",
            metric: metrics.shortlisted,
            statusFilter: "shortlisted",
          })}
          {renderMetricCard({
            className: "onhold",
            title: "View on-hold candidates",
            label: "On-Hold",
            metric: metrics.onHold,
            statusFilter: "on-hold",
          })}
          {renderMetricCard({
            className: "rejected",
            title: "View rejected candidates",
            label: "Rejected",
            metric: metrics.rejected,
            statusFilter: "rejected",
          })}
        </div>
      )}

      <div className="dashboard-main-grid">
        <div
          className="dashboard-card clickable-card"
          onClick={() => handleCardClick("candidates")}
          title="View recent candidates"
        >
          <div className="card-header">
            <div className="card-title">Recent Candidates</div>
          </div>
          <div className="recent-candidates-list">
            {loading ? (
              Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="recent-candidate-item">
                  <SkeletonBlock className="recent-candidate-avatar is-skeleton" />
                  <div className="recent-candidate-info">
                    <SkeletonText lines={2} />
                  </div>
                  <SkeletonBlock className="recent-candidate-score-skeleton" />
                </div>
              ))
            ) : recent.length > 0 ? (
              recent.map((c) => {
                const name = c?.candidate?.name || "Candidate";
                const avatar = name.trim().slice(0, 1).toUpperCase();
                const score = `${Number(c?.final_score ?? 0)}%`;
                return (
                  <div key={c.application_id} className="recent-candidate-item">
                    <div className="recent-candidate-avatar">{avatar}</div>
                    <div className="recent-candidate-info">
                      <div className="recent-candidate-name">{name}</div>
                      <div className="recent-candidate-role">Application #{c.application_id}</div>
                    </div>
                    <div className="recent-candidate-match">
                      <span className="match-score">{score}</span>
                      <span className="match-label">Match</span>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="recent-candidate-item">
                <div className="recent-candidate-info">
                  <div className="recent-candidate-name">No recent candidates</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
