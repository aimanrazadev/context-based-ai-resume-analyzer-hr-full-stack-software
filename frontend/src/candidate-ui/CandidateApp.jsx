import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import "./CandidateApp.css";
import { Bell, Bookmark, CalendarClock, ClipboardCheck, LogOut, Search } from "lucide-react";
import JobSearch from "./JobSearch";
import MyProfile from "./MyProfile";
import Interviews from "./Interviews";
import AppliedJobDetailsPage from "../components/AppliedJobDetailsPage";
import AppliedJobsPage from "../components/AppliedJobsPage";
import CandidateJobDetailPage from "../components/CandidateJobDetailPage";
import { interviewAPI } from "../utils/api";

export default function CandidateApp({ onLogout }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [notifCount, setNotifCount] = useState(0);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifItems, setNotifItems] = useState([]);
  const notifRef = useRef(null);
  const seenRef = useRef(0);

  const activeKey = useMemo(() => {
    const p = location?.pathname || "";
    if (p.startsWith("/candidate/applied/")) return "applied-job-details";
    if (p.startsWith("/candidate/applied")) return "applied-jobs";
    if (p.startsWith("/candidate/saved")) return "saved-jobs";
    if (p.startsWith("/candidate/interviews")) return "interviews";
    if (p.startsWith("/candidate/profile")) return "profile";
    return "job-search";
  }, [location?.pathname]);

  const user = useMemo(() => {
    try {
      const raw = localStorage.getItem("user");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }, []);

  const displayName = user?.name || "Candidate";
  const displayRole = (user?.role || user?.userType || "candidate").replace(/(^|\s)\S/g, (m) => m.toUpperCase());
  const initials = useMemo(() => {
    const parts = String(displayName).trim().split(/\s+/).filter(Boolean);
    const a = parts[0]?.[0] || "C";
    const b = parts[1]?.[0] || parts[0]?.[1] || "J";
    return (a + b).toUpperCase();
  }, [displayName]);

  useEffect(() => {
    let alive = true;
    const loadNotifications = async () => {
      try {
        const lastSeen = Number(localStorage.getItem("notifLastSeen") || 0);
        seenRef.current = lastSeen;
        const res = await interviewAPI.myInterviews();
        if (!alive) return;
        const items = Array.isArray(res?.interviews) ? res.interviews : [];
        const scheduled = items
          .filter((it) => String(it?.status || "").toLowerCase() === "scheduled")
          .sort((a, b) => {
            const ta = a?.scheduled_at ? new Date(a.scheduled_at).getTime() : 0;
            const tb = b?.scheduled_at ? new Date(b.scheduled_at).getTime() : 0;
            return tb - ta;
          });
        const unread = scheduled.filter((it) => {
          if (!it?.scheduled_at) return true;
          const ts = new Date(it.scheduled_at).getTime();
          return Number.isFinite(ts) ? ts > lastSeen : true;
        });
        setNotifCount(unread.length);
        setNotifItems(scheduled.slice(0, 5));
      } catch {
        if (!alive) return;
        setNotifCount(0);
        setNotifItems([]);
      }
    };
    loadNotifications();
    return () => {
      alive = false;
    };
  }, [activeKey]);

  useEffect(() => {
    if (notifOpen) {
      const now = Date.now();
      localStorage.setItem("notifLastSeen", String(now));
      seenRef.current = now;
      setNotifCount(0);
    }
    const handleClickOutside = (event) => {
      if (!notifRef.current) return;
      if (!notifRef.current.contains(event.target)) {
        setNotifOpen(false);
      }
    };
    if (notifOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [notifOpen]);

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
            <div
              className={`candidate-nav-item ${activeKey === "interviews" ? "active" : ""}`}
              onClick={() => navigate("/candidate/interviews")}
            >
              <CalendarClock className="candidate-nav-icon" aria-hidden="true" />
              <span>Interviews</span>
            </div>
            <div
              className={`candidate-nav-item ${activeKey === "saved-jobs" ? "active" : ""}`}
              onClick={() => navigate("/candidate/saved")}
            >
              <Bookmark className="candidate-nav-icon" aria-hidden="true" />
              <span>Saved Jobs</span>
            </div>
          </nav>

          <div className="candidate-sidebar-footer">
            <button
              type="button"
              className="candidate-sidebar-profile"
              onClick={() => navigate("/candidate/profile")}
              title="My Profile"
            >
              <div className="candidate-sidebar-avatar">{initials}</div>
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
              {activeKey === "saved-jobs" && "Saved Jobs"}
              {activeKey === "applied-jobs" && "Applied Jobs"}
              {activeKey === "applied-job-details" && "Application Details"}
              {activeKey === "interviews" && "My Interviews"}
              {activeKey === "profile" && "My Profile"}
            </h1>
            
            <div className="candidate-topbar-right" ref={notifRef}>
              <div className="candidate-search-container">
                <Search className="candidate-search-icon" aria-hidden="true" />
                <input
                  type="text"
                  className="candidate-search"
                  placeholder="Search jobs, companies, skills..."
                />
              </div>
              <button
                type="button"
                className="candidate-notification-button"
                onClick={() => setNotifOpen((prev) => !prev)}
                aria-label="Interview notifications"
              >
                <Bell className="candidate-notification-icon" aria-hidden="true" />
                {notifCount > 0 && <span className="candidate-notification-badge">{notifCount}</span>}
              </button>
              {notifOpen && (
                <div className="candidate-notification-popover">
                  <div className="candidate-notification-title">
                    <span>Notifications</span>
                    <span className="candidate-notification-count">{notifCount || 0}</span>
                  </div>
                  <div className="candidate-notification-sub">Interviews</div>
                  {notifItems.length === 0 ? (
                    <div className="candidate-notification-empty">No new interview notifications.</div>
                  ) : (
                    <div className="candidate-notification-list">
                      {notifItems.map((it) => (
                        <button
                          key={it.id}
                          type="button"
                          className="candidate-notification-item"
                          onClick={() => {
                            setNotifOpen(false);
                            navigate("/candidate/interviews");
                          }}
                        >
                          <div className="candidate-notification-iconwrap" aria-hidden="true">IN</div>
                          <div className="candidate-notification-body">
                            <div className="candidate-notification-message">Interview scheduled</div>
                            <div className="candidate-notification-detail">{it?.job?.title || "Your application"}</div>
                          </div>
                          <div className="candidate-notification-meta">
                            {it?.scheduled_at ? new Date(it.scheduled_at).toLocaleDateString() : "Pending"}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                  <button
                    type="button"
                    className="candidate-notification-footer"
                    onClick={() => {
                      setNotifOpen(false);
                      navigate("/candidate/interviews");
                    }}
                  >
                    View all
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Content Grid */}
          <div className="candidate-content-grid">
            <Routes>
              <Route path="/" element={<Navigate to="jobs" replace />} />
              <Route path="jobs" element={<JobSearch onGoAppliedJobs={() => navigate("/candidate/applied")} />} />
              <Route path="saved" element={<JobSearch savedOnly />} />
              <Route path="jobs/:jobId" element={<CandidateJobDetailPage />} />
              <Route
                path="applied"
                element={<AppliedJobsPage onViewDetails={(id) => navigate(`/applications/${id}`)} />}
              />
              <Route path="applied/:applicationId" element={<AppliedJobDetailsPage />} />
              <Route path="interviews" element={<Interviews />} />
              <Route path="profile" element={<MyProfile />} />
              <Route path="*" element={<Navigate to="jobs" replace />} />
            </Routes>
          </div>
        </div>
      </div>
    </div>
  );
}

