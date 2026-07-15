export default function CandidateInfo({ candidate }) {
  if (!candidate) return null;

  return (
    <div className="ajd-candidate-info">
      <div className="ajd-expl-title">Candidate Information</div>
      <div className="candidate-details">
        <div className="candidate-name-section">
          <h4>{candidate.name || "Candidate"}</h4>
          <p>{candidate.email || "-"}</p>
        </div>

        {(candidate.linkedin || candidate.github) && (
          <div className="candidate-socials">
            <div className="socials-title">Social Links</div>
            <div className="social-links">
              {candidate.linkedin && (
                <a href={candidate.linkedin} target="_blank" rel="noopener noreferrer" className="social-link linkedin">
                  <span className="social-icon">in</span>
                  <span>LinkedIn</span>
                </a>
              )}
              {candidate.github && (
                <a href={candidate.github} target="_blank" rel="noopener noreferrer" className="social-link github">
                  <span className="social-icon">GH</span>
                  <span>GitHub</span>
                </a>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
