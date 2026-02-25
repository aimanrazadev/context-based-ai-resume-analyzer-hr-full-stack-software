import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bookmark,
  BookmarkCheck,
  Briefcase,
  Calendar,
  CalendarClock,
  DollarSign,
  GraduationCap,
  Link2,
  MapPin,
  Phone,
  Users,
  Wrench
} from "lucide-react";
import { jobAPI } from "../utils/api";
import { getRingMetrics, resolveApplicationMatchScore } from "../utils/matchScore";
import "./JobDetailModal.css";

const SAVED_JOBS_KEY = "savedJobs";

function getStoredRole() {
  try {
    const raw = localStorage.getItem("user");
    const u = raw ? JSON.parse(raw) : null;
    return u?.role || u?.userType || null;
  } catch {
    return null;
  }
}

export default function JobDetailModal({ jobId, onClose, onContinueDraft, onApplied }) {
  const navigate = useNavigate();
  const role = useMemo(() => getStoredRole(), []);
  const canEdit = role === "recruiter";
  const isCandidate = role === "candidate";

  const [isSaved, setIsSaved] = useState(false);

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
    salary_range: "",
    job_link: ""
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
  const rafRef = useRef(null);
  const [displayPct, setDisplayPct] = useState(0);
  const alreadyApplied = Boolean(existingApplication?.id);

  const jobTags = useMemo(() => {
    // Use required_skills from job data if available
    if (job?.required_skills && Array.isArray(job.required_skills) && job.required_skills.length > 0) {
      return job.required_skills;
    }
    return [];
  }, [job?.required_skills]);

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

  const perkLabels = {
    joinerBonus: "Joining bonus",
    relocation: "Relocation bonus",
    insurance: "Health insurance",
    pf: "PF",
  };

  const perksList = useMemo(() => {
    const perks = job?.perks && typeof job.perks === "object" ? job.perks : null;
    if (!perks) return [];
    return Object.entries(perks)
      .filter(([, v]) => Boolean(v))
      .map(([k]) => perkLabels[k] || k);
  }, [job?.perks]);

  const scoreVisualFromPct = (pct) => {
    const p = Math.max(0, Math.min(100, Number.isFinite(pct) ? Math.round(pct) : 0));
    // 5-band palette with a slight "gradient-ish" feel via two close tones.
    if (p >= 90) return { pct: p, a: "#22c55e", b: "#16a34a" }; // green
    if (p >= 70) return { pct: p, a: "#7ddc6f", b: "#34d399" }; // light green
    if (p >= 50) return { pct: p, a: "#facc15", b: "#fde047" }; // yellow
    if (p >= 30) return { pct: p, a: "#fb923c", b: "#f97316" }; // orange
    return { pct: p, a: "#fb7185", b: "#ef4444" }; // red/pink-ish
  };

  const briefify = (text) => {
    const t = String(text || "").trim();
    if (!t) return "—";
    // Keep it brief: prefer the first 1–2 sentences; fallback to a safe length.
    const parts = t.split(/(?<=[.!?])\s+/).filter(Boolean);
    const short = parts.slice(0, 2).join(" ");
    const out = short || t;
    return out.length > 320 ? `${out.slice(0, 320).trim()}…` : out;
  };

  const toneFromPct = (pct) => {
    const p = Math.max(0, Math.min(100, Number.isFinite(pct) ? Math.round(pct) : 0));
    if (p >= 90) return "tone-green";
    if (p >= 70) return "tone-lgreen";
    if (p >= 50) return "tone-yellow";
    if (p >= 30) return "tone-orange";
    return "tone-red";
  };

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    setApplyError("");
    setApplyResult(null);
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
          salary_range: j?.salary_range ?? "",
          job_link: j?.job_link ?? ""
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
    };
  }, [jobId]);

  // Animate ring fill + number counting whenever we receive a new result.
  useEffect(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    const t = resolveApplicationMatchScore(applyResult);
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
        setProgress({ active: false, percent: 100, message: "Done", taskId: null });
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        return;
      }
      if (status === "error") {
        setApplyError(t.error || msg || "Analysis failed");
        setApplyResult(null);
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
        setApplyError(err?.message || "Failed to fetch progress");
        setApplyResult(null);
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
      setApplyError(e?.message || "Failed to scan resume");
      setProgress({ active: false, percent: 0, message: "", taskId: null });
    } finally {
      setApplying(false);
    }
  };

  const runApply = async (file) => {
    // Apply now should ONLY save the application (no scoring). After saving, navigate to Applied Jobs.
    setApplyError("");
    setApplying(true);
    setProgress({ active: false, percent: 0, message: "", taskId: null });
    try {
      if (!file) {
        throw new Error("Please upload a resume to apply.");
      }
      const res = await jobAPI.applySaveOnly(jobId, file);
      if (res?.already_applied) {
        if (res?.application) setExistingApplication(res.application);
        setApplyError("Already applied to this job.");
        return;
      }
      if (res?.application) {
        setExistingApplication(res.application);
      }
      cachedFileRef.current = null;
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
        salary_range: form.salary_range,
        job_link: form.job_link
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

  useEffect(() => {
    if (!jobId) return;
    try {
      const raw = localStorage.getItem(SAVED_JOBS_KEY);
      const ids = raw ? JSON.parse(raw) : [];
      setIsSaved(Array.isArray(ids) && ids.includes(jobId));
    } catch {
      setIsSaved(false);
    }
  }, [jobId]);

  const toggleSaved = () => {
    if (!jobId) return;
    try {
      const raw = localStorage.getItem(SAVED_JOBS_KEY);
      const ids = raw ? JSON.parse(raw) : [];
      const list = Array.isArray(ids) ? ids : [];
      const next = list.includes(jobId)
        ? list.filter((id) => id !== jobId)
        : [...list, jobId];
      localStorage.setItem(SAVED_JOBS_KEY, JSON.stringify(next));
      setIsSaved(next.includes(jobId));
    } catch {
      setIsSaved((prev) => !prev);
    }
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
                      <div className="jd-fact-k">START DATE</div>
                      <div className="jd-fact-v">
                        {job?.start_date 
                          ? new Date(job.start_date).toLocaleDateString('en-US', { 
                              year: 'numeric', 
                              month: 'short', 
                              day: 'numeric' 
                            })
                          : "Immediately"}
                      </div>
                    </div>
                    <div className="jd-fact">
                      <div className="jd-fact-k">DURATION</div>
                      <div className="jd-fact-v">{job?.duration || "—"}</div>
                    </div>
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
                    {job?.job_link ? (
                      <div className="jd-fact">
                        <div className="jd-fact-k">JOB LINK</div>
                        <div className="jd-fact-v">
                          <a href={job.job_link} target="_blank" rel="noreferrer">
                            View posting
                          </a>
                        </div>
                      </div>
                    ) : null}
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
                      <div className="jd-detail-k">Openings</div>
                      <div className="jd-detail-v">{job?.openings ?? "—"}</div>
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

                  {perksList.length > 0 && (
                    <div className="jd-perks">
                      <div className="jd-section-h">Perks</div>
                      <div className="jd-perks-list">
                        {perksList.map((p) => (
                          <span key={p} className="jd-perk-chip">{p}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="jd-actions-row">
                    <div className="jd-actions-left">
                      <button
                        type="button"
                        className={`jd-action-icon ${isSaved ? "saved" : ""}`}
                        aria-label={isSaved ? "Unsave job" : "Save job"}
                        onClick={toggleSaved}
                      >
                        {isSaved ? <BookmarkCheck size={18} /> : <Bookmark size={18} />}
                      </button>
                    </div>

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
                              await runApply(file);
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
                            onClick={() => navigate(`/candidate/applied/${existingApplication.id}`)}
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
                              // Apply now: save application only (no scoring).
                              // If a resume was already scanned in this modal, reuse it. Otherwise prompt upload.
                              if (cachedFileRef.current) {
                                uploadModeRef.current = "apply";
                                await runApply(cachedFileRef.current);
                                return;
                              }
                              uploadModeRef.current = "apply";
                              resumeInputRef.current?.click();
                            }}
                            disabled={applying || checkingApplication}
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
                      const v = scoreVisualFromPct(ring.score);
                      const gradId = `jdScoreGrad-${jobId || "x"}`;
                      const cx = 56;
                      const cy = 56;
                      const sections = applyResult?.ai_sections || null;
                      const hasSections =
                        sections &&
                        typeof sections === "object" &&
                        (sections.education_summary || sections.projects_summary || sections.work_experience_summary);
                      return (
                        <div className={`jd-result ${applyResult.ai_error ? "error" : ""}`}>
                          <div className="jd-result-label">Match Score</div>

                          <div className="jd-score-ring" aria-label={`Match score ${ring.score}%`}>
                            <svg className="jd-score-ring-svg" viewBox="0 0 112 112" role="img" aria-hidden="true">
                              <defs>
                                <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
                                  <stop offset="0%" stopColor={v.a} />
                                  <stop offset="100%" stopColor={v.b} />
                                </linearGradient>
                              </defs>
                              <circle
                                className="jd-score-ring-track"
                                cx={cx}
                                cy={cy}
                                r={ring.radius}
                                fill="none"
                                stroke="rgba(15, 23, 42, 0.12)"
                                strokeWidth="10"
                              />
                              {/* Start at 12 o'clock (90° anchor) */}
                              <circle
                                className="jd-score-ring-arc"
                                cx={cx}
                                cy={cy}
                                r={ring.radius}
                                fill="none"
                                stroke={`url(#${gradId})`}
                                strokeWidth="10"
                                strokeLinecap="round"
                                strokeDasharray={ring.strokeDasharray}
                                strokeDashoffset={ring.strokeDashoffset}
                                transform={`rotate(-90 ${cx} ${cy})`}
                              />
                            </svg>
                            <div className="jd-score-ring-inner" aria-hidden="true">
                              <div className="jd-score-ring-num">{ring.score}</div>
                              <div className="jd-score-ring-unit">%</div>
                            </div>
                          </div>

                          <div className="jd-score-ring-sub">Overall Match</div>

                          {applyResult.ai_error ? (
                            <div className="jd-result-text jd-result-text-error">
                              {applyResult.ai_error?.message || "Token exhausted. Please try again later."}
                            </div>
                          ) : hasSections ? (
                            <div className="jd-summary-cards">
                              {[
                                { key: "education_summary", title: "Education Match", Icon: GraduationCap },
                                { key: "projects_summary", title: "Projects Match", Icon: Wrench },
                                { key: "work_experience_summary", title: "Work Experience Match", Icon: Briefcase }
                              ].map((c) => {
                                const s = sections?.[c.key] || {};
                                const sc = typeof s.score === "number" ? s.score : 0;
                                const sum = (s.summary || "").trim();
                                const Icon = c.Icon;
                                return (
                                  <div key={c.key} className={`jd-summary-card ${toneFromPct(sc)}`}>
                                    <div className="jd-summary-card-top">
                                      <div className="jd-summary-card-title">
                                        <Icon className="jd-summary-icon" aria-hidden="true" />
                                        {c.title}
                                      </div>
                                    </div>
                                    <div className="jd-summary-text">{briefify(sum)}</div>
                                  </div>
                                );
                              })}
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

                  {(job?.screening_availability || job?.screening_phone) && (
                    <div className="jd-section">
                      <div className="jd-section-h">Screening Information</div>
                      <div className="jd-qa-container">
                        {job?.screening_availability && (
                          <div className="jd-qa-item">
                            <div className="jd-question">When are you available for screening?</div>
                            <div className="jd-answer">{job.screening_availability}</div>
                          </div>
                        )}
                        {job?.screening_phone && (
                          <div className="jd-qa-item">
                            <div className="jd-question">What is the best contact number?</div>
                            <div className="jd-answer">{job.screening_phone}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
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
                                salary_range: job?.salary_range ?? "",
                                job_link: job?.job_link ?? ""
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

                <div className="job-detail-meta">
                  <div className="job-detail-meta-item">
                    <MapPin className="k" aria-hidden="true" />
                    {isEditing ? (
                      <input
                        value={form.location}
                        onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))}
                        placeholder="Location"
                      />
                    ) : (
                      <span>{job?.location || "Not specified"}</span>
                    )}
                  </div>

                  <div className="job-detail-meta-item">
                    <DollarSign className="k" aria-hidden="true" />
                    {isEditing ? (
                      <input
                        value={form.salary_range}
                        onChange={(e) => setForm((p) => ({ ...p, salary_range: e.target.value }))}
                        placeholder="Salary range"
                      />
                    ) : (
                      <span>{job?.salary_range || "Not specified"}</span>
                    )}
                  </div>

                  <div className="job-detail-meta-item">
                    <Link2 className="k" aria-hidden="true" />
                    {isEditing ? (
                      <input
                        value={form.job_link}
                        onChange={(e) => setForm((p) => ({ ...p, job_link: e.target.value }))}
                        placeholder="Job link"
                      />
                    ) : job?.job_link ? (
                      <a href={job.job_link} target="_blank" rel="noreferrer">
                        Open posting
                      </a>
                    ) : (
                      <span>Not provided</span>
                    )}
                  </div>

                  {job?.created_at && (
                    <div className="job-detail-meta-item">
                      <Calendar className="k" aria-hidden="true" />
                      <span>{new Date(job.created_at).toLocaleString()}</span>
                    </div>
                  )}
                </div>

                <div className="job-detail-meta job-detail-meta-secondary">
                  <div className="job-detail-meta-item">
                    <Briefcase className="k" aria-hidden="true" />
                    <span>Opportunity Type: {job?.opportunity_type || "Not specified"}</span>
                  </div>
                  <div className="job-detail-meta-item">
                    <Briefcase className="k" aria-hidden="true" />
                    <span>Job Type: {job?.job_type || "Not specified"}</span>
                  </div>
                  <div className="job-detail-meta-item">
                    <MapPin className="k" aria-hidden="true" />
                    <span>Job Site: {job?.job_site || "Not specified"}</span>
                  </div>
                  <div className="job-detail-meta-item">
                    <Users className="k" aria-hidden="true" />
                    <span>Openings: {job?.openings ?? "Not specified"}</span>
                  </div>
                  <div className="job-detail-meta-item">
                    <GraduationCap className="k" aria-hidden="true" />
                    <span>
                      Min Experience: {job?.min_experience_years != null ? `${job.min_experience_years} years` : "Not specified"}
                    </span>
                  </div>
                  <div className="job-detail-meta-item">
                    <Wrench className="k" aria-hidden="true" />
                    <span>Perks: {perksList.length ? perksList.join(", ") : "None"}</span>
                  </div>
                  <div className="job-detail-meta-item">
                    <CalendarClock className="k" aria-hidden="true" />
                    <span>Screening Availability: {job?.screening_availability || "Not specified"}</span>
                  </div>
                  <div className="job-detail-meta-item">
                    <Phone className="k" aria-hidden="true" />
                    <span>Screening Phone: {job?.screening_phone || "Not specified"}</span>
                  </div>
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
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

