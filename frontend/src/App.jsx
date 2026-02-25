import { useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import "./App.css";
import RecruiterApp from "./recruiter-ui/RecruiterApp";
import CandidateApp from "./candidate-ui/CandidateApp";
import LoginSignup from "./auth/LoginSignup";
import ApplicationDetailsPage from "./components/ApplicationDetailsPage";

function RequireAuth({ user, role, allowedRole, children }) {
  const location = useLocation();

  if (!user) return <Navigate to="/" replace state={{ from: location }} />;

  if (allowedRole && role !== allowedRole) {
    const dest = role === "candidate" ? "/candidate" : "/recruiter";
    return <Navigate to={dest} replace />;
  }

  return children;
}

export default function App() {
  const navigate = useNavigate();

  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem("user");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  const role = useMemo(() => user?.role || user?.userType || null, [user]);

  const handleLoginSuccess = (nextUser) => {
    setUser(nextUser);
    const nextRole = nextUser?.role || nextUser?.userType;
    navigate(nextRole === "candidate" ? "/candidate" : "/recruiter", { replace: true });
  };

  const handleLogout = () => {
    localStorage.removeItem("user");
    setUser(null);
    navigate("/", { replace: true });
  };

  return (
    <Routes>
      <Route
        path="/"
        element={user ? <Navigate to={role === "candidate" ? "/candidate" : "/recruiter"} replace /> : <LoginSignup onLoginSuccess={handleLoginSuccess} />}
      />

      <Route
        path="/recruiter/*"
        element={
          <RequireAuth user={user} role={role} allowedRole="recruiter">
            <RecruiterApp onLogout={handleLogout} />
          </RequireAuth>
        }
      />

      <Route
        path="/candidate/*"
        element={
          <RequireAuth user={user} role={role} allowedRole="candidate">
            <CandidateApp onLogout={handleLogout} />
          </RequireAuth>
        }
      />

      {/* Shared application details page (candidate + recruiter) */}
      <Route
        path="/applications/:applicationId"
        element={
          <RequireAuth user={user} role={role}>
            <ApplicationDetailsPage />
          </RequireAuth>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

