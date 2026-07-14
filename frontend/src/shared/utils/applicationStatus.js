export const APPLICATION_STATUSES = [
  "not-reviewed",
  "shortlisted",
  "on-hold",
  "rejected",
];

export function normalizeApplicationStatus(status) {
  const value = String(status || "not-reviewed")
    .trim()
    .toLowerCase()
    .replaceAll("_", "-")
    .replace(/\s+/g, "-");

  if (["submitted", "accepted", "applied", "pending"].includes(value)) {
    return "not-reviewed";
  }

  if (["hold", "onhold"].includes(value)) {
    return "on-hold";
  }

  return APPLICATION_STATUSES.includes(value) ? value : "not-reviewed";
}

export function formatApplicationStatus(status) {
  return normalizeApplicationStatus(status)
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
