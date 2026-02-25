import { useMemo, useState } from "react";
import "./RecruiterApp.css";
import {
  Briefcase,
  CalendarClock,
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
import Interviews from "./Interviews";

export default function RecruiterApp({ onLogout }) {
  const [activeView, setActiveView] = useState("dashboard");
  const [jobDetailId, setJobDetailId] = useState(null);
  const [jobsInitialFilter, setJobsInitialFilter] = useState("all");
  const [draftEditing, setDraftEditing] = useState(null); // { jobId, initialDraft }

  const user = useMemo(() => {
    try {
      const raw = localStorage.getItem("user");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }, []);

  const displayName = user?.name || "Recruiter";
  const displayRole = (user?.role || user?.userType || "recruiter").replace(/(^|\s)\S/g, (m) => m.toUpperCase());
  const initials = useMemo(() => {
    const parts = String(displayName).trim().split(/\s+/).filter(Boolean);
    const a = parts[0]?.[0] || "R";
    const b = parts[1]?.[0] || parts[0]?.[1] || "C";
    return (a + b).toUpperCase();
  }, [displayName]);

  const handleCreateClick = () => {
    setDraftEditing(null);
    setActiveView("create-job");
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
              onClick={() => setActiveView("dashboard")}
            >
              <LayoutDashboard className="nav-icon" aria-hidden="true" />
              <span>Dashboard</span>
            </div>
            <div
              className={`nav-item ${activeView === "jobs" ? "active" : ""}`}
              onClick={() => setActiveView("jobs")}
            >
              <Briefcase className="nav-icon" aria-hidden="true" />
              <span>Jobs</span>
            </div>
            <div
              className={`nav-item ${activeView === "candidates" ? "active" : ""}`}
              onClick={() => setActiveView("candidates")}
            >
              <Users className="nav-icon" aria-hidden="true" />
              <span>Candidates</span>
            </div>
            <div
              className={`nav-item ${activeView === "interviews" ? "active" : ""}`}
              onClick={() => setActiveView("interviews")}
            >
              <CalendarClock className="nav-icon" aria-hidden="true" />
              <span>Interviews</span>
            </div>
          </nav>

          <div className="sidebar-footer">
            <button
              type="button"
              className="sidebar-profile"
              onClick={() => setActiveView("dashboard")}
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
              {activeView === "jobs" && "Jobs"}
              {activeView === "candidates" && "Candidates"}
              {activeView === "interviews" && "Interviews"}
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
            {activeView === "dashboard" && <Dashboard onNavigate={setActiveView} />}
            {activeView === "jobs" && (
              <Jobs
                initialFilter={jobsInitialFilter}
                onViewJob={(id) => {
                  setJobDetailId(id);
                  setActiveView("job-detail");
                }}
              />
            )}
            {activeView === "candidates" && <Candidates />}
            {activeView === "interviews" && <Interviews />}
          </div>
        </div>
      </div>

      {/* Fullscreen Create Job Modal */}
      {activeView === "create-job" && (
        <div className="create-job-modal-overlay">
          <CreateJob
            onClose={() => setActiveView("dashboard")}
            onCreated={(_job, meta) => {
              if (meta?.to === "drafts") {
                setJobsInitialFilter("draft");
              } else {
                setJobsInitialFilter("all");
              }
              setDraftEditing(null);
              setActiveView("jobs");
            }}
            draftJobId={draftEditing?.jobId ?? null}
            initialDraft={draftEditing?.initialDraft ?? null}
          />
        </div>
      )}

      {activeView === "job-detail" && jobDetailId != null && (
        <JobDetailModal
          jobId={jobDetailId}
          onContinueDraft={(job) => {
            // Resume draft in the single-page CreateJob flow.
            setDraftEditing({
              jobId: job?.id,
              initialDraft: job?.draft_data || { formData: {} }
            });
            setJobDetailId(null);
            setActiveView("create-job");
          }}
          onClose={() => {
            setJobDetailId(null);
            setActiveView("jobs");
          }}
        />
      )}
    </div>
  );
}
