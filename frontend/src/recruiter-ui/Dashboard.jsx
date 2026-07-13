import "./Dashboard.css";
import { useEffect, useState } from "react";
import { jobAPI } from "../utils/api";
import { PageTransition, SkeletonBlock, SkeletonText } from "../components/ui";

const getStartOfDay = (d) => {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
};

const getStartOfWeek = (d) => {
  const x = getStartOfDay(d);
  const day = x.getDay();
  const diff = (day + 6) % 7;
  x.setDate(x.getDate() - diff);
  return x;
};

const getStartOfMonth = (d) => {
  const x = getStartOfDay(d);
  x.setDate(1);
  return x;
};

const pctChange = (current, previous) => {
  const cur = Number(current) || 0;
  const prev = Number(previous) || 0;
  if (prev === 0) return cur === 0 ? 0 : 100;
  return ((cur - prev) / prev) * 100;
};

const getApplicationStatus = (app) => {
  const value = String(app?.status || "not-reviewed").toLowerCase().trim().replaceAll("_", "-").replace(/\s+/g, "-");
  if (value === "submitted" || value === "accepted" || value === "applied" || value === "pending") {
    return "not-reviewed";
  }
  if (value === "hold" || value === "onhold") return "on-hold";
  return value;
};

const statusIncludes = (app, keyword) => getApplicationStatus(app).includes(keyword);
const statusEquals = (app, status) => getApplicationStatus(app) === status;

const useDashboardCounts = () => {
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState({
    newApplicants: { current: 0, previous: 0, change: 0, rangeLabel: "vs yesterday" },
    applications: { current: 0, previous: 0, change: 0, rangeLabel: "vs last week" },
    notReviewed: { current: 0, previous: 0, change: 0, rangeLabel: "vs last month" },
    shortlisted: { current: 0, previous: 0, change: 0, rangeLabel: "vs last month" },
    onHold: { current: 0, previous: 0, change: 0, rangeLabel: "vs last month" },
    rejected: { current: 0, previous: 0, change: 0, rangeLabel: "vs last month" }
  });
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        setLoading(true);
        const allRes = await jobAPI.getAll({});
        if (!alive) return;
        const jobs = allRes?.jobs || [];

        const allCandidates = await Promise.all(
          jobs.map(async (job) => {
            try {
              const res = await jobAPI.rankedCandidates(job.id);
              return Array.isArray(res?.candidates) ? res.candidates : [];
            } catch {
              return [];
            }
          })
        );

        if (!alive) return;
        const applications = allCandidates.flat();

        const now = new Date();
        const startToday = getStartOfDay(now);
        const startYesterday = new Date(startToday);
        startYesterday.setDate(startYesterday.getDate() - 1);

        const startWeek = getStartOfWeek(now);
        const startLastWeek = new Date(startWeek);
        startLastWeek.setDate(startLastWeek.getDate() - 7);

        const startMonth = getStartOfMonth(now);
        const startLastMonth = new Date(startMonth);
        startLastMonth.setMonth(startLastMonth.getMonth() - 1);

        const inRange = (ts, start, end) => {
          if (!ts) return false;
          const t = new Date(ts).getTime();
          return t >= start.getTime() && t < end.getTime();
        };

        const todayApps = applications.filter((a) => inRange(a?.created_at, startToday, now));
        const yesterdayApps = applications.filter((a) => inRange(a?.created_at, startYesterday, startToday));
        const weekApps = applications.filter((a) => inRange(a?.created_at, startWeek, now));
        const lastWeekApps = applications.filter((a) => inRange(a?.created_at, startLastWeek, startWeek));
        const monthApps = applications.filter((a) => inRange(a?.created_at, startMonth, now));
        const lastMonthApps = applications.filter((a) => inRange(a?.created_at, startLastMonth, startMonth));

        const monthShortlisted = monthApps.filter((a) => statusIncludes(a, "shortlist"));
        const lastMonthShortlisted = lastMonthApps.filter((a) => statusIncludes(a, "shortlist"));
        const monthNotReviewed = monthApps.filter((a) => statusEquals(a, "not-reviewed"));
        const lastMonthNotReviewed = lastMonthApps.filter((a) => statusEquals(a, "not-reviewed"));
        const monthOnHold = monthApps.filter((a) => statusEquals(a, "on-hold"));
        const lastMonthOnHold = lastMonthApps.filter((a) => statusEquals(a, "on-hold"));
        const monthRejected = monthApps.filter((a) => statusIncludes(a, "reject"));
        const lastMonthRejected = lastMonthApps.filter((a) => statusIncludes(a, "reject"));

        setMetrics({
          newApplicants: {
            current: todayApps.length,
            previous: yesterdayApps.length,
            change: pctChange(todayApps.length, yesterdayApps.length),
            rangeLabel: "vs yesterday"
          },
          applications: {
            current: weekApps.length,
            previous: lastWeekApps.length,
            change: pctChange(weekApps.length, lastWeekApps.length),
            rangeLabel: "vs last week"
          },
          shortlisted: {
            current: monthShortlisted.length,
            previous: lastMonthShortlisted.length,
            change: pctChange(monthShortlisted.length, lastMonthShortlisted.length),
            rangeLabel: "vs last month"
          },
          notReviewed: {
            current: monthNotReviewed.length,
            previous: lastMonthNotReviewed.length,
            change: pctChange(monthNotReviewed.length, lastMonthNotReviewed.length),
            rangeLabel: "vs last month"
          },
          onHold: {
            current: monthOnHold.length,
            previous: lastMonthOnHold.length,
            change: pctChange(monthOnHold.length, lastMonthOnHold.length),
            rangeLabel: "vs last month"
          },
          rejected: {
            current: monthRejected.length,
            previous: lastMonthRejected.length,
            change: pctChange(monthRejected.length, lastMonthRejected.length),
            rangeLabel: "vs last month"
          }
        });

        setRecent(
          [...applications]
            .sort((a, b) => new Date(b?.created_at || 0).getTime() - new Date(a?.created_at || 0).getTime())
            .slice(0, 6)
        );
      } catch {
        // Dashboard metrics are non-critical; keep fallback values visible.
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
      <div className="card-hover-effect">View Details →</div>
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
