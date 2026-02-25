import { useEffect, useMemo, useState } from "react";
import { interviewAPI, jobAPI } from "../utils/api";

export default function Interviews() {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [rows, setRows] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [evaluateMode, setEvaluateMode] = useState(false);
  const [selectedOutcome, setSelectedOutcome] = useState("pass");
  const [remarks, setRemarks] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    jobAPI
      .getAll({ status: "active" })
      .then((res) => {
        if (!alive) return;
        const list = res?.jobs || [];
        setJobs(list);
        setJobId((prev) => prev ?? (list[0]?.id ?? null));
      })
      .catch((e) => {
        if (!alive) return;
        setError(e?.message || "Failed to load jobs");
      })
      .finally(() => {
        if (!alive) return;
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    if (!jobId) {
      setRows([]);
      setSelectedId(null);
      setDetail(null);
      return;
    }
    setLoading(true);
    setError("");
    interviewAPI
      .jobInterviews(jobId)
      .then((res) => {
        if (!alive) return;
        setRows(Array.isArray(res?.interviews) ? res.interviews : []);
        setSelectedId(null);
        setDetail(null);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e?.message || "Failed to load interviews");
      })
      .finally(() => {
        if (!alive) return;
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [jobId]);

  useEffect(() => {
    let alive = true;
    if (!selectedId) {
      setDetail(null);
      return;
    }
    setError("");
    interviewAPI
      .interviewDetails(selectedId)
      .then((res) => {
        if (!alive) return;
        setDetail(res?.interview || null);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e?.message || "Failed to load interview details");
      });
    return () => {
      alive = false;
    };
  }, [selectedId]);

  const title = useMemo(() => {
    const j = jobs.find((x) => x.id === jobId);
    return j?.title ? `Interview Sessions — ${j.title}` : "Interview Sessions";
  }, [jobs, jobId]);

  const avatar = (name) => (name ? name.trim().slice(0, 1).toUpperCase() : "?");
  const fmtDt = (iso) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return String(iso);
    }
  };

  return (
    <div>
      <div className="dashboard-card">
        <h2 style={{ fontSize: "20px", fontWeight: 600, marginBottom: "10px", color: "#212529" }}>{title}</h2>
        <p style={{ color: "#6c757d", marginBottom: "18px" }}>View interview invites and candidate readiness.</p>

        <div style={{ display: "flex", gap: "12px", alignItems: "center", marginBottom: "16px" }}>
          <div style={{ color: "#6c757d", fontSize: "14px" }}>Job:</div>
          <select
            value={jobId ?? ""}
            onChange={(e) => {
              const n = Number(e.target.value);
              setJobId(Number.isFinite(n) && n > 0 ? n : null);
            }}
            style={{ padding: "10px 12px", borderRadius: "10px", border: "1px solid #e9ecef", minWidth: "320px" }}
            disabled={loading || jobs.length === 0}
          >
            {jobs.length === 0 ? (
              <option value="">No active jobs</option>
            ) : (
              jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title}
                </option>
              ))
            )}
          </select>
        </div>

        {error && (
          <div
            style={{
              color: "#b91c1c",
              background: "rgba(185,28,28,0.08)",
              border: "1px solid rgba(185,28,28,0.18)",
              borderRadius: "10px",
              padding: "12px",
              marginBottom: "14px",
            }}
          >
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ color: "#6c757d" }}>Loading…</div>
        ) : rows.length === 0 ? (
          <div style={{ color: "#6c757d" }}>No interviews yet for this job.</div>
        ) : (
          <div>
            <div className="comment-list">
              {(Array.isArray(rows) ? rows.filter(Boolean) : []).map((r, idx) => (
                <div key={r?.id ?? `row-${idx}`}>
                  <div
                    className="comment-item"
                    style={{
                      cursor: r?.id ? "pointer" : "default",
                      border: selectedId === r?.id ? "1px solid rgba(59,130,246,0.35)" : undefined,
                      background: selectedId === r?.id ? "rgba(59,130,246,0.06)" : undefined,
                    }}
                    onClick={() => {
                      if (!r?.id) return;
                      setSelectedId(selectedId === r.id ? null : r.id);
                    }}
                  >
                    <div className="comment-avatar">{avatar(r?.candidate?.name)}</div>
                    <div className="comment-content">
                      <div className="comment-header">
                        <span className="comment-author">{r?.candidate?.name || "Candidate"}</span>
                        <span style={{ color: "#6c757d" }}>• Interview</span>
                        <span className="comment-time">{r?.status || ""}</span>
                      </div>
                      <div className="comment-text">Interview invite</div>
                    </div>
                  </div>

                  {selectedId === r.id && detail && (
                    <div
                      style={{
                        border: "1px solid rgba(17, 24, 39, 0.10)",
                        borderRadius: "12px",
                        padding: "14px",
                        background: "#fff",
                        marginLeft: "8px",
                        marginRight: "8px",
                        marginTop: "8px",
                        marginBottom: "8px",
                      }}
                    >
                      <div style={{ fontWeight: 700, color: "#111827", marginBottom: "6px" }}>Interview details</div>
                      <div style={{ color: "#495057", fontSize: "14px", lineHeight: 1.6 }}>
                        <div>
                          Status: <span style={{ fontWeight: 800 }}>{detail?.status || "scheduled"}</span>
                        </div>
                        <div style={{ marginTop: "8px" }}>Scheduled: {fmtDt(detail?.scheduled_at)}</div>
                        <div>Timezone: {detail?.timezone || "—"}</div>
                        <div>Duration: {detail?.duration_minutes ? `${detail.duration_minutes} min` : "—"}</div>
                        <div>Mode: {detail?.mode || "—"}</div>
                        {detail?.meeting_link ? (
                          <div>
                            Meeting link:{" "}
                            <a href={detail.meeting_link} target="_blank" rel="noreferrer">
                              {detail.meeting_link}
                            </a>
                          </div>
                        ) : null}
                        {detail?.location ? <div>Location: {detail.location}</div> : null}
                        {detail?.interviewer_name ? <div>Interviewer: {detail.interviewer_name}</div> : null}
                        {detail?.recruiter_notes ? (
                          <div style={{ marginTop: "10px" }}>
                            <div style={{ fontWeight: 800, color: "#111827" }}>Recruiter notes</div>
                            <div style={{ color: "#495057", whiteSpace: "pre-wrap" }}>{detail.recruiter_notes}</div>
                          </div>
                        ) : null}

                        {detail?.feedback ? (
                          <div style={{ marginTop: "10px" }}>
                            <div style={{ fontWeight: 800, color: "#111827" }}>Feedback</div>
                            <div style={{ color: "#495057", whiteSpace: "pre-wrap" }}>{detail.feedback}</div>
                          </div>
                        ) : null}

                        {detail?.outcome && (
                          <div style={{ marginTop: "10px" }}>
                            <div style={{ fontWeight: 800, color: "#111827" }}>Outcome</div>
                            <div style={{ color: "#495057" }}>
                              <span style={{
                                display: "inline-block",
                                padding: "4px 10px",
                                borderRadius: "6px",
                                background: detail.outcome === "pass" ? "rgba(34,197,94,0.12)" : detail.outcome === "fail" ? "rgba(239,68,68,0.12)" : "rgba(168,85,247,0.12)",
                                color: detail.outcome === "pass" ? "#15803d" : detail.outcome === "fail" ? "#b91c1c" : "#6b21a8",
                                fontWeight: 600,
                                textTransform: "capitalize"
                              }}>
                                {detail.outcome}
                              </span>
                            </div>
                          </div>
                        )}

                        <div style={{ marginTop: "14px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
                          <button
                            type="button"
                            style={{
                              padding: "10px 12px",
                              borderRadius: "10px",
                              border: "1px solid rgba(15,23,42,0.14)",
                              background: "#fff",
                              cursor: "pointer",
                              fontWeight: 800,
                            }}
                            onClick={async () => {
                              try {
                                await interviewAPI.completeInterview(detail.id, { feedback: "" });
                                const rr = await interviewAPI.interviewDetails(detail.id);
                                setDetail(rr?.interview || null);
                                const list = await interviewAPI.jobInterviews(jobId);
                                setRows(Array.isArray(list?.interviews) ? list.interviews : []);
                              } catch (e) {
                                alert(e?.message || "Failed to mark completed");
                              }
                            }}
                          >
                            Mark Completed
                          </button>
                          <button
                            type="button"
                            style={{
                              padding: "10px 12px",
                              borderRadius: "10px",
                              border: "1px solid rgba(59,130,246,0.35)",
                              background: "rgba(59,130,246,0.10)",
                              cursor: "pointer",
                              fontWeight: 900,
                            }}
                            onClick={() => {
                              setEvaluateMode(!evaluateMode);
                              if (!evaluateMode) {
                                setSelectedOutcome(detail?.outcome || "pass");
                                setRemarks("");
                              }
                            }}
                          >
                            {evaluateMode ? "Cancel Evaluation" : "Evaluate Outcome"}
                          </button>
                        </div>

                        {evaluateMode && (
                          <div style={{ marginTop: "14px", padding: "14px", background: "rgba(59,130,246,0.06)", borderRadius: "10px", border: "1px solid rgba(59,130,246,0.2)" }}>
                            <div style={{ fontWeight: 700, color: "#111827", marginBottom: "10px" }}>Select Outcome</div>
                            <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                              {["pass", "fail", "on_hold"].map((opt) => (
                                <button
                                  key={opt}
                                  type="button"
                                  onClick={() => setSelectedOutcome(opt)}
                                  style={{
                                    padding: "8px 12px",
                                    borderRadius: "8px",
                                    border: selectedOutcome === opt ? "2px solid #3b82f6" : "1px solid #d1d5db",
                                    background: selectedOutcome === opt ? "rgba(59,130,246,0.12)" : "#fff",
                                    color: selectedOutcome === opt ? "#1e40af" : "#374151",
                                    fontWeight: selectedOutcome === opt ? 700 : 500,
                                    cursor: "pointer",
                                    textTransform: "uppercase",
                                    fontSize: "12px",
                                  }}
                                >
                                  {opt === "on_hold" ? "On Hold" : opt.charAt(0).toUpperCase() + opt.slice(1)}
                                </button>
                              ))}
                            </div>
                            <label style={{ display: "grid", gap: "6px", fontSize: "13px", color: "#374151", marginBottom: "12px" }}>
                              Remarks (optional)
                              <textarea
                                value={remarks}
                                onChange={(e) => setRemarks(e.target.value)}
                                placeholder="Add feedback about the interview..."
                                rows={3}
                                style={{ padding: "10px 12px", borderRadius: "8px", border: "1px solid #d1d5db", fontFamily: "inherit", fontSize: "13px", resize: "vertical" }}
                              />
                            </label>
                            <div style={{ display: "flex", gap: "10px" }}>
                              <button
                                type="button"
                                onClick={() => setEvaluateMode(false)}
                                style={{
                                  padding: "8px 12px",
                                  borderRadius: "8px",
                                  border: "1px solid #d1d5db",
                                  background: "#fff",
                                  cursor: "pointer",
                                  fontWeight: 600,
                                  fontSize: "13px",
                                }}
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                onClick={async () => {
                                  try {
                                    await interviewAPI.evaluateInterview(detail.id, { outcome: selectedOutcome, remarks });
                                    const rr = await interviewAPI.interviewDetails(detail.id);
                                    setDetail(rr?.interview || null);
                                    const list = await interviewAPI.jobInterviews(jobId);
                                    setRows(Array.isArray(list?.interviews) ? list.interviews : []);
                                    setEvaluateMode(false);
                                  } catch (e) {
                                    alert(e?.message || "Failed to evaluate interview");
                                  }
                                }}
                                style={{
                                  padding: "8px 12px",
                                  borderRadius: "8px",
                                  border: "none",
                                  background: "#3b82f6",
                                  color: "#fff",
                                  cursor: "pointer",
                                  fontWeight: 700,
                                  fontSize: "13px",
                                }}
                              >
                                Save Evaluation
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

