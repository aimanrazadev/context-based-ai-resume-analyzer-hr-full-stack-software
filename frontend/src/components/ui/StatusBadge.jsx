const normalizeApplicationStatus = (status) => {
  const value = String(status || "not-reviewed").toLowerCase().trim().replaceAll("_", "-").replace(/\s+/g, "-");
  if (value === "submitted" || value === "accepted" || value === "applied" || value === "pending") {
    return "not-reviewed";
  }
  if (value === "hold" || value === "onhold") return "on-hold";
  return value;
};

const labelForStatus = (status) =>
  status
    .replaceAll("_", "-")
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

export default function StatusBadge({ status = "not-reviewed" }) {
  const normalized = normalizeApplicationStatus(status);
  const toneClass = {
    "not-reviewed": "ds-tone-neutral",
    shortlisted: "ds-tone-positive",
    rejected: "ds-tone-negative",
    "on-hold": "ds-tone-warning",
  }[normalized] || "ds-tone-warning";

  return (
    <span className={`ds-status-badge ${toneClass}`}>
      {labelForStatus(normalized)}
    </span>
  );
}
