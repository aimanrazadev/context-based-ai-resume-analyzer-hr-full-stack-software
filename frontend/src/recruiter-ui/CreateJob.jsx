import { useEffect, useMemo, useState } from "react";
import "./CreateJob.css";
import { BackButton } from "../components/ui";
import { jobAPI } from "../shared/utils/api";
import { useAuth } from "../shared/auth/useAuth";
import { ALL_SKILLS } from "../shared/utils/skillsList";
import {
  DEFAULT_JOB_FORM_DATA,
  buildJobFormPayload,
  hasRequiredActiveJobFields,
  toCreateJobResetData,
} from "../features/jobs/create/jobFormMapper";

const NON_MATCHING_SKILL_KEYS = new Set([
  "communication",
  "teamwork",
  "problem solving",
  "critical thinking",
  "time management",
  "leadership",
  "adaptability",
  "collaboration",
  "presentation",
  "stakeholder management",
  "project management",
  "analytical thinking"
]);

const normalizeSkill = (skill) => String(skill || "").replace(/\s+/g, " ").trim();

const skillKey = (skill) =>
  normalizeSkill(skill)
    .toLowerCase()
    .replace(/\([^)]*\)/g, "")
    .replace(/[^a-z0-9+#.]+/g, " ")
    .trim();

const uniqueSkills = (skills) => {
  const seen = new Set();
  return skills.filter((skill) => {
    const key = skillKey(skill);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const SYSTEM_REQUIRED_SKILLS = uniqueSkills(ALL_SKILLS).filter(
  (skill) => !NON_MATCHING_SKILL_KEYS.has(skillKey(skill))
);

const skillLookup = new Map(SYSTEM_REQUIRED_SKILLS.map((skill) => [skillKey(skill), skill]));

export default function CreateJob({ onClose, onCreated, draftJobId = null, initialDraft = null }) {
  const { user, role } = useAuth();
  const isEditingDraft = useMemo(() => Boolean(draftJobId), [draftJobId]);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const isBusy = isPublishing || isSavingDraft;
  const [error, setError] = useState("");
  const [formData, setFormData] = useState(DEFAULT_JOB_FORM_DATA);
  const [skillsDropdown, setSkillsDropdown] = useState(false);
  const [skillSearch, setSkillSearch] = useState("");
  const [skillWarning, setSkillWarning] = useState("");

  useEffect(() => {
    if (!initialDraft) return;
    const fd = initialDraft?.formData || initialDraft;
    if (fd && typeof fd === "object") {
      // Convert ISO dates to datetime-local format for inputs
      const converted = {
        ...fd,
        shortDescription: fd.shortDescription ?? fd.short_description ?? "",
      };
      setFormData((prev) => ({ ...prev, ...converted }));
    }
  }, [initialDraft]);

  const selectedSkillKeys = useMemo(
    () => new Set(formData.requiredSkills.map(skillKey)),
    [formData.requiredSkills]
  );

  const filteredSkills = useMemo(() => {
    if (!skillSearch.trim()) return [];
    const query = skillSearch.toLowerCase();
    return SYSTEM_REQUIRED_SKILLS
      .filter((s) => !selectedSkillKeys.has(skillKey(s)) && s.toLowerCase().includes(query))
      .slice(0, 15);
  }, [skillSearch, selectedSkillKeys]);

  const hasSkill = (skill) => {
    return selectedSkillKeys.has(skillKey(skill));
  };

  const handleAddSkill = (skill, { keepInputOpen = true, showWarning = true } = {}) => {
    const normalized = normalizeSkill(skill);
    if (!normalized) return;
    const systemSkill = skillLookup.get(skillKey(normalized));
    if (!systemSkill) {
      if (showWarning) setSkillWarning("Some skills are not recognised.");
      setSkillSearch("");
      setSkillsDropdown(keepInputOpen);
      return;
    }

    setSkillWarning("");
    if (!hasSkill(systemSkill)) {
      setFormData((prev) => ({
        ...prev,
        requiredSkills: [...prev.requiredSkills, systemSkill]
      }));
    }
    setSkillSearch("");
    setSkillsDropdown(keepInputOpen);
  };

  const handleRemoveSkill = (skill) => {
    setFormData((prev) => ({
      ...prev,
      requiredSkills: prev.requiredSkills.filter((s) => s !== skill)
    }));
  };

  const addSkillsFromText = (value) => {
    const pieces = String(value || "")
      .split(/[,;\n\t]+/)
      .map(normalizeSkill)
      .filter(Boolean);
    let added = 0;
    let rejected = 0;
    setFormData((prev) => {
      const selected = new Set(prev.requiredSkills.map(skillKey));
      const nextSkills = [...prev.requiredSkills];
      pieces.forEach((skill) => {
        const systemSkill = skillLookup.get(skillKey(skill));
        if (!systemSkill) {
          rejected += 1;
          return;
        }
        const key = skillKey(systemSkill);
        if (selected.has(key)) return;
        selected.add(key);
        nextSkills.push(systemSkill);
        added += 1;
      });
      return { ...prev, requiredSkills: nextSkills };
    });
    setSkillWarning(rejected > 0 ? "Some skills are not recognised." : "");
    if (added > 0 || rejected > 0) setSkillSearch("");
    setSkillsDropdown(true);
  };

  const handleSkillKeyDown = (e) => {
    if (["Enter", ",", "Tab"].includes(e.key) && skillSearch.trim()) {
      e.preventDefault();
      addSkillsFromText(skillSearch);
    }
    if (e.key === "Backspace" && !skillSearch && formData.requiredSkills.length > 0) {
      handleRemoveSkill(formData.requiredSkills[formData.requiredSkills.length - 1]);
    }
    if (e.key === "Escape") {
      setSkillsDropdown(false);
    }
  };

  const handleSkillPaste = (e) => {
    const text = e.clipboardData?.getData("text") || "";
    if (!/[,\n;\t]/.test(text)) return;
    e.preventDefault();
    addSkillsFromText(text);
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleJobDescriptionKeyDown = (e) => {
    if (e.key !== "Enter") return;
    const value = formData.jobDescription || "";
    const start = e.currentTarget.selectionStart ?? value.length;
    const end = e.currentTarget.selectionEnd ?? value.length;
    const before = value.slice(0, start);
    const after = value.slice(end);
    const lineStart = before.lastIndexOf("\n") + 1;
    const currentLine = before.slice(lineStart);
    const match = currentLine.match(/^\s*(?:[-*]\s+|\d+\.\s+)/);
    if (!match) return;

    e.preventDefault();
    const prefix = match[0];
    const insert = `\n${prefix}`;
    const next = `${before}${insert}${after}`;
    setFormData((prev) => ({
      ...prev,
      jobDescription: next,
    }));

    const cursor = before.length + insert.length;
    requestAnimationFrame(() => {
      e.currentTarget.setSelectionRange(cursor, cursor);
    });
  };

  const handleRequirementChange = (index, value) => {
    const updated = [...formData.nonNegotiables];
    updated[index] = value;
    setFormData(prev => ({ ...prev, nonNegotiables: updated }));
  };

  const addRequirement = () => {
    setFormData(prev => ({
      ...prev,
      nonNegotiables: [...prev.nonNegotiables, ""]
    }));
  };

  const removeRequirement = (index) => {
    const updated = formData.nonNegotiables.filter((_, i) => i !== index);
    setFormData(prev => ({ ...prev, nonNegotiables: updated }));
  };

  const handleSubmit = async () => {
    // Validation
    if (!hasRequiredActiveJobFields(formData)) {
      setError("Please fill in all required fields");
      return;
    }

    setIsPublishing(true);
    setError("");

    try {
      if (!user || role !== "recruiter") {
        throw new Error("You must be logged in as a recruiter");
      }

      const jobData = buildJobFormPayload(formData, "active");

      const response = isEditingDraft
        ? await jobAPI.update(draftJobId, {
            ...jobData,
            status: "active",
            draft_data: null,
            draft_step: 1
          })
        : await jobAPI.create(jobData);

      if (response?.success || response?.job?.id || response?.id) {
        // After successful creation, redirect recruiter back to Jobs page.
        if (onCreated) {
          onCreated(response?.job || response);
          return;
        }
        // Reset form
        setFormData(toCreateJobResetData());
      }
    } catch (err) {
      const msg =
        typeof err?.message === "string"
          ? err.message
          : typeof err === "string"
            ? err
            : "Failed to create job. Please try again.";
      setError(msg);
    } finally {
      setIsPublishing(false);
    }
  };

  const handleSaveDraft = async () => {
    setIsSavingDraft(true);
    setError("");
    try {
      if (!user || role !== "recruiter") {
        throw new Error("You must be logged in as a recruiter");
      }

      const jobData = buildJobFormPayload(formData, "draft");

      const response = isEditingDraft ? await jobAPI.update(draftJobId, jobData) : await jobAPI.create(jobData);
      if (response?.success || response?.job?.id || response?.id) {
        // Redirect immediately (avoid blocking `alert()` which pauses navigation).
        onCreated?.(response?.job || response, { to: "drafts" });
        return;
      }
    } catch (err) {
      const msg =
        typeof err?.message === "string"
          ? err.message
          : typeof err === "string"
            ? err
            : "Failed to save draft. Please try again.";
      setError(msg);
    } finally {
      setIsSavingDraft(false);
    }
  };

  return (
    <div className="job-page">
      {/* Back Button */}
      <BackButton className="job-back-btn" onClick={onClose} />
      
      <div className="job-card">
        {/* Header */}
        <div className="form-header">
          <h2>
            Create New Job Posting
          </h2>
        </div>

        <div className="form-step">
          <div className="form-group job-title-field">
            <label>Job Title <span className="required">*</span></label>
            <input
              type="text"
              value={formData.jobTitle}
              onChange={(e) => handleInputChange("jobTitle", e.target.value)}
              placeholder="Product Manager II"
            />
          </div>

          <div className="form-group short-description-field">
            <label>Short Description</label>
            <input
              type="text"
              value={formData.shortDescription}
              onChange={(e) => handleInputChange("shortDescription", e.target.value)}
              placeholder="Backend-focused role with cloud and API work"
            />
          </div>

          <div className="form-row apply-by-field">
            <div className="form-group">
              <label>Apply By</label>
              <input
                type="datetime-local"
                value={formData.applyBy}
                onChange={(e) => handleInputChange("applyBy", e.target.value)}
              />
            </div>
          </div>

          <div className="form-row min-experience-field">
            <div className="form-group">
              <label>Minimum Experience (years)</label>
              <input
                type="number"
                min="0"
                step="1"
                value={formData.minExperienceYears}
                onChange={(e) => handleInputChange("minExperienceYears", e.target.value)}
                placeholder="0"
              />
            </div>
          </div>

          <div className="form-row work-mode-field">
            <div className="form-group">
              <label>Job Type</label>
              <div className="option-row">
                <label className="radio-option">
                  <input
                    type="radio"
                    name="jobType"
                    value="full-time"
                    checked={formData.jobType === "full-time"}
                    onChange={(e) => handleInputChange("jobType", e.target.value)}
                  />
                  Full-time
                </label>
                <label className="radio-option">
                  <input
                    type="radio"
                    name="jobType"
                    value="part-time"
                    checked={formData.jobType === "part-time"}
                    onChange={(e) => handleInputChange("jobType", e.target.value)}
                  />
                  Part-time
                </label>
                <label className="radio-option">
                  <input
                    type="radio"
                    name="jobType"
                    value="contract"
                    checked={formData.jobType === "contract"}
                    onChange={(e) => handleInputChange("jobType", e.target.value)}
                  />
                  Contract
                </label>
                <label className="radio-option">
                  <input
                    type="radio"
                    name="jobType"
                    value="internship"
                    checked={formData.jobType === "internship"}
                    onChange={(e) => handleInputChange("jobType", e.target.value)}
                  />
                  Internship
                </label>
              </div>
            </div>
            <div className="form-group">
              <label>Job Site</label>
              <div className="option-row">
                <label className="radio-option">
                  <input
                    type="radio"
                    name="jobSite"
                    value="remote"
                    checked={formData.jobSite === "remote"}
                    onChange={(e) => handleInputChange("jobSite", e.target.value)}
                  />
                  Remote
                </label>
                <label className="radio-option">
                  <input
                    type="radio"
                    name="jobSite"
                    value="hybrid"
                    checked={formData.jobSite === "hybrid"}
                    onChange={(e) => handleInputChange("jobSite", e.target.value)}
                  />
                  Hybrid
                </label>
                <label className="radio-option">
                  <input
                    type="radio"
                    name="jobSite"
                    value="onsite"
                    checked={formData.jobSite === "onsite"}
                    onChange={(e) => handleInputChange("jobSite", e.target.value)}
                  />
                  Onsite
                </label>
              </div>
            </div>
          </div>

          <div className="form-group salary-field">
            <label>{formData.jobType === "internship" ? "Stipend" : "CTC"} <span className="required">*</span></label>
            <div className="salary-input-group">
              <select
                value={formData.salaryCurrency}
                onChange={(e) => handleInputChange("salaryCurrency", e.target.value)}
                className="currency-select"
              >
                <option value="Rs">Rs</option>
                <option value="$">$</option>
                <option value="EUR">EUR</option>
              </select>
              <input
                type="text"
                value={formData.salaryRange}
                onChange={(e) => handleInputChange("salaryRange", e.target.value)}
                placeholder={formData.jobType === "internship" ? "25K/month" : "25LPA-30LPA"}
                className="salary-input"
                required
              />
            </div>
          </div>

          <div className="form-group location-field">
            <label>Location <span className="required">*</span></label>
            <input
              type="text"
              value={formData.location}
              onChange={(e) => handleInputChange("location", e.target.value)}
              placeholder="Bangalore"
            />
          </div>

          <div className="form-group job-description-field">
            <label>Job Description <span className="required">*</span></label>
            <textarea
              value={formData.jobDescription}
              onChange={(e) => handleInputChange("jobDescription", e.target.value)}
              onKeyDown={handleJobDescriptionKeyDown}
              placeholder="About the job\n\nRoles and Responsibilities:\nBuild Customer Empathy: PMs have to regularly meet and understand customer needs first-hand as well as stay on top of the customer pulse via secondary insights - both qualitative and quantitative.\n\nDevise Strategy: Define both long-term strategy and quarterly roadmap to achieve the product vision and create impact."
              rows="10"
            />
          </div>

          <div className="requirements-section non-negotiables-field">
            <div className="section-header">
              <h3>Non-Negotiables</h3>
            </div>
            <div className="requirements-list">
              {formData.nonNegotiables.map((req, index) => (
                <div key={index} className="requirement-item">
                  <input
                    type="text"
                    value={req}
                    onChange={(e) => handleRequirementChange(index, e.target.value)}
                    className="requirement-input"
                  />
                  <button
                    type="button"
                    className="remove-btn"
                    onClick={() => removeRequirement(index)}
                  >
                    -
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="add-requirement-btn red"
              onClick={addRequirement}
            >
              <span>+</span> Add a new Non-Negotiable
            </button>

          </div>

          <div className="form-group required-skills-field">
            <label>Required Skills <span className="optional">(Optional)</span></label>
            
            <div className="skills-field">
              <div className="skills-combobox">
                <div className="skills-dropdown-wrapper">
                  <input
                    type="text"
                    placeholder={
                      formData.requiredSkills.length
                        ? "Type another skill..."
                        : "Type skills, press Enter or comma..."
                    }
                    value={skillSearch}
                    onChange={(e) => {
                      setSkillSearch(e.target.value);
                      setSkillsDropdown(true);
                    }}
                    onFocus={() => setSkillsDropdown(true)}
                    onBlur={() => setTimeout(() => setSkillsDropdown(false), 120)}
                    onKeyDown={handleSkillKeyDown}
                    onPaste={handleSkillPaste}
                    className="skills-search-box"
                  />

                  {skillsDropdown && skillSearch.trim() && (
                    <div className="skills-dropdown">
                      {filteredSkills.length === 0 ? (
                        <div className="dropdown-item disabled">No recognised system skill</div>
                      ) : (
                        filteredSkills.map((skill) => (
                          <button
                            key={skill}
                            className="dropdown-item"
                            onMouseDown={(e) => {
                              e.preventDefault();
                              handleAddSkill(skill);
                            }}
                            type="button"
                          >
                            {skill}
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>

              {formData.requiredSkills.length > 0 && (
                <div className="skills-display" aria-label="Selected required skills">
                  {formData.requiredSkills.map((skill) => (
                    <div key={skill} className="skill-tag">
                      {skill}
                      <button
                        className="skill-remove"
                        onClick={() => handleRemoveSkill(skill)}
                        type="button"
                        title="Remove skill"
                      >
                        x
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {skillWarning && <div className="skills-warning">{skillWarning}</div>}

            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="form-error-message">
            {error}
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="form-actions">
          <button type="button" className="btn-cancel" onClick={onClose} disabled={isBusy}>
            Cancel
          </button>
          <div className="form-actions-right">
            <button
              type="button"
              className="btn-back"
              onClick={handleSaveDraft}
              disabled={isBusy}
              title="Save progress without publishing"
            >
              {isSavingDraft ? "Saving..." : "Save Draft"}
            </button>
            <button 
              type="button" 
              className="btn-submit" 
              onClick={handleSubmit}
              disabled={isBusy}
            >
              {isPublishing ? "Creating..." : isEditingDraft ? "Post Job" : "Create Job"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
