import { useMemo } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import JobDetailModal from "./JobDetailModal";

export default function CandidateJobDetailPage() {
  const navigate = useNavigate();
  const params = useParams();

  const jobId = useMemo(() => {
    const raw = params?.jobId;
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [params?.jobId]);

  if (!jobId) return <Navigate to="/candidate/jobs" replace />;

  return (
    <JobDetailModal
      jobId={jobId}
      onClose={() => navigate("/candidate/jobs")}
      onApplied={() => navigate("/candidate/applied")}
    />
  );
}

