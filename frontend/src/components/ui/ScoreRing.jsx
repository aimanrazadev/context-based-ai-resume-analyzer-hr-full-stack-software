import { getRingMetrics } from "../../utils/matchScore";

export default function ScoreRing({ score = 0, size = 72, label = "Match score" }) {
  const strokeWidth = Math.max(5, Math.round(size * 0.09));
  const radius = (size - strokeWidth) / 2;
  const ring = getRingMetrics(score, radius);
  const color = ring.score >= 75 ? "#16a34a" : ring.score >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="ds-score-ring" aria-label={`${label} ${ring.score}%`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="#e6edf6" strokeWidth={strokeWidth} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={radius} stroke={color} strokeWidth={strokeWidth} fill="none"
          strokeDasharray={ring.strokeDasharray} strokeDashoffset={ring.strokeDashoffset} strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <strong className="ds-score-ring__value" style={{ fontSize: size * 0.24 }}>
        {ring.score}%
      </strong>
    </div>
  );
}
