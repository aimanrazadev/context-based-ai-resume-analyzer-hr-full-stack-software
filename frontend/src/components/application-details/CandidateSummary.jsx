export default function CandidateSummary({ analysis, getShortVerdict }) {
  return (
    <div className="ajd-verdict-card">
      <div>
        <div className="ajd-expl-title">Candidate Summary</div>
        <div className="ajd-verdict-text">{getShortVerdict(analysis)}</div>
      </div>
    </div>
  );
}
