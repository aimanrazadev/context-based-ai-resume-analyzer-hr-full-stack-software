import { SkillPill } from "../ui";
import { normalizeSkill } from "../../shared/utils/skills";

export default function SkillSnapshot({ skillSnapshot }) {
  if (!skillSnapshot?.matched?.length && !skillSnapshot?.missing?.length) {
    return null;
  }

  return (
    <div className="ajd-insight-box">
      <div className="ajd-expl-title">Skill match snapshot</div>
      <div className="ajd-skill-snapshot">
        {skillSnapshot.matched.map((item) => <SkillPill key={`matched-${normalizeSkill(item)}`} tone="positive">{item}</SkillPill>)}
        {skillSnapshot.missing.map((item) => <SkillPill key={`missing-${normalizeSkill(item)}`} tone="negative">{item}</SkillPill>)}
      </div>
    </div>
  );
}
