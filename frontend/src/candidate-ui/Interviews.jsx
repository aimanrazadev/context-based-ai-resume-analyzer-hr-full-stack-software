import "./Interviews.css";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Calendar, Star, Target } from "lucide-react";
import { interviewAPI } from "../utils/api";

export default function Interviews() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rows, setRows] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await interviewAPI.myInterviews();
      setRows(Array.isArray(res?.interviews) ? res.interviews : []);
    } catch (e) {
      setError(e?.message || "Failed to load interviews");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const prettyStatus = (s) => {
    const t = String(s || "").toLowerCase();
    if (t === "completed") return "Completed";
    if (t === "evaluated") return "Evaluated";
    if (t === "failed") return "Failed";
    if (t === "scheduled") return "Scheduled";
    return "Pending";
  };

  const formatDateTime = (iso, tz) => {
    if (!iso) return "—";
    try {
      const dt = new Date(iso);
      const timeStr = dt.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true });
      const dateStr = dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
      const tzDisplay = tz ? ` (${tz})` : "";
      return `${dateStr} at ${timeStr}${tzDisplay}`;
    } catch {
      return iso;
    }
  };

  return (
    <div className="candidate-interviews-container">
      <div className="interviews-header">
        <h2>My Interviews ({rows.length})</h2>
      </div>

      <div className="interviews-list">
        {loading ? (
          <div className="interview-card">Loading…</div>
        ) : error ? (
          <div className="interview-card" style={{ color: "#b91c1c" }}>
            {error}
          </div>
        ) : rows.length === 0 ? (
          <div className="interview-card">No interviews yet.</div>
        ) : (
          rows.map((it) => {
            const jobTitle = it?.job?.title || "Job";
            const status = String(it?.status || "scheduled").toLowerCase();
            const scheduledAt = it?.scheduled_at ? new Date(it.scheduled_at) : null;
            const overall = typeof it?.overall_fit === "number" ? `${it.overall_fit.toFixed(1)}/10` : "—";
            const isExpanded = selectedId === it.id;

            return (
              <div key={it.id} className="interview-card">
                {/* Card Header */}
                <div className="interview-card-header">
                  <div className="interview-title-section">
                    <h3 className="interview-card-title">{jobTitle}</h3>
                    <p className="interview-card-app-number">Application #{it?.application_id}</p>
                  </div>
                  <span className={`interview-status-badge ${status}`}>
                    {prettyStatus(status)}
                  </span>
                </div>

                {/* Quick Overview with Icons */}
                <div className="interview-quick-details">
                  <div className="detail-item">
                    <Calendar className="detail-icon" aria-hidden="true" />
                    <div className="detail-content">
                      <p className="detail-label">Date & Time</p>
                      <p className="detail-value">
                        {scheduledAt && status === "scheduled"
                          ? formatDateTime(it.scheduled_at, it.timezone)
                          : "Not scheduled yet"}
                      </p>
                    </div>
                  </div>
                  <div className="detail-item">
                    <Target className="detail-icon" aria-hidden="true" />
                    <div className="detail-content">
                      <p className="detail-label">Interview Type</p>
                      <p className="detail-value">{it?.mode ? `${it.mode}` : "Pending"}</p>
                    </div>
                  </div>
                  <div className="detail-item">
                    <Star className="detail-icon" aria-hidden="true" />
                    <div className="detail-content">
                      <p className="detail-label">Fit Score</p>
                      <p className="detail-value">
                        {status === "completed" ? `${overall}` : "Awaiting"}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Expandable Details Section */}
                <div className="interview-details-section">
                  <button
                    className="interview-details-toggle"
                    onClick={() => setSelectedId(isExpanded ? null : it.id)}
                  >
                    <span>Interview Details</span>
                    <span className={`toggle-icon ${isExpanded ? 'open' : ''}`}>▼</span>
                  </button>

                  {isExpanded && (
                    <div className="interview-details-content">
                      <div className="details-grid">
                        {it?.mode && (
                          <div className="details-column">
                            <p className="detail-label">Mode</p>
                            <p className="detail-value">{it.mode}</p>
                          </div>
                        )}
                        {it?.duration_minutes && (
                          <div className="details-column">
                            <p className="detail-label">Duration</p>
                            <p className="detail-value">{it.duration_minutes} minutes</p>
                          </div>
                        )}
                        {it?.interviewer_name && (
                          <div className="details-column">
                            <p className="detail-label">Interviewer</p>
                            <p className="detail-value">{it.interviewer_name}</p>
                          </div>
                        )}
                        {it?.location && (
                          <div className="details-column">
                            <p className="detail-label">Location</p>
                            <p className="detail-value">{it.location}</p>
                          </div>
                        )}
                      </div>
                      {it?.meeting_link && (
                        <div className="meeting-link-row">
                          <p className="detail-label">Meeting Link</p>
                          <a href={it.meeting_link} target="_blank" rel="noreferrer" className="meeting-link">
                            {it.meeting_link}
                          </a>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="interview-card-actions">
                  <button
                    className="btn-view-application"
                    onClick={() => navigate(`/applications/${it.application_id}`)}
                  >
                    View Full Application
                  </button>
                  {status === "scheduled" && it?.meeting_link && (
                    <a
                      href={it.meeting_link}
                      target="_blank"
                      rel="noreferrer"
                      className="btn-join-interview"
                      style={{ textDecoration: "none", display: "inline-block" }}
                    >
                      Join Interview
                    </a>
                  )}
                  {status === "completed" && (
                    <button
                      className="btn-view-feedback"
                      onClick={() => navigate(`/applications/${it.application_id}`)}
                    >
                      View Feedback
                    </button>
                  )}
                  {status === "evaluated" && (
                    <button
                      className="btn-view-result"
                      onClick={() => navigate(`/applications/${it.application_id}`)}
                    >
                      View Result
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

