import { useEffect, useCallback, useMemo, useState } from "react";
import { Calendar, DollarSign, Eye, Lock, MapPin, Trash2 } from "lucide-react";
import "./Jobs.css";
import { jobAPI } from "../shared/utils/api";
import { PageTransition, SkeletonBlock, SkeletonText } from "../components/ui";
import { formatDate } from "../shared/utils/dates";

export default function Jobs({ onViewJob, initialFilter = "all", onAllJobCountChange, onTopbarTitleChange }) {
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

  useEffect(() => {
    setFilter(initialFilter);
  }, [initialFilter]);

  const loadJobsAndCounts = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const listRes = await jobAPI.recruiterJobs({
        status: filter,
        includeStats: true,
      });

      if (listRes?.success) {
        const list = listRes.jobs || [];
        setJobs(list);
        setJobStats(Object.fromEntries(
          list.map((job) => [job.id, job.stats || { count: 0, top: 0, shortlisted: 0 }])
        ));
      }

      const nextCounts = {
        all: Number(listRes?.counts?.all) || 0,
        active: Number(listRes?.counts?.active) || 0,
        closed: Number(listRes?.counts?.closed) || 0,
        draft: Number(listRes?.counts?.draft) || 0,
      };
      setCounts(nextCounts);
      const allCount = nextCounts.all;
      onAllJobCountChange?.(allCount);
    } catch (err) {
      setError(err.message || "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [filter, onAllJobCountChange]);

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

  const handleCloseJob = async (jobId) => {
    if (!window.confirm("Close this job posting? Candidates will no longer be able to apply.")) {
      return;
    }

    try {
      await jobAPI.update(jobId, { status: "closed" });
      loadJobsAndCounts();
    } catch (err) {
      alert(err.message || "Failed to close job");
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

  const fmtCount = (n) => (typeof n === "number" ? n : "…");
  const fmtStat = (n) => (typeof n === "number" ? n : "—");
  const topbarTitle = useMemo(() => {
    const labels = {
      all: "All Jobs",
      active: "Active Jobs",
      closed: "Closed Jobs",
      draft: "Drafts",
    };
    return `${labels[filter] || "Job Listings"} (${fmtCount(counts[filter])})`;
  }, [counts, filter]);

  useEffect(() => {
    onTopbarTitleChange?.(topbarTitle);
  }, [onTopbarTitleChange, topbarTitle]);

  return (
    <PageTransition className="jobs-page">
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
        <div className="jobs-list" aria-label="Loading jobs">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="job-card-item job-card-skeleton">
              <SkeletonBlock className="job-card-logo" />
              <div className="job-card-header">
                <SkeletonText lines={3} />
              </div>
              <div className="job-card-meta">
                <SkeletonText lines={4} />
              </div>
              <div className="job-card-actions">
                <SkeletonBlock className="job-action-skeleton" />
                <SkeletonBlock className="job-action-skeleton" />
              </div>
            </div>
          ))}
        </div>
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
                <div className="job-card-logo" aria-hidden="true">
                  {(job.title || "J").trim().charAt(0).toUpperCase()}
                </div>
                <div className="job-card-header">
                  <div className="job-card-title-section">
                    <h3 className="job-card-title">{job.title}</h3>
                    {getStatusBadge(job.status)}
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
                    <span>{formatDate(job.created_at)}</span>
                  </div>
                </div>
                <div className="job-card-meta job-meta-chips">
                  <div className="job-card-meta-item job-meta-chip job-meta-chip--type">
                    <span className="job-card-meta-value">{job.job_type || "Not specified"}</span>
                  </div>
                  <div className="job-card-meta-item job-meta-chip job-meta-chip--site">
                    <span className="job-card-meta-value">{job.job_site || "Not specified"}</span>
                  </div>
                  <div className="job-card-meta-item job-meta-chip job-meta-chip--experience">
                    <span className="job-card-meta-value">
                      {job.min_experience_years != null ? `${job.min_experience_years} years` : "Not specified"}
                    </span>
                  </div>
                </div>
                <div className="job-card-metrics">
                  <div className="metric-pill">Applicants {fmtStat(jobStats?.[job.id]?.count)}</div>
                  <div className="metric-pill">Top score {fmtStat(jobStats?.[job.id]?.top)}</div>
                  <div className="metric-pill">Shortlist 70+ {fmtStat(jobStats?.[job.id]?.shortlisted)}</div>
                </div>
                <div className="job-card-actions">
                  <button
                    className="btn-view"
                    onClick={() => onViewJob?.(job.id)}
                  >
                    <Eye size={14} aria-hidden="true" />
                    View Job
                  </button>
                  {job.status !== "closed" && (
                    <button
                      className="btn-close-job"
                      onClick={() => handleCloseJob(job.id)}
                    >
                      <Lock size={14} aria-hidden="true" />
                      Close
                    </button>
                  )}
                  <button
                    className="btn-delete"
                    onClick={() => handleDelete(job.id)}
                  >
                    <Trash2 size={14} aria-hidden="true" />
                    Delete
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </PageTransition>
  );
}
