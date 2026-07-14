import "./AppliedJobsPage.css";
import { useCallback, useEffect, useState } from "react";
import { Calendar, Eye, MapPin, Trash2 } from "lucide-react";
import { jobAPI } from "../utils/api";
import { PageTransition, ScoreRing, SkeletonBlock, SkeletonText, StatusBadge } from "./ui";
import { formatLongDate } from "../shared/utils/dates";

export default function AppliedJobsPage({ onCountChange, onViewDetails }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rows, setRows] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await jobAPI.myApplications();
      const applications = Array.isArray(res?.applications) ? res.applications : [];
      setRows(applications);
      onCountChange?.(applications.length);
    } catch (e) {
      setError(e?.message || "Failed to load applied jobs");
      onCountChange?.(0);
    } finally {
      setLoading(false);
    }
  }, [onCountChange]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <PageTransition className="applied-jobs-container">
      <div className="applied-jobs-list">
        {loading ? (
          Array.from({ length: 2 }).map((_, index) => (
            <div className="applied-job-card applied-job-card-v2 applied-job-skeleton" key={`applied-skeleton-${index}`}>
              <SkeletonBlock className="applied-job-rank" />
              <div className="applied-job-main">
                <div className="applied-job-info">
                  <SkeletonText lines={2} />
                </div>
              </div>
              <div className="applied-job-context">
                <SkeletonBlock className="applied-meta-skeleton" />
                <SkeletonBlock className="applied-meta-skeleton" />
              </div>
              <SkeletonBlock className="applied-score-skeleton" />
              <div className="applied-job-actions">
                <SkeletonBlock className="applied-action-skeleton" />
                <SkeletonBlock className="applied-action-skeleton" />
              </div>
            </div>
          ))
        ) : error ? (
          <div className="applied-job-card">{error}</div>
        ) : rows.length === 0 ? (
          <div className="applied-job-card">No applications yet.</div>
        ) : (
          rows.map((row, index) => {
            const job = row?.job || {};
            const finalScore = Number(row?.final_score ?? 0);
            return (
              <div key={row.application_id} className="applied-job-card applied-job-card-v2">
                <div className="applied-job-rank" aria-hidden="true">#{index + 1}</div>

                <div className="applied-job-main">
                  <div className="applied-job-info">
                    <div className="applied-job-title-row">
                      <h3 className="applied-job-title">{job?.title || "Job"}</h3>
                      <StatusBadge status={row?.status || "not-reviewed"} />
                    </div>
                    <div className="applied-job-location">{job?.location || "Location not specified"}</div>
                  </div>
                </div>

                <div className="applied-job-context">
                  <div className="applied-meta-item">
                    <Calendar className="applied-meta-icon" aria-hidden="true" />
                    <span>
                      {row?.created_at
                        ? formatLongDate(row.created_at)
                        : "—"}
                    </span>
                  </div>
                  <div className="applied-meta-item">
                    <MapPin className="applied-meta-icon" aria-hidden="true" />
                    <span>{job?.location || "—"}</span>
                  </div>
                </div>

                <div className="applied-card-score">
                  <ScoreRing score={finalScore} size={58} label="Final score" />
                  <span>Final Score</span>
                </div>

                <div className="applied-job-actions">
                  <button className="btn-view-details" onClick={() => onViewDetails?.(row.application_id)}>
                    <Eye size={14} aria-hidden="true" />
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
                    <Trash2 size={14} aria-hidden="true" />
                    Withdraw
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </PageTransition>
  );
}

