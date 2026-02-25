import { useEffect, useMemo, useState } from "react";
import { Bookmark, BookmarkCheck, Calendar, DollarSign, MapPin, Sparkles, Users } from "lucide-react";
import { useNavigate } from "react-router-dom";
import "./JobSearch.css";
import { jobAPI } from "../utils/api";

const SAVED_JOBS_KEY = "savedJobs";
const SORT_OPTIONS = {
  RELEVANCE: "relevance",
  DATE_POSTED: "date_posted",
  SALARY_HIGH_TO_LOW: "salary_high_to_low",
  SALARY_LOW_TO_HIGH: "salary_low_to_high",
};

export default function JobSearch({ savedOnly = false }) {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [appliedByJobId, setAppliedByJobId] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savedIds, setSavedIds] = useState(() => {
    try {
      const raw = localStorage.getItem(SAVED_JOBS_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });
  
  // Filter states
  const [filterLocation, setFilterLocation] = useState("All Locations");
  const [filterJobSite, setFilterJobSite] = useState({
    onsite: false,
    remote: false,
  });
  const [filterSalary, setFilterSalary] = useState("Any");
  const [filterExperience, setFilterExperience] = useState("Any");
  const [filterJobTypes, setFilterJobTypes] = useState({
    fullTime: false,
    partTime: false,
    contract: false,
    internship: false,
  });
  const [sortBy, setSortBy] = useState(SORT_OPTIONS.RELEVANCE);

  const normalizeText = (value) => String(value || "").trim().toLowerCase();

  // Extract numbers from salary data (handles strings, numbers, any format)
  const extractSalaryNumbers = (job) => {
    // Try structured data first (salary_min, salary_max as numbers)
    let min = null;
    let max = null;

    // Parse salary_min
    if (job.salary_min != null) {
      const n = Number(job.salary_min);
      if (Number.isFinite(n) && n > 0) {
        // Convert to LPA if it's in rupees (> 100000)
        min = n >= 100000 ? n / 100000 : n;
      }
    }

    // Parse salary_max
    if (job.salary_max != null) {
      const n = Number(job.salary_max);
      if (Number.isFinite(n) && n > 0) {
        // Convert to LPA if it's in rupees (> 100000)
        max = n >= 100000 ? n / 100000 : n;
      }
    }

    // Fallback: parse from salary_range string if structured data unavailable
    if (min == null && max == null && job.salary_range) {
      const str = String(job.salary_range).toLowerCase();
      // Extract all numbers from the string
      const numbers = str.match(/\d+(?:\.\d+)?/g);
      
      if (numbers && numbers.length > 0) {
        const nums = numbers.map(n => Number(n)).filter(n => Number.isFinite(n) && n > 0);
        
        if (nums.length >= 2) {
          // Has range like "5-10" or "Rs 25-30"
          min = Math.min(...nums);
          max = Math.max(...nums);
        } else if (nums.length === 1) {
          // Single number - could be min with open end
          min = nums[0];
          max = null; // Open-ended
        }
      }
    }

    return { min, max };
  };

  // Map filter UI options to min/max values (in LPA)
  const getSalaryFilterRange = (filterLabel) => {
    switch (filterLabel) {
      case "5-10 LPA":
        return { min: 5, max: 10 };
      case "10-15 LPA":
        return { min: 10, max: 15 };
      case "15-20 LPA":
        return { min: 15, max: 20 };
      case "20+ LPA":
        return { min: 20, max: Infinity };
      case "Any":
      default:
        return null; // No filter
    }
  };

  // Map experience filter UI options to min/max values (in years)
  const getExperienceFilterRange = (filterLabel) => {
    switch (filterLabel) {
      case "0-2 years":
        return { min: 0, max: 2 };
      case "2-4 years":
        return { min: 2, max: 4 };
      case "4-6 years":
        return { min: 4, max: 6 };
      case "6+ years":
        return { min: 6, max: Infinity };
      case "Any":
      default:
        return null; // No filter
    }
  };

  // Extract experience from job (handles strings, numbers, any format)
  const extractExperienceYears = (job) => {
    if (job.min_experience_years != null) {
      const n = Number(job.min_experience_years);
      if (Number.isFinite(n) && n >= 0) {
        return n;
      }
    }
    return null;
  };

  useEffect(() => {
    let alive = true;

    Promise.all([
      jobAPI.getAll({ status: "active" }),
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
    let result = jobs.filter((job) => {
      if (savedOnly && !savedIds.includes(job.id)) {
        return false;
      }
      // Location filter
      if (filterLocation !== "All Locations") {
        const selectedLocation = normalizeText(filterLocation);
        const jobLocation = normalizeText(job.location);
        if (!jobLocation || !jobLocation.includes(selectedLocation)) {
          return false;
        }
      }

      // Job site filter (Onsite/Remote checkboxes)
      const hasJobSiteFilter = Object.values(filterJobSite).some((v) => v);
      if (hasJobSiteFilter) {
        const jobSite = normalizeText(job.job_site);
        const jobLocation = normalizeText(job.location);
        const matchesRemote = jobSite.includes("remote") || jobLocation.includes("remote");
        const matchesOnsite =
          jobSite.includes("onsite") ||
          jobSite.includes("on-site") ||
          jobSite.includes("in-office") ||
          jobSite.includes("office");

        const allowRemote = filterJobSite.remote && matchesRemote;
        const allowOnsite = filterJobSite.onsite && matchesOnsite;

        if (!allowRemote && !allowOnsite) {
          return false;
        }
      }

      // Salary range filter - ROBUST IMPLEMENTATION
      if (filterSalary !== "Any") {
        // Get explicit filter range from UI selection
        const filterRange = getSalaryFilterRange(filterSalary);
        
        if (filterRange) {
          // Extract job salary as numbers (handles all formats)
          const jobSalary = extractSalaryNumbers(job);
          
          // DEBUG: Uncomment to see salary parsing in console
          // console.log('Job:', job.title, '| Job salary:', jobSalary, '| Filter:', filterRange);
          
          // If job has NO salary data at all, exclude it (unless filter is "Any")
          if (jobSalary.min == null && jobSalary.max == null) {
            return false;
          }
          
          // Prepare actual ranges for overlap check
          // If job has only min, treat max as infinity (open-ended like "20+")
          // If job has only max, treat min as 0 (upper-bound only)
          const jobMin = jobSalary.min ?? 0;
          const jobMax = jobSalary.max ?? Infinity;
          
          const filterMin = filterRange.min ?? 0;
          const filterMax = filterRange.max ?? Infinity;
          
          // CRITICAL: Range overlap logic
          // Job overlaps filter if: job.max >= filter.min AND job.min <= filter.max
          const overlaps = (jobMax >= filterMin) && (jobMin <= filterMax);
          
          if (!overlaps) {
            return false;
          }
        }
      }

      // Experience filter - ROBUST IMPLEMENTATION
      if (filterExperience !== "Any") {
        // Get explicit filter range from UI selection
        const filterRange = getExperienceFilterRange(filterExperience);
        
        if (filterRange) {
          // Extract job's minimum experience requirement as number
          const jobMinExp = extractExperienceYears(job);
          
          // DEBUG: Uncomment to see experience parsing in console
          // console.log('Job:', job.title, '| Requires:', jobMinExp, 'years | Candidate has:', filterRange);
          
          // If job has no experience data, include it (assume entry-level)
          if (jobMinExp == null) {
            // No experience specified = open to all, so keep applying other filters
          } else {
            // LOGIC: Candidate with X-Y years experience should see jobs requiring <= Y years
            // Example: Candidate with "4-6 years" should see jobs requiring 0,1,2,3,4,5,6 years
            // Job requiring 7+ years should NOT show
            const candidateMaxExp = filterRange.max ?? Infinity;
          
            // Job should show if: job's minimum requirement <= candidate's maximum experience
            const isQualified = jobMinExp <= candidateMaxExp;

            if (!isQualified) {
              return false;
            }
          }
        }
      }

      // Job type filter
      const hasJobTypeFilter = Object.values(filterJobTypes).some((v) => v);
      if (hasJobTypeFilter) {
        const jobType = normalizeText(job.job_type);
        const opportunityType = normalizeText(job.opportunity_type);
        const selectedTypes = [];
        if (filterJobTypes.fullTime) selectedTypes.push("full-time");
        if (filterJobTypes.partTime) selectedTypes.push("part-time");
        if (filterJobTypes.contract) selectedTypes.push("contract");
        if (filterJobTypes.internship) selectedTypes.push("internship");

        const hasTypeMatch = selectedTypes.some((type) => {
          if (type === "internship") {
            return opportunityType.includes("internship") || jobType.includes("internship");
          }
          return jobType.includes(type);
        });

        if (!hasTypeMatch) {
          return false;
        }
      }

      return true;
    });

    // Apply sorting
    if (sortBy === SORT_OPTIONS.DATE_POSTED) {
      result = result.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    } else if (sortBy === SORT_OPTIONS.SALARY_HIGH_TO_LOW) {
      result = result.sort((a, b) => {
        const aSalary = extractSalaryNumbers(a);
        const bSalary = extractSalaryNumbers(b);
        const aVal = aSalary.max ?? aSalary.min ?? 0;
        const bVal = bSalary.max ?? bSalary.min ?? 0;
        return bVal - aVal;
      });
    } else if (sortBy === SORT_OPTIONS.SALARY_LOW_TO_HIGH) {
      result = result.sort((a, b) => {
        const aSalary = extractSalaryNumbers(a);
        const bSalary = extractSalaryNumbers(b);
        const aVal = aSalary.min ?? aSalary.max ?? 0;
        const bVal = bSalary.min ?? bSalary.max ?? 0;
        return aVal - bVal;
      });
    }
    // "Relevance" is default (no sorting)

    return result;
  }, [jobs, savedIds, savedOnly, filterLocation, filterJobSite, filterSalary, filterExperience, filterJobTypes, sortBy]);

  const total = useMemo(() => filteredJobs.length, [filteredJobs]);

  return (
    <div className="job-search-container">
      {/* Top Header (spans filters + results) */}
      <div className="job-search-topbar">
        <h2 className="job-search-topbar-title">
          {savedOnly ? `Saved Jobs (${total})` : `Found ${total} Jobs for you`}
        </h2>
        <div className="sort-options">
          <select className="sort-select" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value={SORT_OPTIONS.RELEVANCE}>Relevance</option>
            <option value={SORT_OPTIONS.DATE_POSTED}>Date Posted</option>
            <option value={SORT_OPTIONS.SALARY_HIGH_TO_LOW}>Salary: High to Low</option>
            <option value={SORT_OPTIONS.SALARY_LOW_TO_HIGH}>Salary: Low to High</option>
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
          <label>Job Site</label>
          <div className="filter-checkboxes">
            <label>
              <input
                type="checkbox"
                checked={filterJobSite.onsite}
                onChange={(e) => setFilterJobSite((p) => ({ ...p, onsite: e.target.checked }))}
              />
              Onsite
            </label>
            <label>
              <input
                type="checkbox"
                checked={filterJobSite.remote}
                onChange={(e) => setFilterJobSite((p) => ({ ...p, remote: e.target.checked }))}
              />
              Remote
            </label>
          </div>
        </div>

        <div className="filter-section">
          <label>Salary Range</label>
          <select 
            className="filter-select"
            value={filterSalary}
            onChange={(e) => setFilterSalary(e.target.value)}
          >
            <option>Any</option>
            <option>5-10 LPA</option>
            <option>10-15 LPA</option>
            <option>15-20 LPA</option>
            <option>20+ LPA</option>
          </select>
        </div>

        <div className="filter-section">
          <label>Experience</label>
          <select 
            className="filter-select"
            value={filterExperience}
            onChange={(e) => setFilterExperience(e.target.value)}
          >
            <option>Any</option>
            <option>0-2 years</option>
            <option>2-4 years</option>
            <option>4-6 years</option>
            <option>6+ years</option>
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
            <div style={{ padding: 12, color: "#6c757d" }}>Loading jobs...</div>
          ) : error ? (
            <div style={{ padding: 12, color: "#b91c1c" }}>{error}</div>
          ) : filteredJobs.length === 0 ? (
            <div style={{ padding: 12, color: "#6c757d" }}>
              {savedOnly ? "No saved jobs yet." : "No jobs found matching your filters."}
            </div>
          ) : (
            filteredJobs.map((job) => {
              const title = job.title || "Untitled role";
              const logoLetter = title.trim().slice(0, 1).toUpperCase() || "J";
              const opportunity = String(job.opportunity_type || "").toLowerCase();
              const rawJobType = String(job.job_type || "").trim().toLowerCase();
              const inferredJobType = rawJobType || (opportunity === "internship" ? "internship" : "full-time");
              const supportedJobTypes = new Set(["full-time", "part-time", "contract", "internship"]);
              const variant = supportedJobTypes.has(inferredJobType) ? inferredJobType : "full-time";
              const label = variant;
              const perksText = job.perks ? Object.keys(job.perks).filter((k) => job.perks[k]).join(", ") || "None" : "None";
              const isSaved = savedIds.includes(job.id);
              const existingApplicationId = appliedByJobId[job.id];
              const alreadyApplied = Number.isFinite(existingApplicationId) && existingApplicationId > 0;

              return (
                <div key={job.id} className="job-card">
                  <div className="job-card-header">
                    <div className="job-logo" aria-hidden="true">
                      {logoLetter}
                    </div>
                    <div className="job-title-section">
                      <div className="job-title-row">
                        <h3 className="job-title">{title}</h3>
                        <div className="job-actions">
                          <button
                            type="button"
                            className={`job-action-btn ${isSaved ? "saved" : ""}`}
                            aria-label={isSaved ? "Unsave job" : "Save job"}
                            onClick={() => {
                              setSavedIds((prev) => {
                                const next = prev.includes(job.id)
                                  ? prev.filter((id) => id !== job.id)
                                  : [...prev, job.id];
                                localStorage.setItem(SAVED_JOBS_KEY, JSON.stringify(next));
                                return next;
                              });
                            }}
                          >
                            {isSaved ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}
                          </button>
                        </div>
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

                  <div className="job-type-row">
                    <span className={`job-type-pill job-type-pill--${variant}`}>{label}</span>
                  </div>

                  <div className="job-mini-card">
                    <div className="job-mini-title">{job.short_description || title}</div>
                    <div className="job-mini-sub">Experience: {job.min_experience_years != null ? `${job.min_experience_years} yrs` : "Not specified"}</div>
                    <span className="job-mini-chip">{job.job_site || "Not specified"}</span>
                  </div>

                  <div className="job-stats">
                    <div className="job-stat">
                      <Users size={14} />
                      <span>{job.openings || "Not specified"} openings</span>
                    </div>
                    <div className="job-stat">
                      <Sparkles size={14} />
                      <span>{perksText}</span>
                    </div>
                  </div>

                  <p className="job-description">{job.description || "No description provided."}</p>

                  <div className="job-card-actions">
                    <button
                      className="btn-apply"
                      onClick={() => {
                        if (alreadyApplied) {
                          navigate(`/applications/${existingApplicationId}`);
                          return;
                        }
                        navigate(`/candidate/jobs/${job.id}`);
                      }}
                    >
                      {alreadyApplied ? "View Application" : "Apply Now"}
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

