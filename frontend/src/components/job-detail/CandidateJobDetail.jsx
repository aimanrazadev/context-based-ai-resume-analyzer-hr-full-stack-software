import { ScoreRing, SkeletonBlock, SkeletonText, SkillPill } from "../ui";
import { formatDate } from "../../shared/utils/dates";
import { getScoreTone } from "../../shared/utils/scores";
import "../AppliedJobDetails.css";

const clampPercent = (value) => Math.max(0, Math.min(100, Number(value) || 0));

export default function CandidateJobDetail({
  loading,
  error,
  job,
  jobTags,
  bullets,
  resumeInputRef,
  uploadModeRef,
  runScan,
  runApply,
  applyError,
  setApplyError,
  setApplyResult,
  setProgress,
  setApplying,
  applying,
  checkingApplication,
  alreadyApplied,
  existingApplication,
  canApplyAfterScan,
  applyResult,
  progress,
  displayPct,
  briefify,
  cleanScanError,
  onViewApplication,
}) {
  if (loading) {
    return (
      <div className="ajd-card ajd-detail-skeleton">
        <SkeletonBlock className="ajd-score-skeleton" />
        <SkeletonText lines={2} className="ajd-head-skeleton" />
        <SkeletonBlock className="ajd-summary-skeleton" />
        <div className="ajd-insight-grid">
          <SkeletonBlock className="ajd-panel-skeleton" />
          <SkeletonBlock className="ajd-panel-skeleton" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ajd-card">
        <div className="job-detail-error">{error}</div>
      </div>
    );
  }

  const opp = String(job?.opportunity_type || "").toLowerCase();
  const jt = String(job?.job_type || "").toLowerCase();
  const isInternship = opp === "internship" || jt.includes("intern");
  const stipendLabel = isInternship ? "Stipend" : "CTC";
  const score = clampPercent(displayPct);
  const scoreTone = getScoreTone(score);
  const hasScanResult = Boolean(applyResult && applyResult.final_score !== undefined && applyResult.final_score !== null);
  const analysis = applyResult?.ai_analysis || null;

  const openFilePicker = () => {
    uploadModeRef.current = "scan";
    resumeInputRef.current?.click();
  };

  const applyWithScan = async () => {
    if (!canApplyAfterScan) {
      setApplyError("Please scan your resume first. You can apply after the match score is generated.");
      return;
    }
    uploadModeRef.current = "apply";
    await runApply();
  };

  return (
    <div className="ajd-card candidate-job-detail-card">
      <aside className="ajd-side-column" aria-label="Resume match and application actions">
        <div className="ajd-side-rail candidate-job-match">
          {hasScanResult ? (
            <>
              <div className="ajd-score-ring-wrap">
                <ScoreRing score={score} size={116} />
              </div>
              <div className="ajd-score-sub">
                <span>Overall Match</span>
                <span>{analysis?.candidate_summary ? "Resume scan completed." : briefify(applyResult?.ai_explanation)}</span>
              </div>
              <div
                className="ajd-recommendation-pill"
                style={{
                  "--ajd-score-color": scoreTone.color,
                  "--ajd-score-border": scoreTone.border,
                  "--ajd-score-bg": scoreTone.background,
                }}
              >
                {analysis?.recommendation || "Score Ready"}
              </div>
            </>
          ) : (
            <>
              <div className="candidate-job-preview-title">Resume Match</div>
              <div className="candidate-job-preview-score">--</div>
              <div className="ajd-score-sub">
                <span>Scan Required</span>
                <span>Upload a PDF or DOCX resume to generate your match score before applying.</span>
              </div>
            </>
          )}
        </div>

        <div className="ajd-resume candidate-job-actions">
          <input
            ref={resumeInputRef}
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="candidate-job-file-input"
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
                setApplyResult(null);
                setProgress({ active: false, percent: 0, message: "", taskId: null });
              } finally {
                setApplying(false);
                e.target.value = "";
              }
            }}
          />

          <div className="ajd-expl-title">Resume</div>
          <div className="candidate-job-action-stack">
            {alreadyApplied ? (
              <>
                <span className="ajd-recommendation-pill candidate-job-applied">Already Applied</span>
                <button type="button" className="candidate-job-action-btn is-primary" onClick={() => onViewApplication(existingApplication?.id)}>
                  View Application
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="candidate-job-action-btn"
                  onClick={openFilePicker}
                  disabled={applying || checkingApplication}
                >
                  Scan resume
                </button>
                <button
                  type="button"
                  className="candidate-job-action-btn is-primary"
                  onClick={applyWithScan}
                  disabled={!canApplyAfterScan || applying}
                  title={canApplyAfterScan ? "Apply with the scanned resume" : "Scan your resume first to generate a match score"}
                >
                  {applying ? "Working..." : "Apply now"}
                </button>
              </>
            )}
          </div>
          <div className="candidate-job-upload-note">PDF/DOCX only. Your resume is tied to this job application.</div>
        </div>

        <div className="ajd-note">
          <div className="ajd-note-title">Job status</div>
          <div className="candidate-job-status-pill">Actively hiring</div>
        </div>
      </aside>

      <main className="ajd-main">
        <div className="ajd-top-row">
          <div className="ajd-head">
            <div className="ajd-title">{job?.title || "Job Details"}</div>
            <div className="ajd-sub">{job?.location || "Location not specified"}</div>
          </div>

        </div>

        <div className="candidate-job-meta ajd-insight-box">
          <div>
            <div className="ajd-expl-title">{stipendLabel}</div>
            <div className="candidate-job-meta-value">{job?.salary_range || "-"}</div>
          </div>
          <div>
            <div className="ajd-expl-title">Apply by</div>
            <div className="candidate-job-meta-value">{job?.apply_by ? formatDate(job.apply_by) : "-"}</div>
          </div>
          <div>
            <div className="ajd-expl-title">Job type</div>
            <div className="candidate-job-meta-value">{job?.job_type || "-"}</div>
          </div>
          <div>
            <div className="ajd-expl-title">Job site</div>
            <div className="candidate-job-meta-value">{job?.job_site || "-"}</div>
          </div>
          <div>
            <div className="ajd-expl-title">Min experience</div>
            <div className="candidate-job-meta-value">
              {job?.min_experience_years != null ? `${job.min_experience_years} years` : "-"}
            </div>
          </div>
        </div>

        {applyError && <div className="candidate-job-alert">{applyError}</div>}

        {progress.active && (
          <div className="candidate-job-progress" aria-live="polite">
            <div className="candidate-job-progress-head">
              <div className="candidate-job-progress-msg">
                <span className="candidate-job-spinner" aria-hidden="true" />
                Calculating your match score...
              </div>
              <div>{clampPercent(progress.percent)}%</div>
            </div>
            <div className="candidate-job-progress-bar">
              <div className="candidate-job-progress-fill" style={{ width: `${clampPercent(progress.percent)}%` }} />
            </div>
          </div>
        )}

        {applyResult && (
          <CandidateScanResult
            applyResult={applyResult}
            briefify={briefify}
            cleanScanError={cleanScanError}
          />
        )}

        <div className="ajd-job">
          <div className="ajd-expl-title">Job description</div>
          {bullets.length ? (
            <ul className="ajd-expl-text ajd-job-description candidate-job-description-list">
              {bullets.slice(0, 18).map((bullet, idx) => (
                <li key={`${bullet}-${idx}`}>{bullet}</li>
              ))}
            </ul>
          ) : (
            <div className="ajd-expl-text">No description provided.</div>
          )}
        </div>

        <div className="ajd-insight-box candidate-job-skills-card">
          <div className="ajd-expl-title">Skill(s) required</div>
          {jobTags.length > 0 ? (
            <div className="ajd-skill-snapshot">
              {jobTags.map((tag) => (
                <SkillPill key={tag} tone="positive">
                  {tag}
                </SkillPill>
              ))}
            </div>
          ) : (
            <span className="ajd-empty-text">No specific skills specified by recruiter.</span>
          )}
        </div>
      </main>
    </div>
  );
}

function CandidateScanResult({ applyResult, briefify, cleanScanError }) {
  if (applyResult.ai_error) {
    return (
      <div className="ajd-insight-box candidate-job-alert">
        {cleanScanError(applyResult.ai_error?.message)}
      </div>
    );
  }

  const analysis = applyResult.ai_analysis || null;
  if (!analysis) {
    return (
      <div className="ajd-verdict-card">
        <div className="ajd-expl-title">Scan summary</div>
        <div className="ajd-verdict-text">{briefify(applyResult.ai_explanation)}</div>
      </div>
    );
  }

  return (
    <div className="ajd-insights">
      <div className="ajd-verdict-card">
        <div className="ajd-expl-title">Candidate Summary</div>
        <div className="ajd-verdict-text">{analysis.candidate_summary || "-"}</div>
      </div>

      <div className="ajd-insight-grid">
        <div className="ajd-insight-box">
          <div className="ajd-expl-title">Strengths</div>
          <div className="ajd-pill-list">
            {Array.isArray(analysis.strengths) && analysis.strengths.length > 0 ? (
              analysis.strengths.map((item) => (
                <SkillPill key={item} tone="positive">
                  {item}
                </SkillPill>
              ))
            ) : (
              <span className="ajd-empty-text">No specific strengths saved.</span>
            )}
          </div>
        </div>

        <div className="ajd-insight-box">
          <div className="ajd-expl-title">Weaknesses</div>
          <div className="ajd-pill-list">
            {Array.isArray(analysis.weaknesses) && analysis.weaknesses.length > 0 ? (
              analysis.weaknesses.map((item) => (
                <SkillPill key={item} tone="negative">
                  {item}
                </SkillPill>
              ))
            ) : (
              <span className="ajd-empty-text">No major gaps saved.</span>
            )}
          </div>
        </div>
      </div>

      {analysis.reasoning && (
        <div className="ajd-insight-box ajd-reasoning-card">
          <details className="ajd-reasoning-details">
            <summary>View Detailed AI Reasoning</summary>
            <div className="ajd-expl-text">{analysis.reasoning}</div>
          </details>
        </div>
      )}
    </div>
  );
}
