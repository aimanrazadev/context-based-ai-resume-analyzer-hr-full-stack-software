import { useEffect, useMemo, useRef, useState } from "react";
import { Briefcase, GraduationCap, Wrench } from "lucide-react";
import { jobAPI, interviewAPI } from "../utils/api";
import { getRingMetrics, resolveApplicationMatchScore } from "../utils/matchScore";
import "./AppliedJobDetails.css";

export default function AppliedJobDetails({ applicationId, onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const pollRef = useRef(null);
  const [downloading, setDownloading] = useState(false);
  const [interviews, setInterviews] = useState([]);
  const [interviewsLoading, setInterviewsLoading] = useState(false);

  const app = data?.application || null;
  const job = app?.job || null;

  // Determine if analysis is complete by checking score_updated_at
  const isAnalysisComplete = useMemo(() => {
    return !!(app?.score_updated_at);
  }, [app?.score_updated_at]);

  const overallScore = useMemo(() => {
    if (!isAnalysisComplete) return 0;
    return resolveApplicationMatchScore(app);
  }, [app, isAnalysisComplete]);

  const overallRing = useMemo(() => getRingMetrics(overallScore, 46), [overallScore]);

  useEffect(() => {
    let alive = true;
    if (!applicationId) {
      setLoading(false);
      setError("Missing application id");
      return;
    }
    setLoading(true);
    setError("");
    setData(null);

    const fetchOnce = async () => {
      // Shared endpoint works for both candidate + recruiter.
      // If the backend is older, fallback to candidate-only endpoint.
      try {
        const shared = await jobAPI.applicationDetailsShared(applicationId);
        if (!alive) return null;
        setData(shared || null);
        // attempt to fetch interview details for this application (candidate view)
        try {
          setInterviewsLoading(true);
          const im = await interviewAPI.myInterviews();
          const items = im?.interviews || [];
          const ours = items.filter((x) => Number(x.application_id) === Number(applicationId));
          // fetch full details for each interview to surface feedback/outcome
          const details = await Promise.all(
            (ours || []).map(async (it) => {
              try {
                const r = await interviewAPI.interviewDetails(it.id);
                return r?.interview || null;
              } catch {
                return null;
              }
            })
          );
          setInterviews((details || []).filter(Boolean));
        } catch {
          // ignore if not candidate or API fails
        } finally {
          setInterviewsLoading(false);
        }
        return shared || null;
      } catch {
        const res = await jobAPI.applicationDetails(applicationId);
        if (!alive) return null;
        setData(res || null);
        return res || null;
      }
    };

    fetchOnce()
      .then((res) => {
        if (!alive) return;
        // If analysis is still running (apply_save background task), poll briefly.
        const a = res?.application || null;
        const pending = !a?.score_updated_at && !a?.ai_sections && !a?.ai_explanation;
        if (!pending) return;
        let tries = 0;
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(async () => {
          tries += 1;
          try {
            let rr = null;
            try {
              rr = await jobAPI.applicationDetailsShared(applicationId);
            } catch {
              rr = await jobAPI.applicationDetails(applicationId);
            }
            if (!alive) return;
            setData(rr || null);
            const aa = rr?.application || null;
            const done = !!aa?.score_updated_at || !!aa?.ai_sections || !!aa?.ai_explanation;
            if (done || tries >= 25) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
          } catch {
            // ignore transient polling errors
            if (tries >= 25 && pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
          }
        }, 1200);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e?.message || "Failed to load application");
      })
      .finally(() => {
        if (!alive) return;
        setLoading(false);
      });
    return () => {
      alive = false;
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [applicationId]);

  const sections = app?.ai_sections || null;
  const resume = app?.resume || null;
  const resumeName = resume?.original_filename || "Resume";
  const analysisPending = !app?.score_updated_at && !sections && !app?.ai_explanation;

  const downloadResume = async () => {
    if (!applicationId || downloading) return;
    setDownloading(true);
    try {
      const blob = await jobAPI.downloadApplicationResume(applicationId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = resumeName || "resume";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (e) {
      alert(e?.message || "Failed to download resume");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="ajd-wrap">
      <button type="button" className="ajd-back" onClick={() => onBack?.()}>
        ← Back to applied jobs
      </button>

      {loading ? (
        <div className="ajd-card">Loading…</div>
      ) : error ? (
        <div className="ajd-card ajd-error">{error}</div>
      ) : (
        <div className="ajd-card">
          <div className="ajd-head">
            <div className="ajd-title">{job?.title || "Job"}</div>
            <div className="ajd-sub">{job?.location || ""}</div>
          </div>

          {/* Candidate Information Section */}
          {app?.candidate && (
            <div className="ajd-candidate-info">
              <div className="ajd-expl-title">Candidate Information</div>
              <div className="candidate-details">
                <div className="candidate-name-section">
                  <h4>{app.candidate.name || "Candidate"}</h4>
                  <p>{app.candidate.email || "—"}</p>
                </div>

                {/* Social Links */}
                {(app.candidate.linkedin || app.candidate.github) && (
                  <div className="candidate-socials">
                    <div className="socials-title">Social Links</div>
                    <div className="social-links">
                      {app.candidate.linkedin && (
                        <a href={app.candidate.linkedin} target="_blank" rel="noopener noreferrer" className="social-link linkedin">
                          <span className="social-icon">in</span>
                          <span>LinkedIn</span>
                        </a>
                      )}
                      {app.candidate.github && (
                        <a href={app.candidate.github} target="_blank" rel="noopener noreferrer" className="social-link github">
                          <span className="social-icon">⚙</span>
                          <span>GitHub</span>
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="ajd-note">
            <div className="ajd-note-title">Application submitted</div>
            <div className="ajd-note-text">
              Your resume has been saved. <span className="ajd-muted">Waiting for recruiter to review it.</span>
            </div>
          </div>

          {applicationId && (
            <div className="ajd-resume">
              <div className="ajd-expl-title">Your resume</div>
              <div
                className={`ajd-resume-row ${downloading ? "is-downloading" : ""}`}
                role="button"
                tabIndex={0}
                aria-label="Download resume"
                onClick={downloadResume}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    downloadResume();
                  }
                }}
              >
                <div className="ajd-resume-name">{resumeName}</div>
                <div className="ajd-resume-hint">{downloading ? "Downloading…" : "Click to download"}</div>
              </div>
            </div>
          )}

          <div className="ajd-score" aria-label={`Match score ${overallRing.score}%`}>
            <svg className="ajd-score-svg" viewBox="0 0 112 112" role="img" aria-hidden="true">
              <defs>
                <linearGradient id="ajd-grad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor={isAnalysisComplete ? "#10b981" : "#f59e0b"} />
                  <stop offset="100%" stopColor={isAnalysisComplete ? "#059669" : "#d97706"} />
                </linearGradient>
              </defs>
              <circle
                className="ajd-score-track"
                cx="56"
                cy="56"
                r={overallRing.radius}
                fill="none"
                stroke="rgba(15, 23, 42, 0.12)"
                strokeWidth="10"
              />
              <circle
                className="ajd-score-arc"
                cx="56"
                cy="56"
                r={overallRing.radius}
                fill="none"
                stroke="url(#ajd-grad)"
                strokeWidth="10"
                strokeLinecap="round"
                strokeDasharray={overallRing.strokeDasharray}
                strokeDashoffset={overallRing.strokeDashoffset}
                transform="rotate(-90 56 56)"
              />
            </svg>
            <div className="ajd-score-inner" aria-hidden="true">
              <div className="ajd-score-num">{overallRing.score}</div>
              <div className="ajd-score-unit">%</div>
            </div>
          </div>

          <div className="ajd-score-sub">Overall Match</div>

          {analysisPending && (
            <div className="ajd-pending">
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div
                  style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    background: "#f59e0b",
                    animation: "pulse 2s infinite",
                  }}
                />
                Analyzing your resume… this page will update automatically.
              </div>
            </div>
          )}

          {sections && (
            <div className="ajd-sections">
              {[
                { key: "education_summary", title: "Education Match", Icon: GraduationCap },
                { key: "projects_summary", title: "Projects Match", Icon: Wrench },
                { key: "work_experience_summary", title: "Work Experience Match", Icon: Briefcase }
              ].map((c) => {
                const s = sections?.[c.key] || {};
                const sc = typeof s.score === "number" ? s.score : 0;
                const sum = (s.summary || "").trim();
                const Icon = c.Icon;
                const getTone = (score) => {
                  if (score >= 80) return "tone-green";
                  if (score >= 60) return "tone-lgreen";
                  if (score >= 40) return "tone-yellow";
                  if (score >= 20) return "tone-orange";
                  return "tone-red";
                };
                return (
                  <div key={c.key} className={`ajd-sec ${getTone(sc)}`}>
                    <div className="ajd-sec-top">
                      <div className="ajd-sec-title">
                        <Icon className="ajd-sec-icon" aria-hidden="true" />
                        {c.title}
                      </div>
                    </div>
                    <div className="ajd-sec-text">{sum || "—"}</div>
                  </div>
                );
              })}
            </div>
          )}

          {!sections && (
            <div className="ajd-expl">
              <div className="ajd-expl-title">Explanation</div>
              <div className="ajd-expl-text">{app?.ai_explanation || "—"}</div>
            </div>
          )}

          <div className="ajd-job">
            <div className="ajd-expl-title">Job description</div>
            <div className="ajd-expl-text">{job?.description || "—"}</div>
          </div>
        </div>
      )}

      {/* Interview Feedback Section - Separate Container */}
      {!loading && !error && (
        <div className="ajd-feedback-card">
          <div className="ajd-expl-title">Interview Feedback</div>
          {interviewsLoading ? (
            <div className="ajd-note-text">Loading feedback…</div>
          ) : interviews.length === 0 ? (
            <div className="ajd-note-text ajd-muted">No feedback yet.</div>
          ) : (
            interviews.map((it) => (
              <div key={it.id} className="ajd-feedback-item">
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <div>
                    <strong>{(it.job && it.job.title) || "Interview"}</strong>
                    <div className="ajd-muted">Status: {it.status || "—"}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    {it.outcome && <div className="ajd-badge">{it.outcome}</div>}
                    <div className="ajd-muted">{it.scheduled_at ? new Date(it.scheduled_at).toLocaleString() : ""}</div>
                  </div>
                </div>
                {it.recruiter_notes && (
                  <div className="ajd-note" style={{ marginTop: 8 }}>
                    <div className="ajd-note-title">Recruiter notes</div>
                    <div className="ajd-note-text">{it.recruiter_notes}</div>
                  </div>
                )}
                {it.feedback && (
                  <div className="ajd-note" style={{ marginTop: 8 }}>
                    <div className="ajd-note-title">Feedback</div>
                    <div className="ajd-note-text">{it.feedback}</div>
                  </div>
                )}
                <div style={{ marginTop: 6 }} className="ajd-muted">
                  {it.evaluated_at ? `Evaluated: ${new Date(it.evaluated_at).toLocaleString()}` : it.completed_at ? `Completed: ${new Date(it.completed_at).toLocaleString()}` : ""}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

