import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Briefcase,
  Calendar,
  DollarSign,
  GraduationCap,
  MapPin,
} from "lucide-react";
import { jobAPI } from "../utils/api";
import { getRingMetrics } from "../utils/matchScore";
import { ScoreRing, SkillPill } from "./ui";
import "./JobDetailModal.css";

function getStoredRole() {
  try {
    const raw = localStorage.getItem("user");
    const u = raw ? JSON.parse(raw) : null;
    return u?.role || u?.userType || null;
  } catch {
    return null;
  }
}

function cleanScanError(message) {
  const text = String(message || "").trim();
  if (!text) return "Analysis failed. Please try again.";
  const lower = text.toLowerCase();
  if (
    lower.includes("generativelanguage.googleapis.com") ||
    lower.includes("access_token_type_unsupported") ||
    lower.includes("unauthenticated") ||
    lower.includes("gemini") ||
    lower.includes('"error"')
  ) {
    return "AI explanation could not be generated. The match score is still available.";
  }
  return text;
}

export default function JobDetailModal({ jobId, onClose, onContinueDraft, onApplied }) {
  const navigate = useNavigate();
  const role = useMemo(() => getStoredRole(), []);
  const canEdit = role === "recruiter";
  const isCandidate = role === "candidate";

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const isDraft = canEdit && job?.status === "draft";

  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    title: "",
    description: "",
    location: "",
    salary_range: ""
  });

  // Candidate: resume upload & analysis (per job application)
  const resumeInputRef = useRef(null);
  const pollRef = useRef(null);
  const uploadModeRef = useRef("apply"); // 'scan' | 'apply'
  const cachedFileRef = useRef(null);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState("");
  const [applyResult, setApplyResult] = useState(null);
  const [existingApplication, setExistingApplication] = useState(null);
  const [checkingApplication, setCheckingApplication] = useState(false);
  const [progress, setProgress] = useState({ active: false, percent: 0, message: "", taskId: null });
  const [scanTaskId, setScanTaskId] = useState(null);
  const rafRef = useRef(null);
  const [displayPct, setDisplayPct] = useState(0);
  const alreadyApplied = Boolean(existingApplication?.id);
  const canApplyAfterScan = Boolean(applyResult && scanTaskId && !progress.active && !applying && !checkingApplication);

  const jobTags = useMemo(() => {
    // Use required_skills from job data if available
    if (job?.required_skills && Array.isArray(job.required_skills) && job.required_skills.length > 0) {
      return job.required_skills;
    }
    return [];
  }, [job?.required_skills]);

  const detailCards = useMemo(() => {
    if (!job) return [];
    return [
      {
        label: "Location",
        value: isEditing ? null : (job.location || "Not specified"),
        icon: MapPin,
        editor: (
          <input
            value={form.location}
            onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))}
            placeholder="Location"
          />
        ),
      },
      {
        label: "Salary",
        value: isEditing ? null : (job.salary_range || "Not specified"),
        icon: DollarSign,
        editor: (
          <input
            value={form.salary_range}
            onChange={(e) => setForm((p) => ({ ...p, salary_range: e.target.value }))}
            placeholder="Salary range"
          />
        ),
      },
      {
        label: "Date & Time",
        value: job.created_at ? new Date(job.created_at).toLocaleString() : "Not specified",
        icon: Calendar,
      },
      {
        label: "Opportunity Type",
        value: job.opportunity_type || "Not specified",
        icon: Briefcase,
      },
      {
        label: "Job Type",
        value: job.job_type || "Not specified",
        icon: Briefcase,
      },
      {
        label: "Job Site",
        value: job.job_site || "Not specified",
        icon: MapPin,
      },
      {
        label: "Min Experience",
        value: job.min_experience_years != null ? `${job.min_experience_years} years` : "Not specified",
        icon: GraduationCap,
      },
    ];
  }, [form.location, form.salary_range, isEditing, job]);

  const bullets = useMemo(() => {
    const raw = String(job?.description || "").trim();
    if (!raw) return [];
    const lines = raw
      .split(/\r?\n+/)
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length >= 3) return lines.slice(0, 24);

    return raw
      .split(/(?<=[.!?])\s+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 18);
  }, [job?.description]);

  const briefify = (text) => {
    const t = String(text || "").trim();
    if (!t) return "—";
    // Keep it brief: prefer the first 1–2 sentences; fallback to a safe length.
    const parts = t.split(/(?<=[.!?])\s+/).filter(Boolean);
    const short = parts.slice(0, 2).join(" ");
    const out = short || t;
    return out.length > 320 ? `${out.slice(0, 320).trim()}…` : out;
  };

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    setApplyError("");
    setApplyResult(null);
    setScanTaskId(null);
    setExistingApplication(null);
    setCheckingApplication(false);
    setProgress({ active: false, percent: 0, message: "", taskId: null });
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    jobAPI
      .getById(jobId)
      .then((res) => {
        if (!alive) return;
        const j = res?.job;
        setJob(j);
        setForm({
          title: j?.title ?? "",
          description: j?.description ?? "",
          location: j?.location ?? "",
          salary_range: j?.salary_range ?? ""
        });

        if (isCandidate) {
          setCheckingApplication(true);
          jobAPI
            .myApplicationForJob(jobId)
            .then((appRes) => {
              if (!alive) return;
              if (appRes?.already_applied && appRes?.application) {
                setExistingApplication(appRes.application);
              } else {
                setExistingApplication(null);
              }
            })
            .catch(() => {
              if (!alive) return;
              setExistingApplication(null);
            })
            .finally(() => {
              if (!alive) return;
              setCheckingApplication(false);
            });
        }
      })
      .catch((e) => {
        if (!alive) return;
        setError(e?.message || "Failed to load job");
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
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      cachedFileRef.current = null;
      setScanTaskId(null);
    };
  }, [jobId, isCandidate]);

  // Animate ring fill + number counting whenever we receive a new result.
  useEffect(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    const t = Number(applyResult?.final_score ?? 0);
    const start = performance.now();
    const duration = 900; // ms
    const from = 0;

    const tick = (now) => {
      const k = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - k, 3); // easeOutCubic
      const val = Math.round(from + (t - from) * eased);
      setDisplayPct(val);
      if (k < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        rafRef.current = null;
      }
    };

    setDisplayPct(0);
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [applyResult]);

  const startPoll = (taskId) => {
    const poll = async () => {
      const st = await jobAPI.applyStatus(taskId);
      const t = st?.task;
      if (!t) return;
      const pct = typeof t.percent === "number" ? t.percent : 0;
      const msg = t.message || "Analyzing…";
      const status = t.status;

      if (status === "done") {
        setApplyResult(t.result || null);
        setScanTaskId(taskId);
        setProgress({ active: false, percent: 100, message: "Done", taskId: null });
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        return;
      }
      if (status === "error") {
        setApplyError(cleanScanError(t.error || msg || "Analysis failed"));
        setApplyResult(null);
        setScanTaskId(null);
        setProgress({ active: false, percent: pct, message: msg, taskId: null });
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        return;
      }

      setProgress({ active: true, percent: pct, message: msg, taskId });
    };

    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => {
      poll().catch((err) => {
        setApplyError(cleanScanError(err?.message || "Failed to fetch progress"));
        setApplyResult(null);
        setScanTaskId(null);
        setProgress({ active: false, percent: 0, message: "", taskId: null });
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      });
    }, 800);
    return poll();
  };

  const runScan = async (file) => {
    setApplyError("");
    setApplyResult(null);
    setScanTaskId(null);
    setApplying(true);
    setProgress({ active: true, percent: 1, message: "Uploading resume for scan…", taskId: null });
    try {
      cachedFileRef.current = file;
      const start = await jobAPI.scanResumeAsync(jobId, file);
      const taskId = start?.task_id || null;
      if (!taskId) throw new Error("Failed to start scan");
      setProgress({ active: true, percent: 3, message: "Scanning resume…", taskId });
      setApplying(false);
      await startPoll(taskId);
    } catch (e) {
      setApplyError(cleanScanError(e?.message || "Failed to scan resume"));
      setProgress({ active: false, percent: 0, message: "", taskId: null });
    } finally {
      setApplying(false);
    }
  };

  const runApply = async () => {
    // Apply now saves the exact completed scan result. No second scoring pass runs here.
    setApplyError("");
    setApplying(true);
    setProgress({ active: false, percent: 0, message: "", taskId: null });
    try {
      if (!scanTaskId) {
        throw new Error("Please scan your resume first. You can apply after the match score is generated.");
      }
      const res = await jobAPI.applyFromScan(jobId, scanTaskId);
      if (res?.already_applied) {
        if (res?.application) setExistingApplication(res.application);
        setApplyError("Already applied to this job.");
        return;
      }
      if (res?.application) {
        setExistingApplication(res.application);
      }
      cachedFileRef.current = null;
      setScanTaskId(null);
      setApplyResult(null);
      onApplied?.();
    } catch (e) {
      setApplyError(e?.message || "Failed to apply");
      setApplyResult(null);
      setProgress({ active: false, percent: 0, message: "", taskId: null });
    } finally {
      setApplying(false);
    }
  };

  const handleSave = async () => {
    setError("");
    setSaving(true);
    try {
      const res = await jobAPI.update(jobId, {
        title: form.title,
        description: form.description,
        location: form.location,
        salary_range: form.salary_range
      });
      setJob(res?.job || null);
      setIsEditing(false);
    } catch (e) {
      setError(e?.message || "Failed to save changes");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("Delete this job?")) return;
    setError("");
    setSaving(true);
    try {
      await jobAPI.delete(jobId);
      onClose?.();
    } catch (e) {
      setError(e?.message || "Failed to delete job");
    } finally {
      setSaving(false);
    }
  };

  const handleBack = () => {
    // Preferred: let the parent close the modal (RecruiterApp / CandidateApp).
    if (typeof onClose === "function") {
      onClose();
      return;
    }

    // Fallback: try browser history.
    if (typeof window !== "undefined" && window.history?.length > 1) {
      navigate(-1);
      return;
    }

    // Last resort: route to role home.
    navigate(role === "candidate" ? "/candidate" : "/recruiter", { replace: true });
  };

  return (
    <div className="job-detail-overlay" role="dialog" aria-modal="true">
      <div className="job-detail-page">
        <button
          type="button"
          className="job-detail-back"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            handleBack();
          }}
        >
          <span>←</span> Back
        </button>

        {/* Candidate view (single-card Internshala-like layout) */}
        {isCandidate && !isEditing ? (
          <>
            {loading ? (
              <div className="jd-card jd-loading">Loading…</div>
            ) : error ? (
              <div className="jd-card jd-main-card">
                <div className="job-detail-error">{error}</div>
              </div>
            ) : (
              <>
                <div className="jd-page-title">{job?.title || "Job Details"}</div>

                <div className="jd-card jd-main-card">
                  {(() => {
                    const opp = String(job?.opportunity_type || "").toLowerCase();
                    const jt = String(job?.job_type || "").toLowerCase();
                    const isInternship = opp === "internship" || jt.includes("intern");
                    const stipendLabel = isInternship ? "STIPEND" : "CTC";
                    return (
                      <>
                  <div className="jd-top">
                    <div className="jd-top-left">
                      <div className="jd-badge-row">
                        <span className="jd-badge">Actively hiring</span>
                        {isInternship && <span className="jd-pill-internship">Internship</span>}
                      </div>
                      <div className="jd-role">{job?.short_description || job?.title || "Role"}</div>
                      <div className="jd-company">{job?.location || "Location not specified"}</div>
                      <div className="jd-subline">
                        <div className="jd-subline-text">
                          {job?.created_at ? `Posted ${new Date(job.created_at).toLocaleDateString()}` : ""}
                        </div>
                        <div className="jd-posted-chip">
                          <span className="jd-chip success">Posted recently</span>
                        </div>
                      </div>
                    </div>

                    <div className="jd-top-right">
                      <div className="jd-brand" aria-hidden="true">
                        {(job?.title || "J").slice(0, 1).toUpperCase()}
                      </div>
                    </div>
                  </div>

                  <div className="jd-facts">
                    <div className="jd-fact">
                      <div className="jd-fact-k">{stipendLabel}</div>
                      <div className="jd-fact-v">{job?.salary_range || "—"}</div>
                    </div>
                    <div className="jd-fact">
                      <div className="jd-fact-k">APPLY BY</div>
                      <div className="jd-fact-v">
                        {job?.apply_by 
                          ? new Date(job.apply_by).toLocaleDateString('en-US', { 
                              year: 'numeric', 
                              month: 'short', 
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit'
                            })
                          : "—"}
                      </div>
                    </div>
                  </div>

                  <div className="jd-detail-grid">
                    <div className="jd-detail-item">
                      <div className="jd-detail-k">Job type</div>
                      <div className="jd-detail-v">{job?.job_type || "—"}</div>
                    </div>
                    <div className="jd-detail-item">
                      <div className="jd-detail-k">Job site</div>
                      <div className="jd-detail-v">{job?.job_site || "—"}</div>
                    </div>
                    <div className="jd-detail-item">
                      <div className="jd-detail-k">Min experience</div>
                      <div className="jd-detail-v">
                        {job?.min_experience_years != null ? `${job.min_experience_years} years` : "—"}
                      </div>
                    </div>
                  </div>
                      </>
                    );
                  })()}

                  <div className="jd-actions-row">
                    <div className="jd-actions-right">
                      <input
                        ref={resumeInputRef}
                        type="file"
                        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        style={{ display: "none" }}
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          try {
                            if (uploadModeRef.current === "scan") {
                              await runScan(file);
                            } else {
                              await runApply();
                            }
                          } catch (err) {
                            setApplyError(err?.message || "Failed to apply");
                            // Avoid showing stale results when the request fails/timeouts.
                            setApplyResult(null);
                            setProgress({ active: false, percent: 0, message: "", taskId: null });
                          } finally {
                            setApplying(false);
                            e.target.value = "";
                          }
                        }}
                      />

                      {alreadyApplied ? (
                        <div className="jd-applied-state">
                          <span className="jd-chip success">Already Applied</span>
                          <button
                            type="button"
                            className="jd-scan"
                            onClick={() => navigate(`/applications/${existingApplication.id}`)}
                          >
                            View Application
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="jd-scan"
                            onClick={() => {
                              uploadModeRef.current = "scan";
                              resumeInputRef.current?.click();
                            }}
                            disabled={applying || checkingApplication}
                          >
                            Scan resume
                          </button>

                          <button
                            type="button"
                            className="jd-apply"
                            onClick={async () => {
                              if (!canApplyAfterScan) {
                                setApplyError("Please scan your resume first. You can apply after the match score is generated.");
                                return;
                              }
                              // Apply now: persist the completed scan result only.
                              uploadModeRef.current = "apply";
                              await runApply();
                            }}
                            disabled={!canApplyAfterScan}
                            title={
                              canApplyAfterScan
                                ? "Apply with the scanned resume"
                                : "Scan your resume first to generate a match score"
                            }
                          >
                            {applying ? "Working..." : "Apply now"}
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="jd-upload-note-inline">Upload PDF/DOCX — resume is tied to this job application only.</div>

                  {applyError && <div className="jd-alert">{applyError}</div>}

                  {progress.active && (
                    <div className="jd-progress" aria-live="polite">
                      <div className="jd-progress-head">
                        <div className="jd-progress-msg">
                          <span className="jd-spinner" aria-hidden="true" />
                          Calculating your match score…
                        </div>
                        <div className="jd-progress-pct">{Math.max(0, Math.min(100, progress.percent || 0))}%</div>
                      </div>
                      <div className="jd-progress-bar">
                        <div
                          className="jd-progress-fill"
                          style={{ width: `${Math.max(0, Math.min(100, progress.percent || 0))}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {applyResult && (
                    (() => {
                      const ring = getRingMetrics(displayPct || 0, 46);
                      return (
                        <div className={`jd-result ${applyResult.ai_error ? "error" : ""}`}>
                          <div className="jd-result-label">Match Score</div>

                          <ScoreRing score={ring.score} size={112} />

                          <div className="jd-score-ring-sub">Overall Match</div>

                          {applyResult.ai_error ? (
                            <div className="jd-result-text jd-result-text-error">
                              {cleanScanError(applyResult.ai_error?.message)}
                            </div>
                          ) : applyResult.ai_analysis ? (
                            <div className="jd-summary-cards" style={{ gridTemplateColumns: "1fr" }}>
                              <div className="jd-summary-card">
                                <div className="jd-summary-card-title">{applyResult.ai_analysis.recommendation || "Review Manually"}</div>
                                <div className="jd-summary-text">{applyResult.ai_analysis.candidate_summary || "—"}</div>
                                <div className="jd-summary-text"><strong>Reasoning:</strong> {applyResult.ai_analysis.reasoning || "—"}</div>
                                {Array.isArray(applyResult.ai_analysis.strengths) && applyResult.ai_analysis.strengths.length > 0 && (
                                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                                    {applyResult.ai_analysis.strengths.map((item) => <SkillPill key={item} tone="positive">{item}</SkillPill>)}
                                  </div>
                                )}
                              </div>
                            </div>
                          ) : (
                            <div className="jd-result-text">{briefify(applyResult.ai_explanation)}</div>
                          )}
                        </div>
                      );
                    })()
                  )}

                  <div className="jd-section">
                    <div className="jd-section-h">About the job</div>
                    {bullets.length ? (
                      <ol className="jd-list">
                        {bullets.slice(0, 18).map((b, idx) => (
                          <li key={idx}>{b}</li>
                        ))}
                      </ol>
                    ) : (
                      <div className="jd-muted">No description provided.</div>
                    )}
                  </div>

                  <div className="jd-section">
                    <div className="jd-section-h">Skill(s) required</div>
                    {jobTags.length > 0 ? (
                      <div className="jd-tags">
                        {jobTags.map((t) => (
                          <span key={t} className="jd-pill">
                            {t}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <div className="jd-muted">No specific skills specified by recruiter</div>
                    )}
                  </div>

                </div>
              </>
            )}
          </>
        ) : (
          /* Recruiter + editing view (keep existing UI) */
          <div className="job-detail-card">
            {loading ? (
              <div className="job-detail-loading">Loading…</div>
            ) : error ? (
              <div className="job-detail-error">{error}</div>
            ) : (
              <>
                <div className="job-detail-header">
                  <div className="job-detail-title-group">
                    {!isEditing && (
                      <div className="job-detail-avatar" aria-hidden="true">
                        {(job?.title || "J").trim().charAt(0).toUpperCase()}
                      </div>
                    )}
                    {isEditing ? (
                      <input
                        className="job-detail-title-input"
                        value={form.title}
                        onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                        placeholder="Job title"
                      />
                    ) : (
                      <h2 className="job-detail-title">{job?.title}</h2>
                    )}
                  </div>

                  {canEdit && (
                    <div className="job-detail-actions">
                      {isEditing ? (
                        <>
                          <button
                            type="button"
                            className="job-detail-btn secondary"
                            onClick={() => {
                              setIsEditing(false);
                              setForm({
                                title: job?.title ?? "",
                                description: job?.description ?? "",
                                location: job?.location ?? "",
                                salary_range: job?.salary_range ?? ""
                              });
                            }}
                            disabled={saving}
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            className="job-detail-btn primary"
                            onClick={handleSave}
                            disabled={saving}
                          >
                            {saving ? "Saving..." : "Save"}
                          </button>
                        </>
                      ) : (
                        <>
                          {isDraft && typeof onContinueDraft === "function" && (
                            <button
                              type="button"
                              className="job-detail-btn primary"
                              onClick={() => onContinueDraft(job)}
                            >
                              Continue editing
                            </button>
                          )}
                          <button
                            type="button"
                            className="job-detail-btn secondary"
                            onClick={() => setIsEditing(true)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="job-detail-btn danger"
                            onClick={handleDelete}
                            disabled={saving}
                          >
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>

                <div className="job-detail-info-grid">
                  {detailCards.map((item) => {
                    const Icon = item.icon;
                    return (
                      <div className="job-detail-info-card" key={item.label}>
                        <div className="job-detail-info-icon">
                          <Icon aria-hidden="true" />
                        </div>
                        <div className="job-detail-info-body">
                          <div className="job-detail-info-label">{item.label}</div>
                          <div className="job-detail-info-value">
                            {item.editor && isEditing ? item.editor : item.value}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="job-detail-section">
                  <h3>Description</h3>
                  {isEditing ? (
                    <textarea
                      value={form.description}
                      onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                      rows={10}
                    />
                  ) : (
                    <p className="job-detail-desc">{job?.description || "No description provided."}</p>
                  )}
                </div>

                <div className="job-detail-section">
                  <h3>Non-negotiables</h3>
                  {Array.isArray(job?.non_negotiables) && job.non_negotiables.length > 0 ? (
                    <ul className="job-detail-list">
                      {job.non_negotiables.map((item, idx) => (
                        <li key={`${item}-${idx}`}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="job-detail-desc">No non-negotiables provided.</p>
                  )}
                </div>

                <div className="job-detail-section">
                  <h3>Required Skills</h3>
                  <p className="job-detail-desc job-detail-help">
                    These exact skills are used for resume matching and the green/red skill snapshot.
                  </p>
                  {Array.isArray(job?.required_skills) && job.required_skills.length > 0 ? (
                    <div className="job-detail-skill-list" aria-label="Required skills used for matching">
                      {job.required_skills.map((skill, idx) => (
                        <span key={`${skill}-${idx}`} className="job-detail-skill-pill">
                          {skill}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="job-detail-desc">No required skills provided.</p>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

