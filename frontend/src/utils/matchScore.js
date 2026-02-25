export function normalizeMatchScore(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  if (numeric <= 0) return 0;
  if (numeric >= 100) return 100;
  return Math.round(numeric);
}

export function resolveApplicationMatchScore(application) {
  if (!application || typeof application !== "object") return 0;

  if (typeof application.final_score === "number") {
    return normalizeMatchScore(application.final_score);
  }

  if (typeof application.ai_overall_match_score === "number") {
    return normalizeMatchScore(application.ai_overall_match_score);
  }

  if (typeof application.match_score === "number") {
    return normalizeMatchScore(application.match_score * 100);
  }

  return 0;
}

export function getRingMetrics(score, radius) {
  const safeScore = normalizeMatchScore(score);
  const safeRadius = Number(radius);
  const r = Number.isFinite(safeRadius) && safeRadius > 0 ? safeRadius : 0;
  const circumference = 2 * Math.PI * r;
  const strokeDashoffset = circumference * (1 - safeScore / 100);

  return {
    score: safeScore,
    radius: r,
    circumference,
    strokeDasharray: circumference,
    strokeDashoffset,
  };
}
