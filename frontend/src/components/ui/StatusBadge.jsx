export default function StatusBadge({ status = "submitted" }) {
  const normalized = String(status || "submitted").toLowerCase();
  const toneClass = {
    submitted: "ds-tone-primary",
    applied: "ds-tone-primary",
    shortlisted: "ds-tone-positive",
    rejected: "ds-tone-negative",
    "on-hold": "ds-tone-warning",
    accepted: "ds-tone-positive",
  }[normalized] || "ds-tone-primary";

  return (
    <span className={`ds-status-badge ${toneClass}`}>
      {normalized.replaceAll("_", " ")}
    </span>
  );
}
