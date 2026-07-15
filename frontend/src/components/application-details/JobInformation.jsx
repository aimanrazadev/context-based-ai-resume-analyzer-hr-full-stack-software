import { formatDate } from "../../shared/utils/dates";

export default function JobInformation({ compensationLabel, formatJobDescription, job }) {
  return (
    <>
      <div className="candidate-job-meta ajd-insight-box">
        <div>
          <div className="ajd-expl-title">{compensationLabel}</div>
          <div className="candidate-job-meta-value">{job?.salary_range || "-"}</div>
        </div>
        <div>
          <div className="ajd-expl-title">Apply by</div>
          <div className="candidate-job-meta-value">{job?.apply_by ? formatDate(job.apply_by) : "-"}</div>
        </div>
        <div>
          <div className="ajd-expl-title">Job type</div>
          <div className="candidate-job-meta-value">{job?.job_type || "-"}</div>
        </div>
        <div>
          <div className="ajd-expl-title">Job site</div>
          <div className="candidate-job-meta-value">{job?.job_site || "-"}</div>
        </div>
        <div>
          <div className="ajd-expl-title">Min experience</div>
          <div className="candidate-job-meta-value">
            {job?.min_experience_years != null ? `${job.min_experience_years} years` : "-"}
          </div>
        </div>
      </div>

      <div className="ajd-job">
        <div className="ajd-expl-title">Job description</div>
        <div className="ajd-expl-text ajd-job-description">
          {formatJobDescription(job?.description)?.map((block, index) => (
            block.type === "bullets" ? (
              <ul key={`bullets-${index}`}>
                {block.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : (
              <p key={`text-${index}`}>{block.text}</p>
            )
          )) || "-"}
        </div>
      </div>
    </>
  );
}
