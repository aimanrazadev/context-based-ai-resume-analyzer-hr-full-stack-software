import { useEffect, useMemo, useState } from "react";
import { Calendar, DollarSign, MapPin } from "lucide-react";
import { useNavigate } from "react-router-dom";
import "./JobSearch.css";
import { jobAPI } from "../utils/api";
import { PageTransition, SkeletonBlock, SkeletonText } from "../components/ui";

const SORT_OPTIONS = {
  RELEVANCE: "relevance",
  DATE_POSTED: "date_posted",
};

export default function JobSearch() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [appliedByJobId, setAppliedByJobId] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Filter states
  const [filterLocation, setFilterLocation] = useState("All Locations");
  const [filterJobTypes, setFilterJobTypes] = useState({
    fullTime: false,
    partTime: false,
    contract: false,
    internship: false,
  });
  const [sortBy, setSortBy] = useState(SORT_OPTIONS.RELEVANCE);

  const normalizeText = (value) => String(value || "").trim().toLowerCase();

  useEffect(() => {
    let alive = true;

    Promise.all([
      jobAPI.getAll(),
      jobAPI.myApplications().catch(() => ({ applications: [] })),
    ])
      .then(([jobsRes, appsRes]) => {
        if (!alive) return;
        setJobs(jobsRes?.jobs || []);
        const map = {};
        const rows = Array.isArray(appsRes?.applications) ? appsRes.applications : [];
        for (const row of rows) {
          const existingJobId = Number(row?.job?.id ?? row?.job_id);
          const applicationId = Number(row?.application_id ?? row?.id);
          if (Number.isFinite(existingJobId) && existingJobId > 0 && Number.isFinite(applicationId) && applicationId > 0) {
            map[existingJobId] = applicationId;
          }
        }
        setAppliedByJobId(map);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e?.message || "Failed to load jobs");
      })
      .finally(() => {
        if (!alive) return;
        setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, []);

  const filteredJobs = useMemo(() => {
    const result = jobs.filter((job) => {
      if (filterLocation !== "All Locations") {
        const location = normalizeText(job.location);
        if (!location.includes(normalizeText(filterLocation))) return false;
      }

      const selectedTypes = [];
      if (filterJobTypes.fullTime) selectedTypes.push("full-time");
      if (filterJobTypes.partTime) selectedTypes.push("part-time");
      if (filterJobTypes.contract) selectedTypes.push("contract");
      if (filterJobTypes.internship) selectedTypes.push("internship");
      if (selectedTypes.length > 0) {
        const jobType = normalizeText(job.job_type);
        const opportunityType = normalizeText(job.opportunity_type);
        const matches = selectedTypes.some((type) =>
          type === "internship"
            ? opportunityType.includes("internship") || jobType.includes("internship")
            : jobType.includes(type)
        );
        if (!matches) return false;
      }
      return true;
    });

    if (sortBy === SORT_OPTIONS.DATE_POSTED) {
      return [...result].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }
    return result;
  }, [jobs, filterLocation, filterJobTypes, sortBy]);
  const total = useMemo(() => filteredJobs.length, [filteredJobs]);

  return (
    <PageTransition className="job-search-container">
      {/* Top Header (spans filters + results) */}
      <div className="job-search-topbar">
        <h2 className="job-search-topbar-title">
          Found {total} Jobs for you
        </h2>
        <div className="sort-options">
          <select className="sort-select" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value={SORT_OPTIONS.RELEVANCE}>Relevance</option>
            <option value={SORT_OPTIONS.DATE_POSTED}>Date Posted</option>
          </select>
        </div>
      </div>

      {/* Filters Sidebar */}
      <div className="job-filters">
        <h3>Filters</h3>
        
        <div className="filter-section">
          <label>Location</label>
          <select 
            className="filter-select"
            value={filterLocation}
            onChange={(e) => setFilterLocation(e.target.value)}
          >
            <option>All Locations</option>
            <option>Bangalore</option>
            <option>Mumbai</option>
            <option>Delhi</option>
          </select>
        </div>

        <div className="filter-section">
          <label>Job Type</label>
          <div className="filter-checkboxes">
            <label>
              <input 
                type="checkbox" 
                checked={filterJobTypes.fullTime}
                onChange={(e) => setFilterJobTypes((p) => ({ ...p, fullTime: e.target.checked }))}
              /> 
              Full Time
            </label>
            <label>
              <input 
                type="checkbox" 
                checked={filterJobTypes.partTime}
                onChange={(e) => setFilterJobTypes((p) => ({ ...p, partTime: e.target.checked }))}
              /> 
              Part Time
            </label>
            <label>
              <input 
                type="checkbox" 
                checked={filterJobTypes.contract}
                onChange={(e) => setFilterJobTypes((p) => ({ ...p, contract: e.target.checked }))}
              /> 
              Contract
            </label>
            <label>
              <input 
                type="checkbox" 
                checked={filterJobTypes.internship}
                onChange={(e) => setFilterJobTypes((p) => ({ ...p, internship: e.target.checked }))}
              /> 
              Internship
            </label>
          </div>
        </div>
      </div>

      {/* Job Listings */}
      <div className="job-listings">
        <div className="jobs-list">
          {loading ? (
            Array.from({ length: 3 }).map((_, index) => (
              <div className="job-card job-card-skeleton" key={`job-skeleton-${index}`}>
                <div className="job-card-header">
                  <SkeletonBlock className="job-logo" />
                  <div className="job-title-section">
                    <SkeletonText lines={2} />
                  </div>
                </div>
                <div className="job-details">
                  <SkeletonBlock className="job-meta-skeleton" />
                  <SkeletonBlock className="job-meta-skeleton" />
                  <SkeletonBlock className="job-meta-skeleton" />
                </div>
                <SkeletonBlock className="job-pill-skeleton" />
                <div className="job-mini-card">
                  <SkeletonText lines={2} />
                  <SkeletonBlock className="job-mini-chip-skeleton" />
                </div>
                <SkeletonText lines={2} />
                <SkeletonBlock className="job-action-skeleton" />
              </div>
            ))
          ) : error ? (
            <div className="job-search-state is-error">{error}</div>
          ) : filteredJobs.length === 0 ? (
            <div className="job-search-state">
              No jobs found matching your filters.
            </div>
          ) : (
            filteredJobs.map((job) => {
              const title = job.title || "Untitled role";
              const logoLetter = title.trim().slice(0, 1).toUpperCase() || "J";
              const opportunity = String(job.opportunity_type || "").toLowerCase();
              const rawJobType = String(job.job_type || "").trim().toLowerCase();
              const jobType = rawJobType || (opportunity === "internship" ? "internship" : "full-time");
              const existingApplicationId = appliedByJobId[job.id];
              const alreadyApplied = Number.isFinite(existingApplicationId) && existingApplicationId > 0;
              const isClosed = String(job.status || "").toLowerCase() === "closed";

              return (
                <div key={job.id} className="job-card">
                  <div className="job-card-header">
                    <div className="job-logo" aria-hidden="true">
                      {logoLetter}
                    </div>
                    <div className="job-title-section">
                      <div className="job-title-row">
                        <h3 className="job-title">{title}</h3>
                      </div>
                    </div>
                  </div>

                  <div className="job-details">
                    <div className="job-detail-item">
                      <MapPin className="job-detail-icon" aria-hidden="true" />
                      <span>{job.location || "Not specified"}</span>
                    </div>
                    <div className="job-detail-item">
                      <DollarSign className="job-detail-icon" aria-hidden="true" />
                      <span>{job.salary_range || "Not specified"}</span>
                    </div>
                    <div className="job-detail-item">
                      <Calendar className="job-detail-icon" aria-hidden="true" />
                      <span>{job.created_at ? new Date(job.created_at).toLocaleDateString() : "—"}</span>
                    </div>
                  </div>

                  <div className="job-meta-chips">
                    <span className="job-meta-chip job-meta-chip--type">{jobType}</span>
                    <span className="job-meta-chip job-meta-chip--site">{job.job_site || "Not specified"}</span>
                    <span className="job-meta-chip job-meta-chip--experience">
                      {job.min_experience_years != null ? `${job.min_experience_years} years` : "Not specified"}
                    </span>
                  </div>

                  <div className="job-mini-card">
                    <div className="job-mini-title">{job.short_description || title}</div>
                  </div>

                  <p className="job-description">{job.description || "No description provided."}</p>

                  <div className="job-card-actions">
                    <button
                      className={`btn-apply ${isClosed ? "is-closed" : ""}`}
                      disabled={isClosed}
                      onClick={() => {
                        if (isClosed) return;
                        if (alreadyApplied) {
                          navigate(`/applications/${existingApplicationId}`);
                          return;
                        }
                        navigate(`/candidate/jobs/${job.id}`);
                      }}
                    >
                      {isClosed ? "Closed" : alreadyApplied ? "View Application" : "Apply Now"}
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </PageTransition>
  );
}

