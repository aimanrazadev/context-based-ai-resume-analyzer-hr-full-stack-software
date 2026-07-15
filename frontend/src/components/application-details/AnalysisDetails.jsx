import CandidateSummary from "./CandidateSummary";
import SkillSnapshot from "./SkillSnapshot";
import StrengthsWeaknesses from "./StrengthsWeaknesses";

export default function AnalysisDetails({
  analysis,
  app,
  detailedReasoning,
  getShortVerdict,
  skillSnapshot,
}) {
  if (!analysis) {
    return (
      <div className="ajd-expl">
        <div className="ajd-expl-title">Explanation</div>
        <div className="ajd-expl-text">{app?.ai_explanation || "No explanation saved."}</div>
      </div>
    );
  }

  return (
    <div className="ajd-insights">
      <CandidateSummary analysis={analysis} getShortVerdict={getShortVerdict} />
      <StrengthsWeaknesses analysis={analysis} />

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

      <SkillSnapshot skillSnapshot={skillSnapshot} />
    </div>
  );
}
