export function getRingMetrics(score, radius) {
  const safeScore = Math.max(0, Math.min(100, Math.round(Number(score) || 0)));
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
