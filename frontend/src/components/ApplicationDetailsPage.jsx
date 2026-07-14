import { useMemo } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import AppliedJobDetails from "./AppliedJobDetails";
import { useAuth } from "../shared/auth/useAuth";

export default function ApplicationDetailsPage() {
  const navigate = useNavigate();
  const params = useParams();
  const { role } = useAuth();

  const applicationId = useMemo(() => {
    const raw = params?.applicationId;
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [params?.applicationId]);

  const fallbackHome = useMemo(() => {
    return role === "recruiter" ? "/recruiter" : "/candidate";
  }, [role]);

  if (!applicationId) return <Navigate to={fallbackHome} replace />;

  return (
    <div className="application-details-page">
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

