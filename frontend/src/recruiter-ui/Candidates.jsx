import { useEffect, useMemo, useState } from "react";
import { Mail, SlidersHorizontal, Sparkles, Trash2 } from "lucide-react";
import { jobAPI } from "../shared/utils/api";
import { PageTransition, ScoreRing, SkeletonBlock, SkeletonText, SkillPill, StatusBadge } from "../components/ui";
import { APPLICATION_STATUSES, formatApplicationStatus, normalizeApplicationStatus } from "../shared/utils/applicationStatus";
import { toTimestamp } from "../shared/utils/dates";
import "./Candidates.css";

const ALL_JOBS_ID = "all";
const ALL_STATUSES = "all";
const STATUS_OPTIONS = APPLICATION_STATUSES;
const ACTION_STATUS_OPTIONS = ["shortlisted", "on-hold", "rejected"];
const SORT_OPTIONS = {
  SCORE_DESC: "score_desc",
  SCORE_ASC: "score_asc",
  NEWEST: "newest",
  OLDEST: "oldest",
};

const getScore = (row) => Math.round(Number(row?.final_score) || 0);

const getTopSkills = (row) => {
  const breakdown = row?.breakdown && typeof row.breakdown === "object" ? row.breakdown : {};
  const insights = row?.insights && typeof row.insights === "object" ? row.insights : {};
  const matchedSkills = Array.isArray(insights.matched_skills)
    ? insights.matched_skills
    : Array.isArray(breakdown.matched_skills)
      ? breakdown.matched_skills
      : [];

  return [...new Set(matchedSkills.map((skill) => String(skill || "").trim()).filter(Boolean))].slice(0, 5);
};

const SUMMARY_CTA = "Click to View Complete Summary";

const openApplicationDetails = (applicationId) => {
  if (!applicationId) return;
  window.location.assign(`/applications/${applicationId}`);
};

const isInteractiveTarget = (target) =>
  Boolean(target?.closest?.("button, select, input, textarea, a"));

export default function Candidates({ initialStatusFilter = ALL_STATUSES }) {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState(ALL_JOBS_ID);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rows, setRows] = useState([]);
  const [statusFilter, setStatusFilter] = useState(ALL_STATUSES);
  const [sortBy, setSortBy] = useState(SORT_OPTIONS.SCORE_DESC);
  const [updatingStatusId, setUpdatingStatusId] = useState(null);

  useEffect(() => {
    setStatusFilter(STATUS_OPTIONS.includes(initialStatusFilter) ? initialStatusFilter : ALL_STATUSES);
  }, [initialStatusFilter]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    (async () => {
      try {
        const res = await jobAPI.recruiterCandidates({
          jobId: jobId && jobId !== ALL_JOBS_ID ? jobId : undefined,
          status: statusFilter !== ALL_STATUSES ? statusFilter : undefined,
          sort: sortBy,
          page: 1,
        });
        if (!alive) return;
        const list = Array.isArray(res?.jobs) ? res.jobs : [];
        setJobs(list);
        setJobId((prev) => {
          if (!list.length) return null;
          if (!prev) return ALL_JOBS_ID;
          if (prev === ALL_JOBS_ID) return prev;
          return list.some((job) => Number(job.id) === Number(prev)) ? prev : ALL_JOBS_ID;
        });
        setRows(Array.isArray(res?.candidates) ? res.candidates : []);
      } catch (e) {
        if (!alive) return;
        setError(e?.message || "Failed to load candidates");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [jobId, sortBy, statusFilter]);

  const visibleRows = useMemo(() => {
    const filtered = rows.filter((row) => {
      if (statusFilter === ALL_STATUSES) return true;
      return normalizeApplicationStatus(row?.status) === statusFilter;
    });

    return [...filtered].sort((a, b) => {
      if (sortBy === SORT_OPTIONS.SCORE_ASC) {
        return getScore(a) - getScore(b);
      }
      if (sortBy === SORT_OPTIONS.NEWEST) {
        return toTimestamp(b?.created_at) - toTimestamp(a?.created_at);
      }
      if (sortBy === SORT_OPTIONS.OLDEST) {
        return toTimestamp(a?.created_at) - toTimestamp(b?.created_at);
      }
      return getScore(b) - getScore(a);
    });
  }, [rows, sortBy, statusFilter]);

  const clearFilters = () => {
    setJobId(jobs.length ? ALL_JOBS_ID : null);
    setStatusFilter(ALL_STATUSES);
    setSortBy(SORT_OPTIONS.SCORE_DESC);
  };

  const handleDeleteCandidate = async (row) => {
    const appId = row?.application_id;
    if (!appId) return;
    const name = row?.candidate?.name || "this candidate";
    if (!window.confirm(`Delete ${name} from All Candidates? This removes the application.`)) {
      return;
    }
    try {
      await jobAPI.deleteApplication(appId);
      setRows((prev) => prev.filter((item) => item?.application_id !== appId));
    } catch (e) {
      alert(e?.message || "Failed to delete candidate");
    }
  };

  const handleStatusChange = async (row, status) => {
    const appId = row?.application_id;
    if (!appId) return;
    const nextStatus = normalizeApplicationStatus(status);
    setUpdatingStatusId(appId);
    setRows((prev) =>
      prev.map((item) =>
        item?.application_id === appId ? { ...item, status: nextStatus } : item
      )
    );
    try {
      const res = await jobAPI.updateApplicationStatus(appId, nextStatus);
      const savedStatus = normalizeApplicationStatus(res?.application?.status || nextStatus);
      const finalStatus = savedStatus === nextStatus ? savedStatus : nextStatus;
      setRows((prev) =>
        prev.map((item) =>
          item?.application_id === appId ? { ...item, status: finalStatus } : item
        )
      );
    } catch (e) {
      setRows((prev) =>
        prev.map((item) =>
          item?.application_id === appId ? { ...item, status: row?.status } : item
        )
      );
      alert(e?.message || "Failed to update application status");
    } finally {
      setUpdatingStatusId(null);
    }
  };

  const renderCandidateRows = () => {
    if (error) return <div className="candidate-error">{error}</div>;

    if (loading) {
      return (
        <div className="candidate-list" aria-label="Loading candidates">
          {Array.from({ length: 3 }).map((_, index) => (
            <article key={index} className="candidate-row-card candidate-row-skeleton">
              <SkeletonBlock className="candidate-rank" />
              <div className="candidate-profile-block">
                <SkeletonText lines={3} />
              </div>
              <div className="candidate-skills-block">
                <SkeletonText lines={3} />
              </div>
              <div className="candidate-score-block">
                <SkeletonBlock className="candidate-score-skeleton" />
              </div>
              <div className="candidate-actions-block">
                <SkeletonBlock className="candidate-action-skeleton" />
                <SkeletonBlock className="candidate-action-skeleton" />
              </div>
            </article>
          ))}
        </div>
      );
    }

    if (visibleRows.length === 0) {
      return (
        <div className="candidate-state">
          {rows.length === 0
            ? (jobId === ALL_JOBS_ID ? "No applications yet." : "No applications yet for this job.")
            : "No candidates match the selected filters."}
        </div>
      );
    }

    return (
      <>
        <div className="candidate-list">
          {visibleRows.map((row, index) => {
            const topSkills = getTopSkills(row);
            const currentStatus = normalizeApplicationStatus(row?.status);

            return (
              <article
                key={row.application_id}
                className="candidate-row-card"
                role="button"
                tabIndex={0}
                onClick={(e) => {
                  if (isInteractiveTarget(e.target)) return;
                  openApplicationDetails(row.application_id);
                }}
                onKeyDown={(e) => {
                  if (isInteractiveTarget(e.target)) return;
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    openApplicationDetails(row.application_id);
                  }
                }}
              >
                <div className="candidate-rank">#{index + 1}</div>

                <div className="candidate-profile-block">
                  <div className="candidate-name-line">
                    <h3>{row?.candidate?.name || "Candidate"}</h3>
                    <StatusBadge status={currentStatus} />
                  </div>
                  <p className="candidate-job-title">
                    {row?._job?.title || row?.job_title || "Applied job"}
                  </p>
                  <p className="candidate-email">
                    <Mail size={14} />
                    {row?.candidate?.email || "No email available"}
                  </p>
                </div>

                <div className="candidate-skills-block">
                  <span className="candidate-section-label">Top Skills</span>
                  <div className="candidate-skill-list">
                    {topSkills.length > 0 ? (
                      topSkills.map((skill) => (
                        <SkillPill key={`${row.application_id}-${skill}`}>{skill}</SkillPill>
                      ))
                    ) : (
                      <span className="candidate-muted">No matched skills saved</span>
                    )}
                  </div>
                  <p className="candidate-summary">
                    <Sparkles size={14} />
                    <span>{SUMMARY_CTA}</span>
                  </p>
                </div>

                <div className="candidate-score-block">
                  <ScoreRing score={getScore(row)} size={58} label="Candidate score" />
                </div>

                <div className="candidate-actions-block">
                  <button
                    type="button"
                    className="candidate-delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteCandidate(row);
                    }}
                  >
                    <Trash2 size={15} />
                    Delete
                  </button>

                  <div className="candidate-status-menu">
                    <select
                      value={ACTION_STATUS_OPTIONS.includes(currentStatus) ? currentStatus : ""}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => {
                        e.stopPropagation();
                        if (!e.target.value) return;
                        handleStatusChange(row, e.target.value);
                      }}
                      disabled={updatingStatusId === row.application_id}
                      aria-label="Update application status"
                    >
                      {!ACTION_STATUS_OPTIONS.includes(currentStatus) && (
                        <option value="" disabled>-</option>
                      )}
                      {ACTION_STATUS_OPTIONS.map((status) => (
                        <option key={status} value={status}>{formatApplicationStatus(status)}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </article>
            );
          })}
        </div>

        <div className="candidate-list-footer">
          Showing 1 to {visibleRows.length} of {visibleRows.length} candidates
        </div>
      </>
    );
  };

  return (
    <PageTransition className="candidates-panel">
      <div className="candidates-filters" aria-label="Candidate filters">
        <label className="candidate-filter-field">
          <span>Job</span>
          <select
            value={jobId ?? ""}
            onChange={(e) => {
              const value = e.target.value;
              if (!value) setJobId(null);
              else if (value === ALL_JOBS_ID) setJobId(ALL_JOBS_ID);
              else setJobId(Number(value));
            }}
            disabled={loading || jobs.length === 0}
          >
            {jobs.length === 0 ? (
              <option value="">No jobs yet</option>
            ) : (
              [
                <option key={ALL_JOBS_ID} value={ALL_JOBS_ID}>
                  All jobs
                </option>,
                ...jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                )),
              ]
            )}
          </select>
        </label>

        <label className="candidate-filter-field">
          <span>Status</span>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} disabled={loading}>
            <option value={ALL_STATUSES}>All statuses</option>
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>{formatApplicationStatus(status)}</option>
            ))}
          </select>
        </label>

        <label className="candidate-filter-field">
          <span>Sort</span>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} disabled={loading}>
            <option value={SORT_OPTIONS.SCORE_DESC}>Highest score</option>
            <option value={SORT_OPTIONS.SCORE_ASC}>Lowest score</option>
            <option value={SORT_OPTIONS.NEWEST}>Newest applications</option>
            <option value={SORT_OPTIONS.OLDEST}>Oldest applications</option>
          </select>
        </label>

        <button type="button" className="candidate-clear-filters" onClick={clearFilters} disabled={loading}>
          <SlidersHorizontal size={14} />
          Clear filters
        </button>
      </div>

      {renderCandidateRows()}
    </PageTransition>
  );
}
