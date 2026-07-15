import { useCallback, useEffect, useMemo, useState } from "react";
import { jobAPI } from "../shared/utils/api";
import { BackButton, ErrorState, PageTransition, ScoreRing, SkeletonBlock, SkeletonText, SkillPill, StatusBadge } from "./ui";
import { usePolling } from "../shared/hooks/usePolling";
import { formatDate } from "../shared/utils/dates";
import { getScoreTone } from "../shared/utils/scores";
import { cleanList, normalizeSkill, uniqueByNormalizedSkill } from "../shared/utils/skills";
import "./AppliedJobDetails.css";

const getShortVerdict = (analysis) => {
  const text = String(analysis?.candidate_summary || "").trim();
  if (!text) return "No AI summary was saved for this application.";
  return text;
};

const classifySkillSnapshot = ({ analysis }) => {
  const matched = cleanList(analysis?.matched_skills, 40);
  const missing = cleanList(analysis?.missing_skills, 40);
  const safeMatched = uniqueByNormalizedSkill(matched);
  const matchedKeys = new Set(safeMatched.map(normalizeSkill));
  const safeMissing = uniqueByNormalizedSkill(missing, matchedKeys);
  return { matched: safeMatched, missing: safeMissing };
};

const limitReasoningParagraphs = (text, maxParagraphs = 2, maxSentencesPerParagraph = 3) => {
  const cleanText = String(text || "").replace(/\s+/g, " ").trim();
  if (!cleanText) return "";
  const sentences = cleanText.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [cleanText];
  const capped = sentences.slice(0, maxParagraphs * maxSentencesPerParagraph);
  const paragraphs = [];
  for (let i = 0; i < capped.length; i += maxSentencesPerParagraph) {
    paragraphs.push(capped.slice(i, i + maxSentencesPerParagraph).join(" ").trim());
  }
  return paragraphs.filter(Boolean).join("\n\n");
};

const detailedReasoningText = (analysis) => {
  const source =
    analysis?.reasoning ||
    [analysis?.strength_reasoning, analysis?.weakness_reasoning]
      .map((item) => String(item || "").trim())
      .filter(Boolean)
      .join(" ");

  return limitReasoningParagraphs(source, 2, 3);
};

const formatJobDescription = (description) => {
  const text = String(description || "").replace(/\\n/g, "\n").trim();
  if (!text) return null;

  const normalized = text
    .replace(/\s*\*\s*/g, "\n- ")
    .replace(/\s*(Responsibilities:)/gi, "\n$1\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  const lines = normalized
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);

  const blocks = [];
  let bullets = [];

  lines.forEach((line) => {
    if (line.startsWith("-")) {
      bullets.push(line.replace(/^-\s*/, ""));
      return;
    }
    if (bullets.length) {
      blocks.push({ type: "bullets", items: bullets });
      bullets = [];
    }
    blocks.push({ type: "text", text: line });
  });

  if (bullets.length) blocks.push({ type: "bullets", items: bullets });
  return blocks;
};

export default function AppliedJobDetails({ applicationId, onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [pollingAnalysis, setPollingAnalysis] = useState(false);
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
    setPollingAnalysis(false);

    const fetchOnce = async () => {
      const res = await jobAPI.applicationDetails(applicationId);
      if (!alive) return null;
      setData(res || null);
      return res || null;
    };

    fetchOnce()
      .then((res) => {
        if (!alive) return;
        // If analysis is still running, poll briefly.
        const a = res?.application || null;
        const pending = !a?.score_updated_at && !a?.ai_analysis && !a?.ai_explanation;
        setPollingAnalysis(pending);
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
    };
  }, [applicationId]);

  const requestLatestApplication = useCallback(
    () => jobAPI.applicationDetails(applicationId),
    [applicationId]
  );

  const isAnalysisReady = useCallback((res) => {
    const latest = res?.application || null;
    return Boolean(latest?.score_updated_at || latest?.ai_analysis || latest?.ai_explanation);
  }, []);

  usePolling({
    enabled: pollingAnalysis && Boolean(applicationId),
    intervalMs: 1200,
    maxAttempts: 25,
    request: requestLatestApplication,
    stopWhen: isAnalysisReady,
    onSuccess: (res) => {
      setData(res || null);
      if (isAnalysisReady(res)) {
        setPollingAnalysis(false);
      }
    },
    onError: (_error, attempts) => {
      if (attempts >= 25) {
        setPollingAnalysis(false);
      }
    },
  });

  const analysis = app?.ai_analysis || null;
  const skillSnapshot = analysis ? classifySkillSnapshot({ analysis }) : { matched: [], missing: [] };
  const detailedReasoning = analysis ? detailedReasoningText(analysis) : "";
  const resume = app?.resume || null;
  const resumeName = resume?.original_filename || "Resume";
  const analysisPending = !app?.score_updated_at && !analysis && !app?.ai_explanation;
  const scoreTone = getScoreTone(overallScore);
  const jobType = String(job?.job_type || "").toLowerCase();
  const opportunityType = String(job?.opportunity_type || "").toLowerCase();
  const isInternship = opportunityType === "internship" || jobType.includes("intern");
  const compensationLabel = isInternship ? "Stipend" : "CTC";

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
    <PageTransition className="ajd-wrap">
      <BackButton className="ajd-back" onClick={() => onBack?.()}>
        Back to applied jobs
      </BackButton>

      {loading ? (
        <div className="ajd-card ajd-detail-skeleton">
          <SkeletonText lines={2} className="ajd-head-skeleton" />
          <SkeletonBlock className="ajd-note-skeleton" />
          <SkeletonBlock className="ajd-resume-skeleton" />
          <SkeletonBlock className="ajd-score-skeleton" />
          <SkeletonBlock className="ajd-summary-skeleton" />
          <div className="ajd-insight-grid">
            <SkeletonBlock className="ajd-panel-skeleton" />
            <SkeletonBlock className="ajd-panel-skeleton" />
          </div>
        </div>
      ) : error ? (
        <div className="ajd-card"><ErrorState message={error} /></div>
      ) : (
        <div className="ajd-card">
          <aside className="ajd-side-column" aria-label="Application match summary">
            <div className="ajd-side-rail">
              <div className="ajd-score-ring-wrap"><ScoreRing score={overallScore} size={116} /></div>
              <div className="ajd-score-sub">
                <span>Overall Match</span>
                <span>Strong alignment with the role requirements.</span>
              </div>

              {analysis && (
                <div
                  className="ajd-recommendation-pill"
                  style={{
                    "--ajd-score-color": scoreTone.color,
                    "--ajd-score-border": scoreTone.border,
                    "--ajd-score-bg": scoreTone.background,
                  }}
                >
                  {analysis.recommendation || "Review Manually"}
                </div>
              )}
            </div>

            {applicationId && (
              <div
                className={`ajd-resume ${downloading ? "is-downloading" : ""}`}
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
                <div className="ajd-expl-title">Your resume</div>
                <div className="ajd-resume-row">
                  <div className="ajd-resume-name">{resumeName}</div>
                  {downloading && <div className="ajd-resume-hint">Downloading...</div>}
                </div>
              </div>
            )}

            <div className="ajd-note">
              <div className="ajd-note-title">Application status</div>
              <StatusBadge status={app?.status || "not-reviewed"} />
            </div>

          </aside>

          <main className="ajd-main">
            <div className="ajd-top-row">
              <div className="ajd-head">
                <div className="ajd-title">{job?.title || "Job"}</div>
                <div className="ajd-sub">{job?.location || ""}</div>
              </div>
            </div>

          {/* Candidate Information Section */}
          {app?.candidate && (
            <div className="ajd-candidate-info">
              <div className="ajd-expl-title">Candidate Information</div>
              <div className="candidate-details">
                <div className="candidate-name-section">
                  <h4>{app.candidate.name || "Candidate"}</h4>
                  <p>{app.candidate.email || "-"}</p>
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

          {analysisPending && (
            <div className="ajd-pending">
              <div className="ajd-pending-row">
                <div className="ajd-pending-dot" />
                Analyzing your resume... this page will update automatically.
              </div>
            </div>
          )}

          {analysis ? (
            <div className="ajd-insights">
              <div className="ajd-verdict-card">
                <div>
                  <div className="ajd-expl-title">Candidate Summary</div>
                  <div className="ajd-verdict-text">{getShortVerdict(analysis)}</div>
                </div>
              </div>

              <div className="ajd-insight-grid">
                <div className="ajd-insight-box">
                  <div className="ajd-expl-title">Strengths</div>
                  <div className="ajd-pill-list">
                    {cleanList(analysis.strengths).length > 0 ? (
                      cleanList(analysis.strengths).map((item) => <SkillPill key={item} tone="positive">{item}</SkillPill>)
                    ) : (
                      <span className="ajd-empty-text">No specific strengths saved.</span>
                    )}
                  </div>
                </div>

                <div className="ajd-insight-box">
                  <div className="ajd-expl-title">Weaknesses</div>
                  <div className="ajd-pill-list">
                    {cleanList(analysis.weaknesses).length > 0 ? (
                      cleanList(analysis.weaknesses).map((item) => <SkillPill key={item} tone="negative">{item}</SkillPill>)
                    ) : (
                      <span className="ajd-empty-text">No major gaps saved.</span>
                    )}
                  </div>
                </div>
              </div>

              {detailedReasoning && (
                <div className="ajd-insight-box ajd-reasoning-card">
                  <details className="ajd-reasoning-details">
                    <summary>View Detailed AI Reasoning</summary>
                    <div className="ajd-expl-text">
                      {detailedReasoning}
                    </div>
                  </details>
                </div>
              )}

              {(skillSnapshot.matched.length > 0 || skillSnapshot.missing.length > 0) && (
                <div className="ajd-insight-box">
                  <div className="ajd-expl-title">Skill match snapshot</div>
                  <div className="ajd-skill-snapshot">
                    {skillSnapshot.matched.map((item) => <SkillPill key={`matched-${normalizeSkill(item)}`} tone="positive">{item}</SkillPill>)}
                    {skillSnapshot.missing.map((item) => <SkillPill key={`missing-${normalizeSkill(item)}`} tone="negative">{item}</SkillPill>)}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="ajd-expl">
              <div className="ajd-expl-title">Explanation</div>
              <div className="ajd-expl-text">{app?.ai_explanation || "No explanation saved."}</div>
            </div>
          )}

          <div className="candidate-job-meta ajd-insight-box">
            <div>
              <div className="ajd-expl-title">{compensationLabel}</div>
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

          <div className="ajd-job">
            <div className="ajd-expl-title">Job description</div>
            <div className="ajd-expl-text ajd-job-description">
              {formatJobDescription(job?.description)?.map((block, index) => (
                block.type === "bullets" ? (
                  <ul key={`bullets-${index}`}>
                    {block.items.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                ) : (
                  <p key={`text-${index}`}>{block.text}</p>
                )
              )) || "-"}
            </div>
          </div>
          </main>
        </div>
      )}

    </PageTransition>
  );
}


