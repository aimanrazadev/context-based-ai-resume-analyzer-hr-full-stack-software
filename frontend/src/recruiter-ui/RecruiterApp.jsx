import { useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import "./RecruiterApp.css";
import {
  Briefcase,
  LayoutDashboard,
  LogOut,
  Plus,
  Search,
  Users
} from "lucide-react";
import JobDetailModal from "../components/JobDetailModal";
import CreateJob from "./CreateJob";
import Dashboard from "./Dashboard";
import Jobs from "./Jobs";
import Candidates from "./Candidates";
import { useAuth } from "../shared/auth/useAuth";

function RecruiterJobDetailRoute({ onContinueDraft }) {
  const navigate = useNavigate();
  const { jobId } = useParams();
  const parsedJobId = Number(jobId);

  if (!Number.isFinite(parsedJobId) || parsedJobId <= 0) {
    return <Navigate to="/recruiter/jobs" replace />;
  }

  return (
    <JobDetailModal
      jobId={parsedJobId}
      onContinueDraft={onContinueDraft}
      onClose={() => navigate("/recruiter/jobs")}
    />
  );
}

export default function RecruiterApp({ onLogout }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const [jobsInitialFilter, setJobsInitialFilter] = useState("all");
  const [jobListingsTitle, setJobListingsTitle] = useState("All Jobs (...)");
  const [candidatesInitialStatus, setCandidatesInitialStatus] = useState("all");
  const [draftEditing, setDraftEditing] = useState(null); // { jobId, initialDraft }

  const displayName = user?.name || "Recruiter";
  const displayRole = (user?.role || user?.userType || "recruiter").replace(/(^|\s)\S/g, (m) => m.toUpperCase());
  const initials = useMemo(() => {
    const parts = String(displayName).trim().split(/\s+/).filter(Boolean);
    const a = parts[0]?.[0] || "R";
    const b = parts[1]?.[0] || parts[0]?.[1] || "C";
    return (a + b).toUpperCase();
  }, [displayName]);

  const activeView = useMemo(() => {
    const pathname = location?.pathname || "";
    if (pathname.startsWith("/recruiter/jobs/new")) return "create-job";
    if (pathname.startsWith("/recruiter/jobs")) return "jobs";
    if (pathname.startsWith("/recruiter/candidates")) return "candidates";
    return "dashboard";
  }, [location?.pathname]);

  const handleCreateClick = () => {
    setDraftEditing(null);
    navigate("/recruiter/jobs/new");
  };

  const handleNavigate = (view, options = {}) => {
    if (view === "candidates") {
      setCandidatesInitialStatus(options.statusFilter || "all");
      navigate("/recruiter/candidates");
      return;
    }
    if (view === "jobs") {
      navigate("/recruiter/jobs");
      return;
    }
    navigate("/recruiter");
  };

  return (
    <div className="viewport">
      <div className="app-shell">
        {/* Left Sidebar */}
        <div className="sidebar">
          <div className="logo-container">
            <div className="logo-icon">SN</div>
            <div className="logo-text">StudentsNaukri</div>
          </div>

          <nav className="nav-menu">
            <div
              className={`nav-item ${activeView === "dashboard" ? "active" : ""}`}
              onClick={() => handleNavigate("dashboard")}
            >
              <LayoutDashboard className="nav-icon" aria-hidden="true" />
              <span>Dashboard</span>
            </div>
            <div
              className={`nav-item ${activeView === "jobs" ? "active" : ""}`}
              onClick={() => handleNavigate("jobs")}
            >
              <Briefcase className="nav-icon" aria-hidden="true" />
              <span>Jobs</span>
            </div>
            <div
              className={`nav-item ${activeView === "candidates" ? "active" : ""}`}
              onClick={() => handleNavigate("candidates")}
            >
              <Users className="nav-icon" aria-hidden="true" />
              <span>Candidates</span>
            </div>
          </nav>

          <div className="sidebar-footer">
            <button
              type="button"
              className="sidebar-profile"
              onClick={() => handleNavigate("dashboard")}
              title="Profile"
            >
              <div className="sidebar-profile-avatar">{initials}</div>
              <div className="sidebar-profile-meta">
                <div className="sidebar-profile-name">{displayName}</div>
                <div className="sidebar-profile-role">{displayRole}</div>
              </div>
              <span className="sidebar-profile-status" aria-hidden="true" />
            </button>

            <button type="button" className="sidebar-logout" onClick={onLogout}>
              <LogOut className="sidebar-logout-icon" aria-hidden="true" />
              Logout
            </button>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="main">
          {/* Top Header */}
          <div className="topbar">
            <h1 className="page-title">
              {activeView === "dashboard" && "Dashboard"}
              {activeView === "jobs" && jobListingsTitle}
              {activeView === "candidates" && "Candidates"}
              {activeView === "create-job" && "Create Job"}
            </h1>

            <div className="topbar-right">
              <div className="search-container">
                <Search className="search-icon" aria-hidden="true" />
                <input type="text" className="search" placeholder="Search anything..." />
              </div>
              <button
                type="button"
                className={`topbar-create-btn ${activeView === "create-job" ? "active" : ""}`}
                onClick={handleCreateClick}
              >
                <span className="topbar-create-icon">
                  <Plus className="topbar-create-svg" aria-hidden="true" />
                </span>
                Create Job
              </button>
            </div>
          </div>

          {/* Content Grid */}
          <div className="content-grid">
            <Routes>
              <Route index element={<Dashboard onNavigate={handleNavigate} />} />
              <Route
                path="jobs"
                element={
                  <Jobs
                    initialFilter={jobsInitialFilter}
                    onTopbarTitleChange={setJobListingsTitle}
                    onViewJob={(id) => navigate(`/recruiter/jobs/${id}`)}
                  />
                }
              />
              <Route
                path="jobs/:jobId"
                element={
                  <RecruiterJobDetailRoute
                    onContinueDraft={(job) => {
                      setDraftEditing({
                        jobId: job?.id,
                        initialDraft: job?.draft_data || { formData: {} },
                      });
                      navigate("/recruiter/jobs/new");
                    }}
                  />
                }
              />
              <Route path="jobs/new" element={null} />
              <Route path="candidates" element={<Candidates initialStatusFilter={candidatesInitialStatus} />} />
              <Route path="*" element={<Navigate to="/recruiter" replace />} />
            </Routes>
          </div>
        </div>
      </div>

      {/* Fullscreen Create Job Modal */}
      {activeView === "create-job" && (
        <div className="create-job-modal-overlay">
          <CreateJob
            onClose={() => navigate("/recruiter")}
            onCreated={(_job, meta) => {
              if (meta?.to === "drafts") {
                setJobsInitialFilter("draft");
              } else {
                setJobsInitialFilter("all");
              }
              setDraftEditing(null);
              navigate("/recruiter/jobs");
            }}
            draftJobId={draftEditing?.jobId ?? null}
            initialDraft={draftEditing?.initialDraft ?? null}
          />
        </div>
      )}
    </div>
  );
}
