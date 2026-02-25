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
  const [interviewsByApp, setInterviewsByApp] = useState({});
  // Show all candidates by default; recruiter can raise this to shortlist.
  const [shortlistMin, setShortlistMin] = useState(0);
  const [sortBy, setSortBy] = useState("final_score"); // final_score | name | created_at
  const [sortDir, setSortDir] = useState("desc");
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduleFor, setScheduleFor] = useState(null); // application row
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
          jobAPI.getAll({ status: "deleted" })
        ]);
        if (!alive) return;
        const all = [
          ...(activeRes?.jobs || []),
          ...(closedRes?.jobs || []),
          ...(draftRes?.jobs || []),
          ...(deletedRes?.jobs || [])
        ];
        const unique = new Map();
        all.forEach((j) => {
          if (j && j.id != null && !unique.has(j.id)) unique.set(j.id, j);
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
                return items.map((r) => ({ ...r, _job: job }));
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
          const job = jobs.find((j) => j.id === jobId) || null;
          const items = Array.isArray(res?.candidates) ? res.candidates : [];
          setRows(items.map((r) => ({ ...r, _job: job })));
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
            details.filter(Boolean).forEach((d) => {
              const appId = d.application_id;
              if (!appId) return;
              const ts = d.scheduled_at ? new Date(d.scheduled_at).getTime() : 0;
              const prev = map[appId];
              const prevTs = prev?.scheduled_at ? new Date(prev.scheduled_at).getTime() : 0;
              if (!prev || ts >= prevTs) {
                map[appId] = d;
              }
            });
            return map;
          } catch {
            return {};
          }
        })
      );
      const merged = {};
      maps.forEach((m) => {
        Object.keys(m).forEach((k) => {
          merged[k] = m[k];
        });
      });
      return merged;
    };

    (async () => {
      try {
        if (jobId === ALL_JOBS_ID) {
          const ids = jobs.map((j) => j.id).filter(Boolean);
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
    const j = jobs.find((x) => x.id === jobId);
    return j?.title ? `Candidates — ${j.title}` : "Candidates";
  }, [jobs, jobId]);

  const pct = (v) => Math.max(0, Math.min(100, Math.round((Number(v) || 0) * 100)));
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
    let out = Array.isArray(rows) ? rows.filter((r) => (Number(r?.final_score ?? 0) || 0) >= min) : [];
    const dir = sortDir === "asc" ? 1 : -1;
    out.sort((a, b) => {
      if (sortBy === "name") {
        const na = String(a?.candidate?.name || "").toLowerCase();
        const nb = String(b?.candidate?.name || "").toLowerCase();
        return na < nb ? -1 * dir : na > nb ? 1 * dir : 0;
      }
      if (sortBy === "created_at") {
        const ta = a?.created_at ? new Date(a.created_at).getTime() : 0;
        const tb = b?.created_at ? new Date(b.created_at).getTime() : 0;
        return (ta - tb) * dir;
      }
      // default: final_score
      const fa = Number(a?.final_score ?? 0) || 0;
      const fb = Number(b?.final_score ?? 0) || 0;
      return (fa - fb) * dir;
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
      alert("Interview scheduled. Candidate will be notified (email + in-app).");
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
      setRows((prev) => prev.filter((r) => r?.application_id !== appId));
    } catch (e) {
      alert(e?.message || "Failed to delete candidate");
    }
  };

  return (
    <div>
      <div className="dashboard-card">
        <h2 style={{ fontSize: "20px", fontWeight: 600, marginBottom: "10px", color: "#212529" }}>{title}</h2>
        <p style={{ color: "#6c757d", marginBottom: "18px" }}>Ranked candidates with explainable score breakdown.</p>

        <div style={{ display: "flex", gap: "12px", alignItems: "center", marginBottom: "16px" }}>
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
                ...jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title}
                  </option>
                ))
              ]
            )}
          </select>
          <div style={{ marginLeft: "auto", display: "flex", gap: "12px", alignItems: "center" }}>
            <div style={{ display: "flex", gap: "10px", alignItems: "center", background: "rgba(59,130,246,0.06)", padding: "10px", borderRadius: "10px", border: "1px solid rgba(59,130,246,0.12)" }}>
              <div style={{ color: "#1e40af", fontSize: "13px", fontWeight: 600 }}>Shortlist ≥</div>
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
                <option value="final_score">Match Score</option>
                <option value="name">Candidate Name</option>
                <option value="created_at">Applied Date</option>
              </select>
              <button type="button" onClick={() => setSortDir(sortDir === "asc" ? "desc" : "asc")} style={{ padding: "8px 10px", borderRadius: "8px", border: "1px solid #e5e7eb", background: "#fff", cursor: "pointer" }}>
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

        {loading ? (
          <div style={{ color: "#6c757d" }}>Loading…</div>
        ) : filteredRows.length === 0 ? (
          <div style={{ color: "#6c757d" }}>
            {jobId === ALL_JOBS_ID ? "No applications yet." : "No applications yet for this job."}
          </div>
        ) : (
          <div className="candidate-list">
            {filteredRows.map((r) => {
              const breakdown = r?.breakdown || {};
              const matched = Array.isArray(breakdown.matched_skills) ? breakdown.matched_skills : [];
              const missing = Array.isArray(breakdown.missing_skills) ? breakdown.missing_skills : [];
              const iv = interviewsByApp?.[r.application_id] || null;
              const ivDate = iv?.scheduled_at ? new Date(iv.scheduled_at).toLocaleString() : "TBD";
              const ivOutcome = String(iv?.outcome || "").toLowerCase();
              const showBreakdown =
                matched.length > 0 ||
                missing.length > 0 ||
                breakdown.semantic_score != null ||
                breakdown.skills_score != null ||
                breakdown.experience_score != null ||
                breakdown.ai_relevance_score != null;

              return (
              <div key={r.application_id} className="candidate-item">
                <div className="candidate-info" style={{ minWidth: 0 }}>
                  <div className="candidate-name" style={{ display: "flex", justifyContent: "space-between", gap: "12px" }}>
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r?.candidate?.name || "Candidate"}
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      {(() => {
                        const score = normalizeMatchScore(r?.final_score);
                        const rR = 18;
                        const ring = getRingMetrics(score, rR);
                        const stroke = ring.score >= 75 ? "#16a34a" : ring.score >= 50 ? "#f59e0b" : "#ef4444";
                        return (
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <svg width="44" height="44" viewBox="0 0 44 44">
                              <circle cx="22" cy="22" r={ring.radius} stroke="#e6edf6" strokeWidth="6" fill="transparent" />
                              <circle cx="22" cy="22" r={ring.radius} stroke={stroke} strokeWidth="6" fill="transparent" strokeDasharray={ring.strokeDasharray} strokeDashoffset={ring.strokeDashoffset} strokeLinecap="round" transform="rotate(-90 22 22)" />
                            </svg>
                            <div style={{ color: "#111827", fontWeight: 700 }}>{ring.score}%</div>
                          </div>
                        );
                      })()}
                    </div>
                  </div>
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
                      <div style={{ fontSize: "12px", fontWeight: 800, color: "#111827" }}>Skill Breakdown</div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "10px" }}>
                        {scoreBar("Semantic", breakdown.semantic_score ?? r?.semantic_score ?? 0, "#2563eb")}
                        {scoreBar("Skills", breakdown.skills_score ?? r?.skills_score ?? 0, "#16a34a")}
                        {scoreBar("Experience", breakdown.experience_score ?? 0, "#f59e0b")}
                        {scoreBar("AI relevance", breakdown.ai_relevance_score ?? 0, "#7c3aed")}
                      </div>
                      {matched.length > 0 && (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                          {matched.slice(0, 10).map((s) => (
                            <span
                              key={`m-${s}`}
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
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                      {missing.length > 0 && (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                          {missing.slice(0, 8).map((s) => (
                            <span
                              key={`x-${s}`}
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
                              {s}
                            </span>
                          ))}
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
                      <div style={{ color: "#1f2937", fontSize: "12px", fontWeight: 600 }}>
                        Scheduled: {ivDate}
                      </div>
                      <div style={{ color: "#4b5563", fontSize: "12px" }}>
                        Mode: {iv?.mode || "—"} • Duration: {iv?.duration_minutes ? `${iv.duration_minutes} min` : "—"}
                      </div>
                      {iv?.feedback && (
                        <div style={{ color: "#374151", fontSize: "12px" }}>
                          Feedback: {String(iv.feedback).slice(0, 140)}
                          {String(iv.feedback).length > 140 ? "…" : ""}
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
                        // Shared page (candidate+recruiter). Opens a real saved-details page URL.
                        window.location.assign(`/applications/${r.application_id}`);
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
                        onClick={() => handleDeleteCandidate(r)}
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
                      onClick={() => openSchedule(r)}
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
                  onChange={(e) => setScheduleForm((p) => ({ ...p, date: e.target.value }))}
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Time
                <input
                  type="time"
                  value={scheduleForm.time}
                  onChange={(e) => setScheduleForm((p) => ({ ...p, time: e.target.value }))}
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Timezone (IANA)
                <input
                  value={scheduleForm.timezone}
                  onChange={(e) => setScheduleForm((p) => ({ ...p, timezone: e.target.value }))}
                  placeholder="Asia/Kolkata"
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Duration (minutes)
                <input
                  type="number"
                  value={scheduleForm.duration_minutes}
                  onChange={(e) => setScheduleForm((p) => ({ ...p, duration_minutes: e.target.value }))}
                  min={5}
                  max={480}
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Mode
                <select
                  value={scheduleForm.mode}
                  onChange={(e) => setScheduleForm((p) => ({ ...p, mode: e.target.value }))}
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
                  onChange={(e) => setScheduleForm((p) => ({ ...p, interviewer_name: e.target.value }))}
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Meeting link (for Zoom/Phone)
                <input
                  value={scheduleForm.meeting_link}
                  onChange={(e) => setScheduleForm((p) => ({ ...p, meeting_link: e.target.value }))}
                  placeholder="https://…"
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Location (for In-person)
                <input
                  value={scheduleForm.location}
                  onChange={(e) => setScheduleForm((p) => ({ ...p, location: e.target.value }))}
                  placeholder="Office address…"
                  style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef" }}
                />
              </label>
              <label style={{ gridColumn: "1 / -1", display: "grid", gap: "6px", fontSize: "13px", color: "#374151" }}>
                Recruiter notes (internal)
                <textarea
                  value={scheduleForm.recruiter_notes}
                  onChange={(e) => setScheduleForm((p) => ({ ...p, recruiter_notes: e.target.value }))}
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

