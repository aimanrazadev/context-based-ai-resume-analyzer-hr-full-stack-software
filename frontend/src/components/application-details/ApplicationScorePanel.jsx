import { ScoreRing, StatusBadge } from "../ui";

export default function ApplicationScorePanel({
  applicationId,
  app,
  analysis,
  downloading,
  downloadResume,
  overallScore,
  resumeName,
  scoreTone,
}) {
  return (
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
  );
}
