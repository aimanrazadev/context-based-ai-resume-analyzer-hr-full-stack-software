import { getRingMetrics } from "../../utils/matchScore";
import { getScoreTone } from "../../shared/utils/scores";

export default function ScoreRing({ score = 0, size = 72, label = "Match score" }) {
  const strokeWidth = Math.max(5, Math.round(size * 0.09));
  const radius = (size - strokeWidth) / 2;
  const ring = getRingMetrics(score, radius);
  const { color } = getScoreTone(ring.score);
  return (
    <div className="ds-score-ring" aria-label={`${label} ${ring.score}%`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="#e6edf6" strokeWidth={strokeWidth} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={radius} stroke={color} strokeWidth={strokeWidth} fill="none"
          strokeDasharray={ring.strokeDasharray} strokeDashoffset={ring.strokeDashoffset} strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <span className="ds-score-ring__value" style={{ fontSize: size * 0.24 }}>
        {ring.score}%
      </span>
    </div>
  );
}
