import { useEffect, useCallback, useMemo, useState } from "react";
import { Calendar, DollarSign, Link2, MapPin, Phone, UserRound } from "lucide-react";
import "./Jobs.css";
import { jobAPI } from "../utils/api";

export default function Jobs({ onViewJob, initialFilter = "all" }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Initialize from initialFilter to avoid fetching "all" first (causes Draft tab to show active jobs).
  const [filter, setFilter] = useState(initialFilter); // all, active, closed, draft
  const [counts, setCounts] = useState({
    all: null,
    active: null,
    closed: null,
    draft: null,
  });
  const [jobStats, setJobStats] = useState({});
  const [statsLoading, setStatsLoading] = useState(false);

  useEffect(() => {
    setFilter(initialFilter);
  }, [initialFilter]);

  const loadJobsAndCounts = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      // Fetch counts in parallel, and re-use the selected tab request as the list response.
      const allP = jobAPI.getAll({});
      const activeP = jobAPI.getAll({ status: "active" });
      const closedP = jobAPI.getAll({ status: "closed" });
      const draftP = jobAPI.getAll({ status: "draft" });

      const listP =
        filter === "all" ? allP : filter === "active" ? activeP : filter === "closed" ? closedP : draftP;

      const [allRes, activeRes, closedRes, draftRes, listRes] = await Promise.all([
        allP,
        activeP,
        closedP,
        draftP,
        listP,
      ]);

      if (listRes?.success) {
        const list = listRes.jobs || [];
        setJobs(list);
        setStatsLoading(true);
        try {
          const statsEntries = await Promise.all(
            list.map(async (job) => {
              try {
                const res = await jobAPI.rankedCandidates(job.id);
                const candidates = res?.candidates || [];
                const count = candidates.length;
                const sum = candidates.reduce((acc, c) => acc + (Number(c?.final_score) || 0), 0);
                const avg = count ? Math.round(sum / count) : 0;
                const top = count ? Math.max(...candidates.map((c) => Number(c?.final_score) || 0)) : 0;
                const shortlisted = candidates.filter((c) => (Number(c?.final_score) || 0) >= 70).length;
                return [job.id, { count, avg, top, shortlisted }];
              } catch {
                return [job.id, { count: null, avg: null, top: null, shortlisted: null }];
              }
            })
          );
          setJobStats(Object.fromEntries(statsEntries));
        } finally {
          setStatsLoading(false);
        }
      }

      setCounts({
        all: (allRes?.jobs || []).length,
        active: (activeRes?.jobs || []).length,
        closed: (closedRes?.jobs || []).length,
        draft: (draftRes?.jobs || []).length,
      });
    } catch (err) {
      setError(err.message || "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadJobsAndCounts();
  }, [loadJobsAndCounts]);

  const handleDelete = async (jobId) => {
    if (!window.confirm("Are you sure you want to delete this job?")) {
      return;
    }

    try {
      await jobAPI.delete(jobId);
      loadJobsAndCounts(); // Reload jobs + counts
    } catch (err) {
      alert(err.message || "Failed to delete job");
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      active: { label: "Active", className: "status-active" },
      closed: { label: "Closed", className: "status-closed" },
      draft: { label: "Draft", className: "status-draft" },
      deleted: { label: "Deleted", className: "status-closed" }
    };
    
    const config = statusConfig[status] || statusConfig.active;
    return <span className={`status-badge ${config.className}`}>{config.label}</span>;
  };

  const title = useMemo(() => {
    if (filter === "all") return "All Job Listings";
    if (filter === "active") return "Active Jobs";
    if (filter === "closed") return "Closed Jobs";
    if (filter === "draft") return "Drafts";
    return "Job Listings";
  }, [filter]);

  const headerCount = useMemo(() => {
    if (filter === "all") return counts.all;
    if (filter === "active") return counts.active;
    if (filter === "closed") return counts.closed;
    if (filter === "draft") return counts.draft;
    return null;
  }, [counts, filter]);

  const fmtCount = (n) => (typeof n === "number" ? n : "…");
  const fmtStat = (n) => (typeof n === "number" ? n : "—");
  const prettyText = (value) => String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
  const formatPerks = (perks) => {
    if (!perks || typeof perks !== "object") return "None";
    const active = Object.keys(perks).filter((k) => perks[k]);
    return active.length ? active.map(prettyText).join(", ") : "None";
  };

  return (
    <div className="jobs-page">
      <div className="jobs-header">
        <h2>
          {title} {loading ? "" : `(${fmtCount(headerCount)})`}
        </h2>
        <p>Manage and view all your job postings</p>
      </div>

      {/* Filter Tabs */}
      <div className="jobs-filters">
        <button
          className={`filter-tab ${filter === "all" ? "active" : ""}`}
          onClick={() => setFilter("all")}
        >
          All Jobs ({fmtCount(counts.all)})
        </button>
        <button
          className={`filter-tab ${filter === "active" ? "active" : ""}`}
          onClick={() => setFilter("active")}
        >
          Active ({fmtCount(counts.active)})
        </button>
        <button
          className={`filter-tab ${filter === "closed" ? "active" : ""}`}
          onClick={() => setFilter("closed")}
        >
          Closed ({fmtCount(counts.closed)})
        </button>
        <button
          className={`filter-tab ${filter === "draft" ? "active" : ""}`}
          onClick={() => setFilter("draft")}
        >
          Draft ({fmtCount(counts.draft)})
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="error-message">{error}</div>
      )}

      {/* Loading State */}
      {loading ? (
        <div className="loading-state">Loading jobs...</div>
      ) : (
        /* Jobs List */
        <div className="jobs-list">
          {jobs.length === 0 ? (
            <div className="empty-state">
              <p>No jobs found. Create your first job posting!</p>
            </div>
          ) : (
            jobs.map((job) => (
              <div key={job.id} className="job-card-item">
                <div className="job-card-header">
                  <div className="job-card-title-section">
                    <h3 className="job-card-title">{job.title}</h3>
                    {getStatusBadge(job.status)}
                  </div>
                  <div className="job-card-actions">
                    <button
                      className="btn-view"
                      onClick={() => onViewJob?.(job.id)}
                    >
                      View
                    </button>
                    <button
                      className="btn-delete"
                      onClick={() => handleDelete(job.id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="job-card-details">
                  <div className="job-detail-item">
                    <MapPin className="detail-label" aria-hidden="true" />
                    <span>{job.location || "Not specified"}</span>
                  </div>
                  {job.salary_range && (
                    <div className="job-detail-item">
                      <DollarSign className="detail-label" aria-hidden="true" />
                      <span>{job.salary_range}</span>
                    </div>
                  )}
                  <div className="job-detail-item">
                    <Calendar className="detail-label" aria-hidden="true" />
                    <span>{new Date(job.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="job-card-meta">
                  <div className="job-card-meta-item">
                    <span className="job-card-meta-label">Opportunity Type</span>
                    <span className="job-card-meta-value">{job.opportunity_type || "Not specified"}</span>
                  </div>
                  <div className="job-card-meta-item">
                    <span className="job-card-meta-label">Job Type</span>
                    <span className="job-card-meta-value">{job.job_type || "Not specified"}</span>
                  </div>
                  <div className="job-card-meta-item">
                    <span className="job-card-meta-label">Job Site</span>
                    <span className="job-card-meta-value">{job.job_site || "Not specified"}</span>
                  </div>
                  <div className="job-card-meta-item">
                    <span className="job-card-meta-label">Openings</span>
                    <span className="job-card-meta-value">{job.openings ?? "Not specified"}</span>
                  </div>
                  <div className="job-card-meta-item">
                    <span className="job-card-meta-label">Min Experience</span>
                    <span className="job-card-meta-value">
                      {job.min_experience_years != null ? `${job.min_experience_years} years` : "Not specified"}
                    </span>
                  </div>
                  <div className="job-card-meta-item">
                    <span className="job-card-meta-label">Perks</span>
                    <span className="job-card-meta-value">{formatPerks(job.perks)}</span>
                  </div>
                  <div className="job-card-meta-item">
                    <span className="job-card-meta-label">
                      <UserRound className="detail-label" aria-hidden="true" />
                      Screening Availability
                    </span>
                    <span className="job-card-meta-value">{job.screening_availability || "Not specified"}</span>
                  </div>
                  <div className="job-card-meta-item">
                    <span className="job-card-meta-label">
                      <Phone className="detail-label" aria-hidden="true" />
                      Screening Phone
                    </span>
                    <span className="job-card-meta-value">{job.screening_phone || "Not specified"}</span>
                  </div>
                  <div className="job-card-meta-item">
                    <span className="job-card-meta-label">
                      <Link2 className="detail-label" aria-hidden="true" />
                      Job Posting Link
                    </span>
                    <span className="job-card-meta-value">
                      {job.job_link ? (
                        <a className="job-card-link" href={job.job_link} target="_blank" rel="noreferrer">
                          {job.job_link}
                        </a>
                      ) : (
                        "Not specified"
                      )}
                    </span>
                  </div>
                </div>
                <div className="job-card-metrics">
                  <div className="metric-pill">Applicants {fmtStat(jobStats?.[job.id]?.count)}</div>
                  <div className="metric-pill">Avg score {fmtStat(jobStats?.[job.id]?.avg)}</div>
                  <div className="metric-pill">Top score {fmtStat(jobStats?.[job.id]?.top)}</div>
                  <div className="metric-pill">Shortlist 70+ {fmtStat(jobStats?.[job.id]?.shortlisted)}</div>
                  {statsLoading && <div className="metric-hint">Updating metrics…</div>}
                </div>
                <div className="job-card-description">
                  <p>{job.description?.substring(0, 150)}...</p>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
