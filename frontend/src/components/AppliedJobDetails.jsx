import { useEffect, useMemo, useRef, useState } from "react";
import { jobAPI } from "../utils/api";
import { ErrorState, LoadingState, ScoreRing, SkillPill, StatusBadge } from "./ui";
import "./AppliedJobDetails.css";

const cleanList = (items = [], limit = 6) => {
  if (!Array.isArray(items)) return [];
  return [...new Set(items.map((item) => String(item || "").trim()).filter(Boolean))].slice(0, limit);
};

const getShortVerdict = (analysis) => {
  const text = String(analysis?.candidate_summary || "").trim();
  if (!text) return "No AI summary was saved for this application.";
  return text;
};

const SKILL_ALIASES = {
  fastapi: "fastapi",
  "fast api": "fastapi",
  js: "javascript",
  javascript: "javascript",
  "machine learning": "machine learning",
  machinelearning: "machine learning",
  ml: "machine learning",
  "natural language processing": "nlp",
  naturallanguageprocessing: "nlp",
  nlp: "nlp",
  mysql: "sql",
  postgres: "sql",
  postgresql: "sql",
  sql: "sql",
  sqlite: "sql",
  react: "react",
  reactjs: "react",
  "react.js": "react",
  "rest api": "api",
  "rest apis": "api",
  restapi: "api",
  restapis: "api",
  api: "api",
  apis: "api",
  "large language models": "llm",
  largelanguagemodels: "llm",
  llm: "llm",
  llms: "llm",
  "gemini api": "gemini",
  gemini: "gemini",
  "openai api": "openai",
  openai: "openai",
  "scikit learn": "scikit-learn",
  "scikit-learn": "scikit-learn",
  sklearn: "scikit-learn",
  "problem solving": "problem solving",
  problemsolving: "problem solving",
  communication: "communication",
  communications: "communication",
  teamwork: "teamwork",
};

const normalizeSkill = (skill) => {
  const normalized = String(skill || "")
    .toLowerCase()
    .replace(/[^a-z0-9+#. ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const compact = normalized.replace(/\s+/g, "");
  return SKILL_ALIASES[normalized] || SKILL_ALIASES[compact] || normalized;
};

const uniqueByNormalizedSkill = (items = [], excludeKeys = new Set()) => {
  const seen = new Set(excludeKeys);
  const result = [];
  cleanList(items, 80).forEach((skill) => {
    const key = normalizeSkill(skill);
    if (!key || seen.has(key)) return;
    seen.add(key);
    result.push(skill);
  });
  return result;
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
    .replace(/\s*•\s*/g, "\n• ")
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
    if (line.startsWith("•")) {
      bullets.push(line.replace(/^•\s*/, ""));
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
  const skillSnapshot = analysis ? classifySkillSnapshot({ analysis }) : { matched: [], missing: [] };
  const detailedReasoning = analysis ? detailedReasoningText(analysis) : "";
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
                {downloading && <div className="ajd-resume-hint">Downloading…</div>}
              </div>
            </div>
          )}

          <div className="ajd-score-ring-wrap"><ScoreRing score={overallScore} size={116} /></div>

          <div className="ajd-score-sub">Overall Match</div>

          {analysisPending && (
            <div className="ajd-pending">
              <div className="ajd-pending-row">
                <div className="ajd-pending-dot" />
                Analyzing your resume… this page will update automatically.
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

              <div className="ajd-recommendation-row">
                <span>Recommendation</span>
                <div className="ajd-recommendation-pill">{analysis.recommendation || "Review Manually"}</div>
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
              )) || "—"}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

