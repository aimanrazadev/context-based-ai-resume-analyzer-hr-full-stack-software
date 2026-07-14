import { formatApplicationStatus, normalizeApplicationStatus } from "../../shared/utils/applicationStatus";

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
      {formatApplicationStatus(normalized)}
    </span>
  );
}
