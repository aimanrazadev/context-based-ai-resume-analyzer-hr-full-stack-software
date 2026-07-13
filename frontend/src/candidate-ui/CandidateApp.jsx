import { useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import "./CandidateApp.css";
import { ClipboardCheck, LogOut, Search } from "lucide-react";
import JobSearch from "./JobSearch";
import AppliedJobsPage from "../components/AppliedJobsPage";
import CandidateJobDetailPage from "../components/CandidateJobDetailPage";

export default function CandidateApp({ onLogout }) {
  const navigate = useNavigate();
  const location = useLocation();
  const activeKey = useMemo(() => {
    const p = location?.pathname || "";
    if (p.startsWith("/candidate/applied")) return "applied-jobs";
    return "job-search";
  }, [location?.pathname]);

  const [user] = useState(() => {
    try {
      const raw = localStorage.getItem("user");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [appliedCount, setAppliedCount] = useState(0);

  const displayName =
    user?.name && user.name !== "User"
      ? user.name
      : user?.email
        ? user.email.split("@")[0]
        : "Candidate";
  const displayRole = (user?.role || user?.userType || "candidate").replace(/(^|\s)\S/g, (m) => m.toUpperCase());
  const initials = useMemo(() => {
    const parts = String(displayName).trim().split(/\s+/).filter(Boolean);
    const a = parts[0]?.[0] || "C";
    const b = parts[1]?.[0] || parts[0]?.[1] || "J";
    return (a + b).toUpperCase();
  }, [displayName]);

  return (
    <div className="candidate-viewport">
      <div className="candidate-app-shell">
        {/* Left Sidebar */}
        <div className="candidate-sidebar">
          <div className="candidate-logo-container">
            <div className="candidate-logo-icon">SN</div>
            <div className="candidate-logo-text">StudentsNaukri</div>
          </div>
          
          <nav className="candidate-nav-menu">
            <div
              className={`candidate-nav-item ${activeKey === "job-search" ? "active" : ""}`}
              onClick={() => navigate("/candidate/jobs")}
            >
              <Search className="candidate-nav-icon" aria-hidden="true" />
              <span>Job Search</span>
            </div>
            <div
              className={`candidate-nav-item ${
                activeKey === "applied-jobs" || activeKey === "applied-job-details" ? "active" : ""
              }`}
              onClick={() => navigate("/candidate/applied")}
            >
              <ClipboardCheck className="candidate-nav-icon" aria-hidden="true" />
              <span>Applied Jobs</span>
            </div>
          </nav>

          <div className="candidate-sidebar-footer">
            <div className="candidate-sidebar-profile">
              <div className="candidate-sidebar-avatar">
                {initials}
              </div>
              <div className="candidate-sidebar-meta">
                <div className="candidate-sidebar-name">{displayName}</div>
                <div className="candidate-sidebar-role">{displayRole}</div>
              </div>
              <span className="candidate-sidebar-status" aria-hidden="true" />
            </div>
            <button type="button" className="candidate-sidebar-logout" onClick={onLogout}>
              <LogOut className="candidate-sidebar-logout-icon" aria-hidden="true" />
              Logout
            </button>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="candidate-main">
          {/* Top Header */}
          <div className="candidate-topbar">
            <h1 className="candidate-page-title">
              {activeKey === "job-search" && "Find Your Dream Job"}
              {activeKey === "applied-jobs" && `Applied Jobs (${appliedCount})`}
            </h1>
            
            <div className="candidate-topbar-right">
              <div className="candidate-search-container">
                <Search className="candidate-search-icon" aria-hidden="true" />
                <input
                  type="text"
                  className="candidate-search"
                  placeholder="Search jobs, companies, skills..."
                />
              </div>
            </div>
          </div>

          {/* Content Grid */}
          <div className="candidate-content-grid">
            <Routes>
              <Route path="/" element={<Navigate to="jobs" replace />} />
              <Route path="jobs" element={<JobSearch />} />
              <Route path="jobs/:jobId" element={<CandidateJobDetailPage />} />
              <Route
                path="applied"
                element={
                  <AppliedJobsPage
                    onCountChange={setAppliedCount}
                    onViewDetails={(id) => navigate(`/applications/${id}`)}
                  />
                }
              />
              <Route path="*" element={<Navigate to="jobs" replace />} />
            </Routes>
          </div>
        </div>
      </div>

    </div>
  );
}

