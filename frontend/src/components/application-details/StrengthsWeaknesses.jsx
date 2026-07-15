import { SkillPill } from "../ui";
import { cleanList } from "../../shared/utils/skills";

export default function StrengthsWeaknesses({ analysis }) {
  return (
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
  );
}
