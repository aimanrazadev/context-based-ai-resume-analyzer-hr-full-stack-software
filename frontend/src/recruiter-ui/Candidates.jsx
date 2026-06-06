import { useEffect, useMemo, useState } from "react";
import { interviewAPI, jobAPI } from "../utils/api";
import { getRingMetrics, normalizeMatchScore } from "../utils/matchScore";

const ALL_JOBS_ID = "all";

export default function Candidates() {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState(ALL_JOBS_ID);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rows, setRows] = useState([]);
  const [rankingMeta, setRankingMeta] = useState(null);
  const [interviewsByApp, setInterviewsByApp] = useState({});
  const [shortlistMin, setShortlistMin] = useState(0);
  const [sortBy, setSortBy] = useState("ranking");
  const [sortDir, setSortDir] = useState("asc");
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduleFor, setScheduleFor] = useState(null);
  const [scheduleForm, setScheduleForm] = useState({
    date: "",
    time: "",
    timezone: "Asia/Kolkata",
    duration_minutes: 30,
    mode: "Zoom",
    meeting_link: "",
    location: "",
    interviewer_name: "",
    recruiter_notes: "",
  });

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
        if (!alive) return;
        setLoading(false);
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
      setRankingMeta(null);
      setInterviewsByApp({});
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
          setRankingMeta(null);
          setRows(allRows.flat());
        } else {
          const res = await jobAPI.rankedCandidates(jobId);
          if (!alive) return;
          const job = jobs.find((item) => item.id === jobId) || null;
          const items = Array.isArray(res?.candidates) ? res.candidates : [];
          setRankingMeta(res?.reranking || null);
          setRows(items.map((row, index) => ({ ...row, _job: job, _rankIndex: index })));
        }
      } catch (e) {
        if (!alive) return;
        setError(e?.message || "Failed to load candidates");
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [jobId, jobs]);

  useEffect(() => {
    let alive = true;
    if (!jobId || jobs.length === 0) {
      setInterviewsByApp({});
      return;
    }

    const loadForJobs = async (jobIds) => {
      const maps = await Promise.all(
        jobIds.map(async (jid) => {
          try {
            const res = await interviewAPI.jobInterviews(jid);
            const base = Array.isArray(res?.interviews) ? res.interviews : [];
            const details = await Promise.all(
              base.map(async (it) => {
                try {
                  const r = await interviewAPI.interviewDetails(it.id);
                  return r?.interview || null;
                } catch {
                  return null;
                }
              })
            );
            const map = {};
            details.filter(Boolean).forEach((detail) => {
              const appId = detail.application_id;
              if (!appId) return;
              const ts = detail.scheduled_at ? new Date(detail.scheduled_at).getTime() : 0;
              const prev = map[appId];
              const prevTs = prev?.scheduled_at ? new Date(prev.scheduled_at).getTime() : 0;
              if (!prev || ts >= prevTs) {
                map[appId] = detail;
              }
            });
            return map;
          } catch {
            return {};
          }
        })
      );
      const merged = {};
      maps.forEach((map) => {
        Object.keys(map).forEach((key) => {
          merged[key] = map[key];
        });
      });
      return merged;
    };

    (async () => {
      try {
        if (jobId === ALL_JOBS_ID) {
          const ids = jobs.map((job) => job.id).filter(Boolean);
          const map = await loadForJobs(ids);
          if (!alive) return;
          setInterviewsByApp(map);
        } else {
          const map = await loadForJobs([jobId]);
          if (!alive) return;
          setInterviewsByApp(map);
        }
      } catch {
        if (!alive) return;
        setInterviewsByApp({});
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

  const pct = (value) => Math.max(0, Math.min(100, Math.round((Number(value) || 0) * 100)));
  const scoreBar = (label, value, color) => (
    <div style={{ display: "grid", gap: "6px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "8px" }}>
        <span style={{ color: "#6c757d", fontSize: "12px", fontWeight: 600 }}>{label}</span>
        <span style={{ color: "#111827", fontSize: "12px", fontWeight: 700 }}>{pct(value)}%</span>
      </div>
      <div style={{ height: "6px", borderRadius: "999px", background: "rgba(15,23,42,0.08)", overflow: "hidden" }}>
        <div style={{ width: `${pct(value)}%`, height: "100%", background: color }} />
      </div>
    </div>
  );

  const filteredRows = useMemo(() => {
    const min = Number(shortlistMin) || 0;
    const out = Array.isArray(rows) ? rows.filter((row) => (Number(row?.final_score ?? 0) || 0) >= min) : [];
    const dir = sortDir === "asc" ? 1 : -1;
    out.sort((a, b) => {
      if (sortBy === "name") {
        const aName = String(a?.candidate?.name || "").toLowerCase();
        const bName = String(b?.candidate?.name || "").toLowerCase();
        return aName < bName ? -1 * dir : aName > bName ? 1 * dir : 0;
      }
      if (sortBy === "created_at") {
        const aTime = a?.created_at ? new Date(a.created_at).getTime() : 0;
        const bTime = b?.created_at ? new Date(b.created_at).getTime() : 0;
        return (aTime - bTime) * dir;
      }
      if (sortBy === "ranking") {
        const aRank = Number(a?._rankIndex ?? Number.MAX_SAFE_INTEGER);
        const bRank = Number(b?._rankIndex ?? Number.MAX_SAFE_INTEGER);
        return (aRank - bRank) * dir;
      }
      const aScore = Number(a?.final_score ?? 0) || 0;
      const bScore = Number(b?.final_score ?? 0) || 0;
      return (aScore - bScore) * dir;
    });
    return out;
  }, [rows, shortlistMin, sortBy, sortDir]);

  const openSchedule = (row) => {
    setScheduleFor(row || null);
    setScheduleOpen(true);
    setScheduleForm((prev) => ({
      ...prev,
      interviewer_name: prev.interviewer_name || "Recruiter",
      recruiter_notes: prev.recruiter_notes || "",
    }));
  };

  const closeSchedule = () => {
    setScheduleOpen(false);
    setScheduleFor(null);
  };

  const submitSchedule = async () => {
    const appId = scheduleFor?.application_id;
    if (!appId) return;
    if (!scheduleForm.date || !scheduleForm.time) {
      alert("Please choose date and time.");
      return;
    }
    const scheduled_at = `${scheduleForm.date}T${scheduleForm.time}:00`;
    const payload = {
      application_id: appId,
      scheduled_at,
      timezone: scheduleForm.timezone || null,
      duration_minutes: Number(scheduleForm.duration_minutes) || 30,
      mode: scheduleForm.mode || null,
      meeting_link: scheduleForm.meeting_link || null,
      location: scheduleForm.location || null,
      interviewer_name: scheduleForm.interviewer_name || null,
      recruiter_notes: scheduleForm.recruiter_notes || null,
    };
    try {
      await interviewAPI.scheduleInterview(payload);
      alert("Interview scheduled. Candidate will be notified by email and in-app.");
      closeSchedule();
    } catch (e) {
      alert(e?.message || "Failed to schedule interview");
    }
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

  return (
    <div>
      <div className="dashboard-card">
        <h2 style={{ fontSize: "20px", fontWeight: 600, marginBottom: "10px", color: "#212529" }}>{title}</h2>
        <p style={{ color: "#6c757d", marginBottom: "18px" }}>Ranked candidates with explainable score breakdown.</p>

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

          <div style={{ marginLeft: "auto", display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
            <div
              style={{
                display: "flex",
                gap: "10px",
                alignItems: "center",
                background: "rgba(59,130,246,0.06)",
                padding: "10px",
                borderRadius: "10px",
                border: "1px solid rgba(59,130,246,0.12)",
              }}
            >
              <div style={{ color: "#1e40af", fontSize: "13px", fontWeight: 600 }}>Shortlist &gt;=</div>
              <input
                value={shortlistMin}
                onChange={(e) => setShortlistMin(e.target.value)}
                type="number"
                min="0"
                max="100"
                style={{
                  width: "64px",
                  padding: "8px 10px",
                  borderRadius: "8px",
                  border: "1px solid rgba(59,130,246,0.18)",
                  background: "#fff",
                  fontWeight: 600,
                  textAlign: "center",
                }}
              />
              <span style={{ color: "#6c757d", fontSize: "13px", fontWeight: 500 }}>%</span>
            </div>

            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <label style={{ color: "#6c757d", fontSize: "13px" }}>Sort</label>
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} style={{ padding: "8px 10px", borderRadius: "8px", border: "1px solid #e5e7eb" }}>
                <option value="ranking">Recommended Ranking</option>
                <option value="final_score">Match Score</option>
                <option value="name">Candidate Name</option>
                <option value="created_at">Applied Date</option>
              </select>
              <button
                type="button"
                onClick={() => setSortDir(sortDir === "asc" ? "desc" : "asc")}
                style={{ padding: "8px 10px", borderRadius: "8px", border: "1px solid #e5e7eb", background: "#fff", cursor: "pointer" }}
              >
                {sortDir === "asc" ? "↑" : "↓"}
              </button>
            </div>

            <div style={{ color: "#6c757d", fontSize: "12px" }}>
              Showing {filteredRows.length} of {rows.length}
            </div>
          </div>
        </div>

        {error && (
          <div style={{ color: "#b91c1c", background: "rgba(185,28,28,0.08)", border: "1px solid rgba(185,28,28,0.18)", borderRadius: "10px", padding: "12px", marginBottom: "14px" }}>
            {error}
          </div>
        )}

        {rankingMeta?.enabled && jobId !== ALL_JOBS_ID && (
          <div
            style={{
              marginBottom: "14px",
              padding: "12px 14px",
              borderRadius: "12px",
              border: "1px solid rgba(37,99,235,0.18)",
              background: "rgba(37,99,235,0.06)",
              color: "#1e3a8a",
              display: "grid",
              gap: "6px",
            }}
          >
            <div style={{ fontSize: "13px", fontWeight: 800 }}>Cross-encoder reranking active</div>
            <div style={{ fontSize: "13px" }}>
              Model: <strong>{rankingMeta?.model || "BAAI/bge-reranker-base"}</strong>
            </div>
            <div style={{ fontSize: "12px", color: "#334155" }}>
              Top {rankingMeta?.shortlist_size || 0} candidates are shortlisted with cosine similarity first, then reranked with the transformer model.
            </div>
          </div>
        )}

        {loading ? (
          <div style={{ color: "#6c757d" }}>Loading...</div>
        ) : filteredRows.length === 0 ? (
          <div style={{ color: "#6c757d" }}>
            {jobId === ALL_JOBS_ID ? "No applications yet." : "No applications yet for this job."}
          </div>
        ) : (
          <div className="candidate-list">
            {filteredRows.map((row, index) => {
              const breakdown = row?.breakdown || {};
              const insights = row?.insights || {};
              const reranking = row?.reranking || {};
              const matched = Array.isArray(breakdown.matched_skills) ? breakdown.matched_skills : [];
              const missing = Array.isArray(breakdown.missing_skills) ? breakdown.missing_skills : [];
              const strengths = Array.isArray(insights.strengths) ? insights.strengths : [];
              const weaknesses = Array.isArray(insights.weaknesses) ? insights.weaknesses : [];
              const aiMissing = Array.isArray(insights.missing_skills_ai) ? insights.missing_skills_ai : [];
              const evidence = Array.isArray(insights.evidence) ? insights.evidence : [];
              const notes = Array.isArray(insights.notes) ? insights.notes : [];
              const recruiterSummary = insights.recruiter_summary || row?.ranking_explanation || "";
              const recommendation = insights.recommendation || "";
              const iv = interviewsByApp?.[row.application_id] || null;
              const ivDate = iv?.scheduled_at ? new Date(iv.scheduled_at).toLocaleString() : "TBD";
              const ivOutcome = String(iv?.outcome || "").toLowerCase();
              const showBreakdown =
                matched.length > 0 ||
                missing.length > 0 ||
                breakdown.semantic_score != null ||
                breakdown.skills_score != null ||
                breakdown.experience_score != null ||
                breakdown.projects_score != null ||
                breakdown.education_score != null ||
                breakdown.ai_relevance_score != null ||
                reranking?.was_reranked;

              return (
                <div key={row.application_id} className="candidate-item">
                  <div className="candidate-info" style={{ minWidth: 0 }}>
                    <div className="candidate-name" style={{ display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "start" }}>
                      <div style={{ display: "grid", gap: "4px", minWidth: 0 }}>
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          #{index + 1} {row?.candidate?.name || "Candidate"}
                        </span>
                        <div style={{ color: "#6b7280", fontSize: "12px" }}>{row?.candidate?.email || "No email available"}</div>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {(() => {
                          const score = normalizeMatchScore(row?.final_score);
                          const radius = 18;
                          const ring = getRingMetrics(score, radius);
                          const stroke = ring.score >= 75 ? "#16a34a" : ring.score >= 50 ? "#f59e0b" : "#ef4444";
                          return (
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <svg width="44" height="44" viewBox="0 0 44 44">
                                <circle cx="22" cy="22" r={ring.radius} stroke="#e6edf6" strokeWidth="6" fill="transparent" />
                                <circle
                                  cx="22"
                                  cy="22"
                                  r={ring.radius}
                                  stroke={stroke}
                                  strokeWidth="6"
                                  fill="transparent"
                                  strokeDasharray={ring.strokeDasharray}
                                  strokeDashoffset={ring.strokeDashoffset}
                                  strokeLinecap="round"
                                  transform="rotate(-90 22 22)"
                                />
                              </svg>
                              <div style={{ color: "#111827", fontWeight: 700 }}>{ring.score}%</div>
                            </div>
                          );
                        })()}
                      </div>
                    </div>

                    {reranking?.was_reranked && (
                      <div
                        style={{
                          marginTop: "10px",
                          padding: "10px 12px",
                          borderRadius: "12px",
                          border: "1px solid rgba(99,102,241,0.18)",
                          background: "rgba(99,102,241,0.06)",
                          display: "grid",
                          gap: "6px",
                        }}
                      >
                        <div style={{ fontSize: "12px", fontWeight: 800, color: "#312e81" }}>Reranking Comparison</div>
                        <div style={{ color: "#374151", fontSize: "12px" }}>
                          Semantic shortlist #{reranking?.semantic_shortlist_rank} to reranked #{reranking?.reranked_shortlist_rank}
                        </div>
                        <div style={{ color: "#374151", fontSize: "12px" }}>
                          Cross-encoder {pct(reranking?.reranker_score || 0)}% vs cosine {pct(reranking?.semantic_score || 0)}%
                        </div>
                      </div>
                    )}

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

                    {showBreakdown && (
                      <div
                        style={{
                          marginTop: "10px",
                          padding: "10px 12px",
                          borderRadius: "12px",
                          border: "1px solid rgba(15,23,42,0.08)",
                          background: "rgba(15,23,42,0.03)",
                          display: "grid",
                          gap: "10px",
                        }}
                      >
                        <div style={{ fontSize: "12px", fontWeight: 800, color: "#111827" }}>Score Breakdown</div>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "10px" }}>
                          {scoreBar("Semantic", breakdown.semantic_score ?? row?.semantic_score ?? 0, "#2563eb")}
                          {scoreBar("Skills", breakdown.skills_score ?? row?.skills_score ?? 0, "#16a34a")}
                          {scoreBar("Experience", breakdown.experience_score ?? 0, "#f59e0b")}
                          {scoreBar("Projects", breakdown.projects_score ?? 0, "#0f766e")}
                          {scoreBar("Education", breakdown.education_score ?? 0, "#dc2626")}
                          {scoreBar("AI Relevance", breakdown.ai_relevance_score ?? 0, "#7c3aed")}
                          {reranking?.was_reranked && scoreBar("Reranker", reranking?.reranker_score ?? 0, "#4338ca")}
                        </div>

                        {recommendation && (
                          <div style={{ color: "#111827", fontSize: "12px", fontWeight: 700 }}>
                            Recommendation: <span style={{ color: "#4338ca" }}>{recommendation}</span>
                          </div>
                        )}

                        {matched.length > 0 && (
                          <div>
                            <div style={{ color: "#065f46", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>Matched Skills</div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                              {matched.slice(0, 10).map((skill) => (
                                <span
                                  key={`matched-${skill}`}
                                  style={{
                                    background: "rgba(16,185,129,0.12)",
                                    color: "#065f46",
                                    border: "1px solid rgba(16,185,129,0.3)",
                                    padding: "4px 8px",
                                    borderRadius: "999px",
                                    fontSize: "12px",
                                    fontWeight: 600,
                                  }}
                                >
                                  {skill}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {(missing.length > 0 || aiMissing.length > 0) && (
                          <div>
                            <div style={{ color: "#991b1b", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>Missing Skills</div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                              {[...missing, ...aiMissing].slice(0, 10).map((skill) => (
                                <span
                                  key={`missing-${skill}`}
                                  style={{
                                    background: "rgba(239,68,68,0.10)",
                                    color: "#991b1b",
                                    border: "1px solid rgba(239,68,68,0.25)",
                                    padding: "4px 8px",
                                    borderRadius: "999px",
                                    fontSize: "12px",
                                    fontWeight: 600,
                                  }}
                                >
                                  {skill}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {(strengths.length > 0 || weaknesses.length > 0) && (
                          <div style={{ display: "grid", gap: "8px" }}>
                            {strengths.length > 0 && (
                              <div>
                                <div style={{ color: "#065f46", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>Strengths</div>
                                <ul style={{ margin: 0, paddingLeft: "18px", color: "#065f46", fontSize: "12px" }}>
                                  {strengths.slice(0, 4).map((item) => (
                                    <li key={`strength-${item}`}>{item}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {weaknesses.length > 0 && (
                              <div>
                                <div style={{ color: "#991b1b", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>Weaknesses</div>
                                <ul style={{ margin: 0, paddingLeft: "18px", color: "#991b1b", fontSize: "12px" }}>
                                  {weaknesses.slice(0, 4).map((item) => (
                                    <li key={`weakness-${item}`}>{item}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}

                        {(evidence.length > 0 || notes.length > 0) && (
                          <div style={{ display: "grid", gap: "8px" }}>
                            {evidence.length > 0 && (
                              <div>
                                <div style={{ color: "#111827", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>Candidate Insights</div>
                                <ul style={{ margin: 0, paddingLeft: "18px", color: "#4b5563", fontSize: "12px" }}>
                                  {evidence.slice(0, 4).map((item) => (
                                    <li key={`evidence-${item}`}>{item}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {notes.length > 0 && (
                              <div>
                                <div style={{ color: "#111827", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>Notes</div>
                                <ul style={{ margin: 0, paddingLeft: "18px", color: "#6b7280", fontSize: "12px" }}>
                                  {notes.slice(0, 3).map((item) => (
                                    <li key={`note-${item}`}>{item}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {iv && (
                      <div
                        style={{
                          marginTop: "10px",
                          padding: "10px 12px",
                          borderRadius: "12px",
                          border: "1px solid rgba(59,130,246,0.18)",
                          background: "rgba(59,130,246,0.06)",
                          display: "grid",
                          gap: "6px",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", gap: "10px" }}>
                          <div style={{ fontSize: "12px", fontWeight: 800, color: "#111827" }}>Interview</div>
                          {ivOutcome && (
                            <span
                              style={{
                                padding: "2px 8px",
                                borderRadius: "999px",
                                fontSize: "11px",
                                fontWeight: 700,
                                textTransform: "capitalize",
                                background:
                                  ivOutcome === "pass"
                                    ? "rgba(34,197,94,0.12)"
                                    : ivOutcome === "fail"
                                      ? "rgba(239,68,68,0.12)"
                                      : "rgba(168,85,247,0.12)",
                                color:
                                  ivOutcome === "pass"
                                    ? "#15803d"
                                    : ivOutcome === "fail"
                                      ? "#b91c1c"
                                      : "#6b21a8",
                              }}
                            >
                              {ivOutcome}
                            </span>
                          )}
                        </div>
                        <div style={{ color: "#1f2937", fontSize: "12px", fontWeight: 600 }}>Scheduled: {ivDate}</div>
                        <div style={{ color: "#4b5563", fontSize: "12px" }}>
                          Mode: {iv?.mode || "-"} • Duration: {iv?.duration_minutes ? `${iv.duration_minutes} min` : "-"}
                        </div>
                        {iv?.feedback && (
                          <div style={{ color: "#374151", fontSize: "12px" }}>
                            Feedback: {String(iv.feedback).slice(0, 140)}
                            {String(iv.feedback).length > 140 ? "..." : ""}
                          </div>
                        )}
                      </div>
                    )}

                    <div style={{ marginTop: "10px" }}>
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
                      <button
                        type="button"
                        style={{
                          marginLeft: "10px",
                          padding: "8px 12px",
                          borderRadius: "10px",
                          border: "1px solid rgba(59,130,246,0.35)",
                          background: "rgba(59,130,246,0.10)",
                          cursor: "pointer",
                          fontWeight: 700,
                        }}
                        onClick={() => openSchedule(row)}
                      >
                        Schedule Interview
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {scheduleOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15,23,42,0.45)",
            zIndex: 1200,
            display: "grid",
            placeItems: "center",
            padding: "18px",
          }}
          onClick={closeSchedule}
        >
          <div
            style={{
              width: "min(760px, 100%)",
              background: "#fff",
              borderRadius: "14px",
              border: "1px solid rgba(15,23,42,0.10)",
              boxShadow: "var(--shadow-card)",
              padding: "16px",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "center" }}>
              <div style={{ fontSize: "18px", fontWeight: 700, color: "#111827" }}>Schedule interview</div>
              <button
                type="button"
                onClick={closeSchedule}
                style={{ border: "none", background: "transparent", fontSize: "20px", cursor: "pointer" }}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <div style={{ marginTop: "6px", color: "#6c757d", fontSize: "13px" }}>
              Candidate: {scheduleFor?.candidate?.name || "Candidate"} • Application #{scheduleFor?.application_id}
            </div>

            <div style={{ marginTop: "14px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Date
                <input
                  type="date"
                  value={scheduleForm.date}
                  onChange={(e) => setScheduleForm((prev) => ({ ...prev, date: e.target.value }))}
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Time
                <input
                  type="time"
                  value={scheduleForm.time}
                  onChange={(e) => setScheduleForm((prev) => ({ ...prev, time: e.target.value }))}
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Timezone (IANA)
                <input
                  value={scheduleForm.timezone}
                  onChange={(e) => setScheduleForm((prev) => ({ ...prev, timezone: e.target.value }))}
                  placeholder="Asia/Kolkata"
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Duration (minutes)
                <input
                  type="number"
                  value={scheduleForm.duration_minutes}
                  onChange={(e) => setScheduleForm((prev) => ({ ...prev, duration_minutes: e.target.value }))}
                  min={5}
                  max={480}
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Mode
                <select
                  value={scheduleForm.mode}
                  onChange={(e) => setScheduleForm((prev) => ({ ...prev, mode: e.target.value }))}
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                >
                  <option value="Zoom">Zoom</option>
                  <option value="Phone">Phone</option>
                  <option value="In-person">In-person</option>
                </select>
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Interviewer name
                <input
                  value={scheduleForm.interviewer_name}
                  onChange={(e) => setScheduleForm((prev) => ({ ...prev, interviewer_name: e.target.value }))}
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Meeting link (for Zoom/Phone)
                <input
                  value={scheduleForm.meeting_link}
                  onChange={(e) => setScheduleForm((prev) => ({ ...prev, meeting_link: e.target.value }))}
                  placeholder="https://..."
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Location (for In-person)
                <input
                  value={scheduleForm.location}
                  onChange={(e) => setScheduleForm((prev) => ({ ...prev, location: e.target.value }))}
                  placeholder="Office address..."
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ gridColumn: "1 / -1", display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Recruiter notes (internal)
                <textarea
                  value={scheduleForm.recruiter_notes}
                  onChange={(e) => setScheduleForm((prev) => ({ ...prev, recruiter_notes: e.target.value }))}
                  rows={3}
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef", resize: "vertical" }}
                />
              </label>
            </div>

            <div style={{ marginTop: "12px", display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={closeSchedule}
                style={{
                  padding: "10px 12px",
                  borderRadius: "10px",
                  border: "1px solid rgba(15,23,42,0.14)",
                  background: "#fff",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitSchedule}
                style={{
                  padding: "10px 12px",
                  borderRadius: "10px",
                  border: "1px solid #0f172a",
                  background: "#0f172a",
                  color: "#fff",
                  fontWeight: 800,
                  cursor: "pointer",
                }}
              >
                Schedule
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
