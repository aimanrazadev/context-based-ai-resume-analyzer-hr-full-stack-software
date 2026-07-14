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
import { BackButton } from "./ui";
import { useAuth } from "../shared/auth/useAuth";
import { formatDate } from "../shared/utils/dates";
import CandidateJobDetail from "./job-detail/CandidateJobDetail";
import RecruiterJobDetail from "./job-detail/RecruiterJobDetail";
import "./JobDetailModal.css";

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

function briefify(text) {
  const value = String(text || "").trim();
  if (!value) return "-";
  const parts = value.split(/(?<=[.!?])\s+/).filter(Boolean);
  const short = parts.slice(0, 2).join(" ");
  const out = short || value;
  return out.length > 320 ? `${out.slice(0, 320).trim()}...` : out;
}

function getDescriptionBullets(description) {
  const raw = String(description || "").trim();
  if (!raw) return [];
  const lines = raw
    .split(/\r?\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length >= 3) return lines.slice(0, 24);

  return raw
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean)
    .slice(0, 18);
}

export default function JobDetailModal({ jobId, onClose, onContinueDraft, onApplied }) {
  const navigate = useNavigate();
  const { role } = useAuth();
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
    salary_range: "",
  });

  const resumeInputRef = useRef(null);
  const pollRef = useRef(null);
  const uploadModeRef = useRef("apply");
  const cachedFileRef = useRef(null);
  const rafRef = useRef(null);

  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState("");
  const [applyResult, setApplyResult] = useState(null);
  const [existingApplication, setExistingApplication] = useState(null);
  const [checkingApplication, setCheckingApplication] = useState(false);
  const [progress, setProgress] = useState({ active: false, percent: 0, message: "", taskId: null });
  const [scanTaskId, setScanTaskId] = useState(null);
  const [displayPct, setDisplayPct] = useState(0);

  const alreadyApplied = Boolean(existingApplication?.id);
  const canApplyAfterScan = Boolean(applyResult && scanTaskId && !progress.active && !applying && !checkingApplication);

  const jobTags = useMemo(() => {
    if (Array.isArray(job?.required_skills) && job.required_skills.length > 0) {
      return job.required_skills;
    }
    return [];
  }, [job?.required_skills]);

  const bullets = useMemo(() => getDescriptionBullets(job?.description), [job?.description]);

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
            onChange={(e) => setForm((prev) => ({ ...prev, location: e.target.value }))}
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
            onChange={(e) => setForm((prev) => ({ ...prev, salary_range: e.target.value }))}
            placeholder="Salary range"
          />
        ),
      },
      {
        label: "Apply By",
        value: job.apply_by ? formatDate(job.apply_by) : "Not specified",
        icon: Calendar,
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
        const loadedJob = res?.job;
        setJob(loadedJob);
        setForm({
          title: loadedJob?.title ?? "",
          description: loadedJob?.description ?? "",
          location: loadedJob?.location ?? "",
          salary_range: loadedJob?.salary_range ?? "",
        });

        if (isCandidate) {
          setCheckingApplication(true);
          jobAPI
            .myApplicationForJob(jobId)
            .then((appRes) => {
              if (!alive) return;
              setExistingApplication(appRes?.already_applied && appRes?.application ? appRes.application : null);
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

  useEffect(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    const target = Number(applyResult?.final_score ?? 0);
    const start = performance.now();
    const duration = 900;

    const tick = (now) => {
      const progressRatio = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progressRatio, 3);
      setDisplayPct(Math.round(target * eased));
      if (progressRatio < 1) {
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
      const statusRes = await jobAPI.applyStatus(taskId);
      const task = statusRes?.task;
      if (!task) return;
      const percent = typeof task.percent === "number" ? task.percent : 0;
      const message = task.message || "Analyzing...";

      if (task.status === "done") {
        setApplyResult(task.result || null);
        setScanTaskId(taskId);
        setProgress({ active: false, percent: 100, message: "Done", taskId: null });
        clearActivePoll();
        return;
      }

      if (task.status === "error") {
        setApplyError(cleanScanError(task.error || message || "Analysis failed"));
        setApplyResult(null);
        setScanTaskId(null);
        setProgress({ active: false, percent, message, taskId: null });
        clearActivePoll();
        return;
      }

      setProgress({ active: true, percent, message, taskId });
    };

    clearActivePoll();
    pollRef.current = setInterval(() => {
      poll().catch((err) => {
        setApplyError(cleanScanError(err?.message || "Failed to fetch progress"));
        setApplyResult(null);
        setScanTaskId(null);
        setProgress({ active: false, percent: 0, message: "", taskId: null });
        clearActivePoll();
      });
    }, 800);
    return poll();
  };

  const clearActivePoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const runScan = async (file) => {
    setApplyError("");
    setApplyResult(null);
    setScanTaskId(null);
    setApplying(true);
    setProgress({ active: true, percent: 1, message: "Uploading resume for scan...", taskId: null });
    try {
      cachedFileRef.current = file;
      const start = await jobAPI.scanResumeAsync(jobId, file);
      const taskId = start?.task_id || null;
      if (!taskId) throw new Error("Failed to start scan");
      setProgress({ active: true, percent: 3, message: "Scanning resume...", taskId });
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
        salary_range: form.salary_range,
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
    if (typeof onClose === "function") {
      onClose();
      return;
    }
    if (typeof window !== "undefined" && window.history?.length > 1) {
      navigate(-1);
      return;
    }
    navigate(role === "candidate" ? "/candidate" : "/recruiter", { replace: true });
  };

  return (
    <div className="job-detail-overlay" role="dialog" aria-modal="true">
      <div className="job-detail-page">
        <BackButton
          className="job-detail-back"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            handleBack();
          }}
        >
          Back
        </BackButton>

        {isCandidate && !isEditing ? (
          <CandidateJobDetail
            loading={loading}
            error={error}
            job={job}
            jobTags={jobTags}
            bullets={bullets}
            resumeInputRef={resumeInputRef}
            uploadModeRef={uploadModeRef}
            runScan={runScan}
            runApply={runApply}
            applyError={applyError}
            setApplyError={setApplyError}
            setApplyResult={setApplyResult}
            setProgress={setProgress}
            setApplying={setApplying}
            applying={applying}
            checkingApplication={checkingApplication}
            alreadyApplied={alreadyApplied}
            existingApplication={existingApplication}
            canApplyAfterScan={canApplyAfterScan}
            applyResult={applyResult}
            progress={progress}
            displayPct={displayPct}
            briefify={briefify}
            cleanScanError={cleanScanError}
            onViewApplication={(applicationId) => navigate(`/applications/${applicationId}`)}
          />
        ) : (
          <RecruiterJobDetail
            loading={loading}
            error={error}
            job={job}
            canEdit={canEdit}
            isEditing={isEditing}
            setIsEditing={setIsEditing}
            isDraft={isDraft}
            onContinueDraft={onContinueDraft}
            form={form}
            setForm={setForm}
            saving={saving}
            handleSave={handleSave}
            handleDelete={handleDelete}
            detailCards={detailCards}
          />
        )}
      </div>
    </div>
  );
}
