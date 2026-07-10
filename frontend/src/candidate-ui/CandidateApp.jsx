import { useMemo, useRef, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import "./CandidateApp.css";
import { Camera, ClipboardCheck, LogOut, Search, X } from "lucide-react";
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

  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem("user");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [profilePhoto, setProfilePhoto] = useState(() => localStorage.getItem("profilePhoto") || "");
  const [accountOpen, setAccountOpen] = useState(false);
  const [accountName, setAccountName] = useState(user?.name || "");
  const photoInputRef = useRef(null);

  const displayName = user?.name || "Candidate";
  const displayRole = (user?.role || user?.userType || "candidate").replace(/(^|\s)\S/g, (m) => m.toUpperCase());
  const initials = useMemo(() => {
    const parts = String(displayName).trim().split(/\s+/).filter(Boolean);
    const a = parts[0]?.[0] || "C";
    const b = parts[1]?.[0] || parts[0]?.[1] || "J";
    return (a + b).toUpperCase();
  }, [displayName]);

  const openAccountEditor = () => {
    setAccountName(user?.name || "");
    setAccountOpen(true);
  };

  const saveAccount = () => {
    const cleanName = accountName.trim() || "Candidate";
    const updated = { ...(user || {}), name: cleanName };
    localStorage.setItem("user", JSON.stringify(updated));
    setUser(updated);
    setAccountOpen(false);
  };

  const handlePhotoChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      setProfilePhoto(value);
      localStorage.setItem("profilePhoto", value);
    };
    reader.readAsDataURL(file);
    event.target.value = "";
  };

  const removePhoto = () => {
    setProfilePhoto("");
    localStorage.removeItem("profilePhoto");
  };

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
            <button
              type="button"
              className="candidate-sidebar-profile"
              onClick={openAccountEditor}
              title="Edit account"
            >
              <div className="candidate-sidebar-avatar">
                {profilePhoto ? <img src={profilePhoto} alt="" /> : initials}
              </div>
              <div className="candidate-sidebar-meta">
                <div className="candidate-sidebar-name">{displayName}</div>
                <div className="candidate-sidebar-role">{displayRole}</div>
              </div>
              <span className="candidate-sidebar-status" aria-hidden="true" />
            </button>
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
              {activeKey === "applied-jobs" && "Applied Jobs"}
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
                element={<AppliedJobsPage onViewDetails={(id) => navigate(`/applications/${id}`)} />}
              />
              <Route path="profile" element={<Navigate to="../jobs" replace />} />
              <Route path="*" element={<Navigate to="jobs" replace />} />
            </Routes>
          </div>
        </div>
      </div>

      {accountOpen && (
        <div className="candidate-account-overlay" onClick={() => setAccountOpen(false)}>
          <div className="candidate-account-modal" onClick={(e) => e.stopPropagation()}>
            <div className="candidate-account-header">
              <h2>Edit account</h2>
              <button type="button" className="candidate-account-close" onClick={() => setAccountOpen(false)}>
                <X aria-hidden="true" />
              </button>
            </div>

            <div className="candidate-account-photo-row">
              <button
                type="button"
                className="candidate-account-avatar"
                onClick={() => photoInputRef.current?.click()}
                title="Change profile photo"
              >
                {profilePhoto ? <img src={profilePhoto} alt="Profile" /> : <span>{initials}</span>}
                <span className="candidate-account-camera">
                  <Camera aria-hidden="true" />
                </span>
              </button>
              <div className="candidate-account-photo-actions">
                <button type="button" onClick={() => photoInputRef.current?.click()}>
                  Change photo
                </button>
                {profilePhoto && (
                  <button type="button" className="danger" onClick={removePhoto}>
                    Remove
                  </button>
                )}
                <input
                  ref={photoInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoChange}
                  hidden
                />
              </div>
            </div>

            <label className="candidate-account-field">
              Name
              <input
                type="text"
                value={accountName}
                onChange={(e) => setAccountName(e.target.value)}
                placeholder="Candidate name"
              />
            </label>

            <div className="candidate-account-actions">
              <button type="button" className="secondary" onClick={() => setAccountOpen(false)}>
                Cancel
              </button>
              <button type="button" className="primary" onClick={saveAccount}>
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

