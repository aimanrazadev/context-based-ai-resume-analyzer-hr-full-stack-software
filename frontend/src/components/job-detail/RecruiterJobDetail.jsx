import { SkeletonBlock, SkeletonText } from "../ui";

export default function RecruiterJobDetail({
  loading,
  error,
  job,
  canEdit,
  isEditing,
  setIsEditing,
  isDraft,
  onContinueDraft,
  form,
  setForm,
  saving,
  handleSave,
  handleDelete,
  detailCards,
}) {
  return (
    <div className="job-detail-card">
      {loading ? (
        <div className="job-detail-loading job-detail-skeleton">
          <SkeletonText lines={2} />
          <div className="job-detail-info-grid">
            {Array.from({ length: 6 }).map((_, index) => (
              <SkeletonBlock className="job-detail-info-skeleton" key={index} />
            ))}
          </div>
          <SkeletonText lines={5} />
        </div>
      ) : error ? (
        <div className="job-detail-error">{error}</div>
      ) : (
        <>
          <div className="job-detail-header">
            <div className="job-detail-title-group">
              {!isEditing && (
                <div className="job-detail-avatar" aria-hidden="true">
                  {(job?.title || "J").trim().charAt(0).toUpperCase()}
                </div>
              )}
              {isEditing ? (
                <input
                  className="job-detail-title-input"
                  value={form.title}
                  onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                  placeholder="Job title"
                />
              ) : (
                <h2 className="job-detail-title">{job?.title}</h2>
              )}
            </div>

            {canEdit && (
              <div className="job-detail-actions">
                {isEditing ? (
                  <>
                    <button
                      type="button"
                      className="job-detail-btn secondary"
                      onClick={() => {
                        setIsEditing(false);
                        setForm({
                          title: job?.title ?? "",
                          description: job?.description ?? "",
                          location: job?.location ?? "",
                          salary_range: job?.salary_range ?? "",
                        });
                      }}
                      disabled={saving}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="job-detail-btn primary"
                      onClick={handleSave}
                      disabled={saving}
                    >
                      {saving ? "Saving..." : "Save"}
                    </button>
                  </>
                ) : (
                  <>
                    {isDraft && typeof onContinueDraft === "function" && (
                      <button type="button" className="job-detail-btn primary" onClick={() => onContinueDraft(job)}>
                        Continue editing
                      </button>
                    )}
                    <button type="button" className="job-detail-btn secondary" onClick={() => setIsEditing(true)}>
                      Edit
                    </button>
                    <button type="button" className="job-detail-btn danger" onClick={handleDelete} disabled={saving}>
                      Delete
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          <div className="job-detail-info-grid">
            {detailCards.map((item) => {
              const Icon = item.icon;
              return (
                <div className="job-detail-info-card" key={item.label}>
                  <div className="job-detail-info-icon">
                    <Icon aria-hidden="true" />
                  </div>
                  <div className="job-detail-info-body">
                    <div className="job-detail-info-label">{item.label}</div>
                    <div className="job-detail-info-value">
                      {item.editor && isEditing ? item.editor : item.value}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="job-detail-section">
            <h3>Description</h3>
            {isEditing ? (
              <textarea
                value={form.description}
                onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                rows={10}
              />
            ) : (
              <p className="job-detail-desc">{job?.description || "No description provided."}</p>
            )}
          </div>

          <div className="job-detail-section">
            <h3>Non-negotiables</h3>
            {Array.isArray(job?.non_negotiables) && job.non_negotiables.length > 0 ? (
              <ul className="job-detail-list">
                {job.non_negotiables.map((item, idx) => (
                  <li key={`${item}-${idx}`}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="job-detail-desc">No non-negotiables provided.</p>
            )}
          </div>

          <div className="job-detail-section">
            <h3>Required Skills</h3>
            <p className="job-detail-desc job-detail-help">
              These exact skills are used for resume matching and the green/red skill snapshot.
            </p>
            {Array.isArray(job?.required_skills) && job.required_skills.length > 0 ? (
              <div className="job-detail-skill-list" aria-label="Required skills used for matching">
                {job.required_skills.map((skill, idx) => (
                  <span key={`${skill}-${idx}`} className="job-detail-skill-pill">
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className="job-detail-desc">No required skills provided.</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
