import "./Dashboard.css";
import { useEffect, useState } from "react";
import { jobAPI, interviewAPI } from "../utils/api";
import { getRingMetrics, normalizeMatchScore } from "../utils/matchScore";

const ringSize = 60;
const ringRadius = 26;

const getStartOfDay = (d) => {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
};

const getStartOfWeek = (d) => {
  const x = getStartOfDay(d);
  const day = x.getDay();
  const diff = (day + 6) % 7; // Monday as start
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

const clampPct = (n) => normalizeMatchScore(Math.abs(Number(n) || 0));

// Fetch live counts for dashboard cards
const useDashboardCounts = () => {
  const [metrics, setMetrics] = useState({
    newApplicants: { current: 0, previous: 0, change: 0, rangeLabel: "vs yesterday" },
    applications: { current: 0, previous: 0, change: 0, rangeLabel: "vs last week" },
    shortlisted: { current: 0, previous: 0, change: 0, rangeLabel: "vs last month" },
    onHold: { current: 0, previous: 0, change: 0, rangeLabel: "vs last month" }
  });
  const [upcoming, setUpcoming] = useState([]);
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [allRes, activeRes] = await Promise.all([
          jobAPI.getAll({}),
          jobAPI.getAll({ status: "active" })
        ]);
        if (!alive) return;
        const jobs = allRes?.jobs || [];
        const activeJobs = activeRes?.jobs || [];

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
          const s = start.getTime();
          const e = end.getTime();
          return t >= s && t < e;
        };

        const isShortlisted = (app) => {
          const status = String(app?.status || "").toLowerCase();
          if (status.includes("shortlist")) return true;
          return Number(app?.final_score || 0) >= 70;
        };

        const isOnHold = (app) => {
          const status = String(app?.status || "").toLowerCase();
          return status.includes("hold");
        };

        const todayApps = applications.filter((a) => inRange(a?.created_at, startToday, now));
        const yesterdayApps = applications.filter((a) => inRange(a?.created_at, startYesterday, startToday));

        const weekApps = applications.filter((a) => inRange(a?.created_at, startWeek, now));
        const lastWeekApps = applications.filter((a) => inRange(a?.created_at, startLastWeek, startWeek));

        const monthApps = applications.filter((a) => inRange(a?.created_at, startMonth, now));
        const lastMonthApps = applications.filter((a) => inRange(a?.created_at, startLastMonth, startMonth));

        const monthShortlisted = monthApps.filter(isShortlisted);
        const lastMonthShortlisted = lastMonthApps.filter(isShortlisted);

        const monthOnHold = monthApps.filter(isOnHold);
        const lastMonthOnHold = lastMonthApps.filter(isOnHold);

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
          onHold: {
            current: monthOnHold.length,
            previous: lastMonthOnHold.length,
            change: pctChange(monthOnHold.length, lastMonthOnHold.length),
            rangeLabel: "vs last month"
          }
        });

        // Try to show upcoming interviews for the first active job (best-effort)
        const firstActive = activeJobs[0];
        if (firstActive) {
          const iv = await interviewAPI.jobInterviews(firstActive.id);
          if (!alive) return;
          setUpcoming((iv?.interviews || []).slice(0, 6));

          const rc = await jobAPI.rankedCandidates(firstActive.id);
          if (!alive) return;
          setRecent((rc?.candidates || []).slice(0, 6));
        }
      } catch {
        // ignore — dashboard is non-critical
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return { metrics, upcoming, recent };
};

export default function Dashboard({ onNavigate }) {
  const handleCardClick = (view) => {
    if (onNavigate) {
      onNavigate(view);
    }
  };

  const { metrics, upcoming, recent } = useDashboardCounts();

  const renderChange = (change, rangeLabel) => {
    const value = Math.round(change || 0);
    const sign = value > 0 ? "+" : "";
    const cls = value >= 0 ? "summary-change positive" : "summary-change negative";
    return <div className={cls}>{`${sign}${value}% ${rangeLabel}`}</div>;
  };

  const renderRing = (change, color) => {
    const pct = clampPct(change);
    const ring = getRingMetrics(pct, ringRadius);
    return (
      <div className="circular-progress">
        <svg className="progress-ring" width={ringSize} height={ringSize}>
          <circle
            className="progress-ring-circle"
            stroke={color}
            strokeWidth="4"
            fill="transparent"
            r={ring.radius}
            cx={ringSize / 2}
            cy={ringSize / 2}
            strokeDasharray={ring.strokeDasharray}
            strokeDashoffset={ring.strokeDashoffset}
          />
        </svg>
        <span className="progress-percent">{`${ring.score}%`}</span>
      </div>
    );
  };

  return (
    <div className="dashboard-container">
      {/* Top Summary Cards */}
      <div className="summary-cards">
        <div 
          className="summary-card new-applicants clickable-card"
          onClick={() => handleCardClick("candidates")}
          title="View new applicants"
        >
          <div className="summary-label">NEW APPLICANTS</div>
          <div className="summary-value">{metrics.newApplicants.current ?? "-"}</div>
          {renderChange(metrics.newApplicants.change, metrics.newApplicants.rangeLabel)}
          {renderRing(metrics.newApplicants.change, "#4caf50")}
          <div className="card-hover-effect">View Details →</div>
        </div>

        <div 
          className="summary-card applications clickable-card"
          onClick={() => handleCardClick("candidates")}
          title="View all applications"
        >
          <div className="summary-label">APPLICATIONS</div>
          <div className="summary-value">{metrics.applications.current ?? "-"}</div>
          {renderChange(metrics.applications.change, metrics.applications.rangeLabel)}
          {renderRing(metrics.applications.change, "#9c27b0")}
          <div className="card-hover-effect">View Details →</div>
        </div>

        <div 
          className="summary-card shortlisted clickable-card"
          onClick={() => handleCardClick("candidates")}
          title="View shortlisted candidates"
        >
          <div className="summary-label">SHORTLISTED</div>
          <div className="summary-value">{metrics.shortlisted.current ?? "-"}</div>
          {renderChange(metrics.shortlisted.change, metrics.shortlisted.rangeLabel)}
          {renderRing(metrics.shortlisted.change, "#03a9f4")}
          <div className="card-hover-effect">View Details →</div>
        </div>

        <div 
          className="summary-card onhold clickable-card"
          onClick={() => handleCardClick("candidates")}
          title="View on-hold candidates"
        >
          <div className="summary-label">ON-HOLD</div>
          <div className="summary-value">{metrics.onHold.current ?? "-"}</div>
          {renderChange(metrics.onHold.change, metrics.onHold.rangeLabel)}
          {renderRing(metrics.onHold.change, "#ff9800")}
          <div className="card-hover-effect">View Details →</div>
        </div>
      </div>

      {/* Recent Candidates and Upcoming Interviews */}
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
            {recent.length > 0 ? (
              recent.map((c) => {
                const name = c?.candidate?.name || "Candidate";
                const avatar = name.trim().slice(0, 1).toUpperCase();
                const score = `${normalizeMatchScore(c?.final_score)}%`;
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

        <div 
          className="dashboard-card clickable-card"
          onClick={() => handleCardClick("interviews")}
          title="View upcoming interviews"
        >
          <div className="card-header">
            <div className="card-title">Upcoming Interviews</div>
          </div>
          <div className="upcoming-interviews-list">
            {upcoming && upcoming.length > 0 ? (
              upcoming.map((it) => (
                <div key={it.id} className="upcoming-interview-item">
                  <div className="interview-info">
                    <div className="interview-candidate">{it.candidate?.name || "Candidate"} - {it.job?.title || "Job"}</div>
                    <div className="interview-date">{it.scheduled_at ? new Date(it.scheduled_at).toLocaleString() : "TBD"}</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="upcoming-interview-item"><div className="interview-info"><div className="interview-candidate">No upcoming interviews</div></div></div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
