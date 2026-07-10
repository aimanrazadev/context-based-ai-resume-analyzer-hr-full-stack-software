import { useEffect, useMemo, useRef, useState } from "react";
import { jobAPI } from "../utils/api";
import { ErrorState, LoadingState, ScoreRing, SkillPill, StatusBadge } from "./ui";
import "./AppliedJobDetails.css";

export default function AppliedJobDetails({ applicationId, onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const pollRef = useRef(null);
  const [downloading, setDownloading] = useState(false);

  const app = data?.application || null;
  const job = app?.job || null;

  // Determine if analysis is complete by checking score_updated_at
  const isAnalysisComplete = useMemo(() => {
    return !!(app?.score_updated_at);
  }, [app?.score_updated_at]);

  const overallScore = isAnalysisComplete ? Number(app?.final_score ?? 0) : 0;

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
      const res = await jobAPI.applicationDetails(applicationId);
      if (!alive) return null;
      setData(res || null);
      return res || null;
    };

    fetchOnce()
      .then((res) => {
        if (!alive) return;
        // If analysis is still running (apply_save background task), poll briefly.
        const a = res?.application || null;
        const pending = !a?.score_updated_at && !a?.ai_analysis && !a?.ai_explanation;
        if (!pending) return;
        let tries = 0;
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(async () => {
          tries += 1;
          try {
            const rr = await jobAPI.applicationDetails(applicationId);
            if (!alive) return;
            setData(rr || null);
            const aa = rr?.application || null;
            const done = !!aa?.score_updated_at || !!aa?.ai_analysis || !!aa?.ai_explanation;
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

  const analysis = app?.ai_analysis || null;
  const resume = app?.resume || null;
  const resumeName = resume?.original_filename || "Resume";
  const analysisPending = !app?.score_updated_at && !analysis && !app?.ai_explanation;

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
        <div className="ajd-card"><LoadingState message="Loading application…" /></div>
      ) : error ? (
        <div className="ajd-card"><ErrorState message={error} /></div>
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
            <StatusBadge status={app?.status || "submitted"} />
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

          <div style={{ display: "grid", placeItems: "center", marginTop: 24 }}><ScoreRing score={overallScore} size={116} /></div>

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

          {analysis ? (
            <div className="ajd-expl" style={{ display: "grid", gap: 16 }}>
              <div><div className="ajd-expl-title">Candidate summary</div><div className="ajd-expl-text">{analysis.candidate_summary || "—"}</div></div>
              <div><div className="ajd-expl-title">Recommendation</div><div className="ajd-expl-text"><strong>{analysis.recommendation || "Review Manually"}</strong></div></div>
              <div><div className="ajd-expl-title">Reasoning</div><div className="ajd-expl-text">{analysis.reasoning || "—"}</div></div>
              {Array.isArray(analysis.strengths) && analysis.strengths.length > 0 && <div><div className="ajd-expl-title">Strengths</div><div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>{analysis.strengths.map((item) => <SkillPill key={item} tone="positive">{item}</SkillPill>)}</div></div>}
              {Array.isArray(analysis.weaknesses) && analysis.weaknesses.length > 0 && <div><div className="ajd-expl-title">Weaknesses</div><div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>{analysis.weaknesses.map((item) => <SkillPill key={item} tone="negative">{item}</SkillPill>)}</div></div>}
            </div>
          ) : (
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

    </div>
  );
}

