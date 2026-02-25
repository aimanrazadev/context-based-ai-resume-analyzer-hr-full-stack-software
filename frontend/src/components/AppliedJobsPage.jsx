import "./AppliedJobsPage.css";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Calendar, MapPin } from "lucide-react";
import { jobAPI } from "../utils/api";

export default function AppliedJobsPage({ onViewDetails }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rows, setRows] = useState([]);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await jobAPI.myApplications();
      setRows(Array.isArray(res?.applications) ? res.applications : []);
    } catch (e) {
      setError(e?.message || "Failed to load applied jobs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="applied-jobs-container">
      <div className="applied-jobs-header">
        <h2>Applied Jobs ({rows.length})</h2>
      </div>

      <div className="applied-jobs-list">
        {loading ? (
          <div className="applied-job-card">Loading…</div>
        ) : error ? (
          <div className="applied-job-card">{error}</div>
        ) : rows.length === 0 ? (
          <div className="applied-job-card">No applications yet.</div>
        ) : (
          rows.map((row) => {
            const job = row?.job || {};
            return (
              <div key={row.application_id} className="applied-job-card applied-job-card-v2">
                <div className="applied-job-header-v2">
                  <div className="applied-job-info">
                    <h3 className="applied-job-title">{job?.title || "Job"}</h3>
                    <div className="applied-job-location">{job?.location || "Location not specified"}</div>
                  </div>
                  <span className="applied-status-pill">Applied</span>
                </div>

                <div className="applied-job-meta-row">
                  <div className="applied-meta-item">
                    <Calendar className="applied-meta-icon" aria-hidden="true" />
                    <span>
                      {row?.created_at
                        ? new Date(row.created_at).toLocaleDateString("en-US", {
                            weekday: "long",
                            year: "numeric",
                            month: "long",
                            day: "numeric"
                          })
                        : "—"}
                    </span>
                  </div>
                  <div className="applied-meta-item">
                    <MapPin className="applied-meta-icon" aria-hidden="true" />
                    <span>{job?.location || "—"}</span>
                  </div>
                </div>

                <div className="applied-job-actions">
                  <button className="btn-view-details" onClick={() => onViewDetails?.(row.application_id)}>
                    View Details
                  </button>
                  <button
                    className="btn-withdraw"
                    onClick={async () => {
                      if (!window.confirm("Withdraw this application?")) return;
                      try {
                        await jobAPI.deleteApplication(row.application_id);
                        await load();
                      } catch (e) {
                        alert(e?.message || "Failed to withdraw application");
                      }
                    }}
                  >
                    Withdraw
                  </button>
                  <button className="btn-view-interview" onClick={() => navigate(`/candidate/interviews`)}>
                    View Interview Details
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

