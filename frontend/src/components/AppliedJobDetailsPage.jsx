import { useMemo } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import AppliedJobDetails from "./AppliedJobDetails";

export default function AppliedJobDetailsPage() {
  const navigate = useNavigate();
  const params = useParams();

  const applicationId = useMemo(() => {
    const raw = params?.applicationId;
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [params?.applicationId]);

  if (!applicationId) return <Navigate to="/candidate/applied" replace />;

  return (
    <AppliedJobDetails
      applicationId={applicationId}
      onBack={() => {
        try {
          navigate(-1);
        } catch {
          navigate("/candidate/applied");
        }
      }}
    />
  );
}

