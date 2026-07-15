import { useCallback, useEffect, useMemo, useState } from "react";
import { jobAPI } from "../shared/utils/api";
import { BackButton, ErrorState, PageTransition, SkeletonBlock, SkeletonText } from "./ui";
import { usePolling } from "../shared/hooks/usePolling";
import { getScoreTone } from "../shared/utils/scores";
import { cleanList, normalizeSkill, uniqueByNormalizedSkill } from "../shared/utils/skills";
import AnalysisDetails from "./application-details/AnalysisDetails";
import ApplicationScorePanel from "./application-details/ApplicationScorePanel";
import CandidateInfo from "./application-details/CandidateInfo";
import JobInformation from "./application-details/JobInformation";
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

function ApplicationDetailsSkeleton() {
  return (
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
  );
}

function PendingAnalysisNotice() {
  return (
    <div className="ajd-pending">
      <div className="ajd-pending-row">
        <div className="ajd-pending-dot" />
        Analyzing your resume... this page will update automatically.
      </div>
    </div>
  );
}

export default function AppliedJobDetails({ applicationId, onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [pollingAnalysis, setPollingAnalysis] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const app = data?.application || null;
  const job = app?.job || null;
  const analysis = app?.ai_analysis || null;
  const isAnalysisComplete = useMemo(() => !!app?.score_updated_at, [app?.score_updated_at]);
  const overallScore = isAnalysisComplete ? Number(app?.final_score ?? 0) : 0;
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
        const latest = res?.application || null;
        const pending = !latest?.score_updated_at && !latest?.ai_analysis && !latest?.ai_explanation;
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

  const downloadResume = async () => {
    if (!applicationId || downloading) return;
    setDownloading(true);
    try {
      const blob = await jobAPI.downloadApplicationResume(applicationId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = resumeName || "resume";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
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
        <ApplicationDetailsSkeleton />
      ) : error ? (
        <div className="ajd-card"><ErrorState message={error} /></div>
      ) : (
        <div className="ajd-card">
          <ApplicationScorePanel
            applicationId={applicationId}
            app={app}
            analysis={analysis}
            downloading={downloading}
            downloadResume={downloadResume}
            overallScore={overallScore}
            resumeName={resumeName}
            scoreTone={scoreTone}
          />

          <main className="ajd-main">
            <div className="ajd-top-row">
              <div className="ajd-head">
                <div className="ajd-title">{job?.title || "Job"}</div>
                <div className="ajd-sub">{job?.location || ""}</div>
              </div>
            </div>

            <CandidateInfo candidate={app?.candidate} />
            {analysisPending && <PendingAnalysisNotice />}

            <AnalysisDetails
              analysis={analysis}
              app={app}
              detailedReasoning={detailedReasoning}
              getShortVerdict={getShortVerdict}
              skillSnapshot={skillSnapshot}
            />

            <JobInformation
              compensationLabel={compensationLabel}
              formatJobDescription={formatJobDescription}
              job={job}
            />
          </main>
        </div>
      )}
    </PageTransition>
  );
}
