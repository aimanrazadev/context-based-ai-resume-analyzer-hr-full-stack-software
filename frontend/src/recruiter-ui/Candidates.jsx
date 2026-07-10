import { useEffect, useMemo, useState } from "react";
import { jobAPI } from "../utils/api";
import { ScoreRing, SkillPill, StatusBadge } from "../components/ui";

const ALL_JOBS_ID = "all";
const ALL_STATUSES = "all";
const STATUS_OPTIONS = ["submitted", "shortlisted", "rejected", "on-hold", "accepted"];
const SORT_OPTIONS = {
  SCORE_DESC: "score_desc",
  SCORE_ASC: "score_asc",
  NEWEST: "newest",
  OLDEST: "oldest",
};

export default function Candidates() {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState(ALL_JOBS_ID);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rows, setRows] = useState([]);
  const [statusFilter, setStatusFilter] = useState(ALL_STATUSES);
  const [sortBy, setSortBy] = useState(SORT_OPTIONS.SCORE_DESC);
  const [updatingStatusId, setUpdatingStatusId] = useState(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    (async () => {
      try {
        const [activeRes, closedRes, draftRes, deletedRes] = await Promise.all([
          jobAPI.getAll({ status: "active" }),
          jobAPI.getAll({ status: "closed" }),
          jobAPI.getAll({ status: "draft" }),
          jobAPI.getAll({ status: "deleted" }),
        ]);
        if (!alive) return;
        const all = [
          ...(activeRes?.jobs || []),
          ...(closedRes?.jobs || []),
          ...(draftRes?.jobs || []),
          ...(deletedRes?.jobs || []),
        ];
        const unique = new Map();
        all.forEach((job) => {
          if (job && job.id != null && !unique.has(job.id)) unique.set(job.id, job);
        });
        const list = Array.from(unique.values());
        setJobs(list);
        setJobId((prev) => (prev ? prev : list.length ? ALL_JOBS_ID : null));
      } catch (e) {
        if (!alive) return;
        setError(e?.message || "Failed to load jobs");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    if (!jobId || jobs.length === 0) {
      setRows([]);
      return;
    }
    setLoading(true);
    setError("");
    (async () => {
      try {
        if (jobId === ALL_JOBS_ID) {
          const allRows = await Promise.all(
            jobs.map(async (job) => {
              try {
                const res = await jobAPI.rankedCandidates(job.id);
                const items = Array.isArray(res?.candidates) ? res.candidates : [];
                return items.map((row, index) => ({ ...row, _job: job, _rankIndex: index }));
              } catch {
                return [];
              }
            })
          );
          if (!alive) return;
          setRows(allRows.flat());
        } else {
          const res = await jobAPI.rankedCandidates(jobId);
          if (!alive) return;
          const job = jobs.find((item) => item.id === jobId) || null;
          const items = Array.isArray(res?.candidates) ? res.candidates : [];
          setRows(items.map((row, index) => ({ ...row, _job: job, _rankIndex: index })));
        }
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
  }, [jobId, jobs]);

  const title = useMemo(() => {
    if (jobId === ALL_JOBS_ID) return "All Candidates";
    const job = jobs.find((item) => item.id === jobId);
    return job?.title ? `Candidates - ${job.title}` : "Candidates";
  }, [jobs, jobId]);

  const visibleRows = useMemo(() => {
    const filtered = rows.filter((row) => {
      if (statusFilter === ALL_STATUSES) return true;
      return String(row?.status || "submitted").toLowerCase() === statusFilter;
    });

    return [...filtered].sort((a, b) => {
      if (sortBy === SORT_OPTIONS.SCORE_ASC) {
        return (Number(a?.final_score) || 0) - (Number(b?.final_score) || 0);
      }
      if (sortBy === SORT_OPTIONS.NEWEST) {
        return new Date(b?.created_at || 0) - new Date(a?.created_at || 0);
      }
      if (sortBy === SORT_OPTIONS.OLDEST) {
        return new Date(a?.created_at || 0) - new Date(b?.created_at || 0);
      }
      return (Number(b?.final_score) || 0) - (Number(a?.final_score) || 0);
    });
  }, [rows, sortBy, statusFilter]);

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
    const nextStatus = String(status || "").toLowerCase();
    setUpdatingStatusId(appId);
    try {
      const res = await jobAPI.updateApplicationStatus(appId, nextStatus);
      const savedStatus = res?.application?.status || nextStatus;
      setRows((prev) =>
        prev.map((item) =>
          item?.application_id === appId ? { ...item, status: savedStatus } : item
        )
      );
    } catch (e) {
      alert(e?.message || "Failed to update application status");
    } finally {
      setUpdatingStatusId(null);
    }
  };

  return (
    <div>
      <div className="dashboard-card">
        <h2 style={{ fontSize: "20px", fontWeight: 600, marginBottom: "10px", color: "#212529" }}>{title}</h2>
        <p style={{ color: "#6c757d", marginBottom: "18px" }}>Ranked by the final score stored when each candidate applied.</p>

        <div style={{ display: "flex", gap: "12px", alignItems: "center", marginBottom: "16px", flexWrap: "wrap" }}>
          <div style={{ color: "#6c757d", fontSize: "14px" }}>Job:</div>
          <select
            value={jobId ?? ""}
            onChange={(e) => {
              const value = e.target.value;
              if (!value) {
                setJobId(null);
              } else if (value === ALL_JOBS_ID) {
                setJobId(ALL_JOBS_ID);
              } else {
                setJobId(Number(value));
              }
            }}
            style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef", minWidth: "320px" }}
            disabled={loading || jobs.length === 0}
          >
            {jobs.length === 0 ? (
              <option value="">No jobs yet</option>
            ) : (
              [
                <option key={ALL_JOBS_ID} value={ALL_JOBS_ID}>
                  All candidates
                </option>,
                ...jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                )),
              ]
            )}
          </select>

          <div style={{ color: "#6c757d", fontSize: "14px" }}>Status:</div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef", minWidth: "180px" }}
            disabled={loading}
          >
            <option value={ALL_STATUSES}>All statuses</option>
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>

          <div style={{ color: "#6c757d", fontSize: "14px" }}>Sort:</div>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef", minWidth: "190px" }}
            disabled={loading}
          >
            <option value={SORT_OPTIONS.SCORE_DESC}>Highest stored score</option>
            <option value={SORT_OPTIONS.SCORE_ASC}>Lowest stored score</option>
            <option value={SORT_OPTIONS.NEWEST}>Newest applications</option>
            <option value={SORT_OPTIONS.OLDEST}>Oldest applications</option>
          </select>

        </div>

        {error && (
          <div style={{ color: "#b91c1c", background: "rgba(185,28,28,0.08)", border: "1px solid rgba(185,28,28,0.18)", borderRadius: "10px", padding: "12px", marginBottom: "14px" }}>
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ color: "#6c757d" }}>Loading...</div>
        ) : visibleRows.length === 0 ? (
          <div style={{ color: "#6c757d" }}>
            {rows.length === 0
              ? (jobId === ALL_JOBS_ID ? "No applications yet." : "No applications yet for this job.")
              : "No candidates match the selected filters."}
          </div>
        ) : (
          <div className="candidate-list">
            {visibleRows.map((row, index) => {
              const breakdown = row?.breakdown && typeof row.breakdown === "object" ? row.breakdown : {};
              const insights = row?.insights || {};
              const matchedSkills = Array.isArray(insights.matched_skills)
                ? insights.matched_skills
                : Array.isArray(breakdown.matched_skills)
                  ? breakdown.matched_skills
                  : [];
              const missingSkills = Array.isArray(insights.missing_skills)
                ? insights.missing_skills
                : Array.isArray(breakdown.missing_skills)
                  ? breakdown.missing_skills
                  : [];
              const strengths = Array.isArray(insights.strengths) ? insights.strengths : [];
              const weaknesses = Array.isArray(insights.weaknesses) ? insights.weaknesses : [];
              const recruiterSummary = insights.recruiter_summary || row?.ranking_explanation || "";
              const recommendation = insights.recommendation || "";
              const skillsScore = Number(row?.skills_score ?? breakdown.skills_score ?? 0);

              return (
                <div key={row.application_id} className="candidate-item">
                  <div className="candidate-info" style={{ minWidth: 0 }}>
                    <div className="candidate-name" style={{ display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "start" }}>
                      <div style={{ display: "grid", gap: "4px", minWidth: 0 }}>
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          #{index + 1} {row?.candidate?.name || "Candidate"}
                        </span>
                        <div style={{ color: "#6b7280", fontSize: "12px" }}>{row?.candidate?.email || "No email available"}</div>
                        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                          <StatusBadge status={row?.status || "submitted"} />
                          {row?._job?.title && jobId === ALL_JOBS_ID && (
                            <span style={{ color: "#6b7280", fontSize: 12 }}>{row._job.title}</span>
                          )}
                        </div>
                      </div>
                      <ScoreRing score={row?.final_score ?? 0} size={52} />
                    </div>

                    {recruiterSummary && (
                      <div
                        style={{
                          marginTop: "10px",
                          padding: "10px 12px",
                          borderRadius: "12px",
                          border: "1px solid rgba(15,23,42,0.08)",
                          background: "rgba(15,23,42,0.03)",
                          color: "#1f2937",
                          fontSize: "13px",
                          lineHeight: 1.5,
                        }}
                      >
                        {recruiterSummary}
                      </div>
                    )}

                    {recommendation && <div style={{ marginTop: 10, fontSize: 13 }}><strong>Recommendation:</strong> {recommendation}</div>}
                    {insights.reasoning && <div style={{ marginTop: 8, fontSize: 13, lineHeight: 1.5 }}><strong>Reasoning:</strong> {insights.reasoning}</div>}
                    {(strengths.length > 0 || weaknesses.length > 0) && (
                      <div style={{ marginTop: 10, display: "grid", gap: 6, fontSize: 12 }}>
                        {strengths.length > 0 && <div><strong>Strengths:</strong> {strengths.slice(0, 4).join(", ")}</div>}
                        {weaknesses.length > 0 && <div><strong>Weaknesses:</strong> {weaknesses.slice(0, 4).join(", ")}</div>}
                      </div>
                    )}

                    {(matchedSkills.length > 0 || missingSkills.length > 0) && (
                      <div
                        style={{
                          marginTop: 10,
                          padding: "10px 12px",
                          borderRadius: 12,
                          border: "1px solid rgba(15,23,42,0.08)",
                          background: "rgba(15,23,42,0.025)",
                          display: "grid",
                          gap: 8,
                        }}
                      >
                        <div style={{ fontSize: 12, fontWeight: 800, color: "#111827" }}>
                          Skill match breakdown{Number.isFinite(skillsScore) ? ` · ${Math.round(skillsScore)}%` : ""}
                        </div>
                        {matchedSkills.length > 0 && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                            {matchedSkills.slice(0, 8).map((skill) => (
                              <SkillPill key={`matched-${row.application_id}-${skill}`} tone="positive">{skill}</SkillPill>
                            ))}
                          </div>
                        )}
                        {missingSkills.length > 0 && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                            {missingSkills.slice(0, 8).map((skill) => (
                              <SkillPill key={`missing-${row.application_id}-${skill}`} tone="negative">{skill}</SkillPill>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    <div style={{ marginTop: "10px" }}>
                      <select
                        value={row?.status || "submitted"}
                        onChange={(e) => handleStatusChange(row, e.target.value)}
                        disabled={updatingStatusId === row.application_id}
                        style={{
                          padding: "8px 10px",
                          borderRadius: "10px",
                          border: "1px solid rgba(15,23,42,0.18)",
                          background: "#fff",
                          marginRight: 10,
                          fontWeight: 600,
                        }}
                        aria-label="Update application status"
                      >
                        {STATUS_OPTIONS.map((status) => (
                          <option key={status} value={status}>{status}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        style={{
                          padding: "8px 12px",
                          borderRadius: "10px",
                          border: "1px solid rgba(15,23,42,0.18)",
                          background: "rgba(15,23,42,0.04)",
                          cursor: "pointer",
                          fontWeight: 600,
                        }}
                        onClick={() => {
                          window.location.assign(`/applications/${row.application_id}`);
                        }}
                      >
                        View Application Details
                      </button>
                      {jobId === ALL_JOBS_ID && (
                        <button
                          type="button"
                          style={{
                            marginLeft: "10px",
                            padding: "8px 12px",
                            borderRadius: "10px",
                            border: "1px solid rgba(239,68,68,0.35)",
                            background: "rgba(239,68,68,0.10)",
                            cursor: "pointer",
                            fontWeight: 700,
                            color: "#b91c1c",
                          }}
                          onClick={() => handleDeleteCandidate(row)}
                        >
                          Delete Candidate
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
}
