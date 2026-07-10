export default function StatusBadge({ status = "submitted" }) {
  const normalized = String(status || "submitted").toLowerCase();
  const tones = {
    submitted: ["#eef2ff", "#4338ca"],
    shortlisted: ["#ecfdf5", "#047857"],
    rejected: ["#fef2f2", "#b91c1c"],
    "on-hold": ["#fffbeb", "#b45309"],
    accepted: ["#f0fdf4", "#15803d"],
  };
  const [background, color] = tones[normalized] || tones.submitted;

  return (
    <span style={{ borderRadius: 999, padding: "4px 9px", background, color, fontSize: 12, fontWeight: 700, textTransform: "capitalize" }}>
      {normalized.replaceAll("_", " ")}
    </span>
  );
}
