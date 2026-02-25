import { useMemo } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import AppliedJobDetails from "./AppliedJobDetails";

function getStoredRole() {
  try {
    const raw = localStorage.getItem("user");
    const u = raw ? JSON.parse(raw) : null;
    return u?.role || u?.userType || null;
  } catch {
    return null;
  }
}

export default function ApplicationDetailsPage() {
  const navigate = useNavigate();
  const params = useParams();

  const applicationId = useMemo(() => {
    const raw = params?.applicationId;
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [params?.applicationId]);

  const fallbackHome = useMemo(() => {
    const r = getStoredRole();
    return r === "recruiter" ? "/recruiter" : "/candidate";
  }, []);

  if (!applicationId) return <Navigate to={fallbackHome} replace />;

  return (
    <div style={{ padding: "18px" }}>
      <AppliedJobDetails
        applicationId={applicationId}
        onBack={() => {
          try {
            navigate(-1);
          } catch {
            navigate(fallbackHome);
          }
        }}
      />
    </div>
  );
}

