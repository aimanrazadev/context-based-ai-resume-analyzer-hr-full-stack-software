const normalizeApplicationStatus = (status) => {
  const value = String(status || "on-hold").toLowerCase();
  if (value === "submitted" || value === "accepted" || value === "applied" || value === "pending") {
    return "on-hold";
  }
  return value;
};

export default function StatusBadge({ status = "on-hold" }) {
  const normalized = normalizeApplicationStatus(status);
  const toneClass = {
    shortlisted: "ds-tone-positive",
    rejected: "ds-tone-negative",
    "on-hold": "ds-tone-warning",
  }[normalized] || "ds-tone-warning";

  return (
    <span className={`ds-status-badge ${toneClass}`}>
      {normalized.replaceAll("_", " ")}
    </span>
  );
}
