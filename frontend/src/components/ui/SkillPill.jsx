export default function SkillPill({ children, tone = "neutral" }) {
  const tones = { positive: ["#ecfdf5", "#047857"], negative: ["#fef2f2", "#b91c1c"], neutral: ["#f1f5f9", "#334155"] };
  const [background, color] = tones[tone] || tones.neutral;
  return <span style={{ background, color, borderRadius: 999, padding: "4px 9px", fontSize: 12, fontWeight: 650 }}>{children}</span>;
}
