import { useEffect, useMemo, useState } from "react";
import "./CreateJob.css";
import { jobAPI } from "../utils/api";
import { TECH_SKILLS, ALL_SKILLS } from "../utils/skillsList";

const COMMON_SKILLS = [
  "Communication",
  "Teamwork",
  "Problem Solving",
  "Critical Thinking",
  "Time Management",
  "Leadership",
  "Adaptability",
  "Collaboration",
  "Presentation",
  "Stakeholder Management",
  "Project Management",
  "Analytical Thinking"
];

const DEFAULT_FORM_DATA = {
  opportunityType: "job",
  jobTitle: "",
  shortDescription: "",
  jobPostingLink: "",
  startDate: "",
  duration: "",
  applyBy: "",
  minExperienceYears: "",
  jobType: "full-time",
  jobSite: "remote",
  openings: "",
  salaryCurrency: "Rs",
  salaryRange: "",
  perks: {
    joinerBonus: false,
    relocation: false,
    insurance: false,
    pf: false
  },
  location: "",
  jobDescription: "",
  requiredSkills: [],
  nonNegotiables: [
    "Understanding of technology combined with customer-first & business-first thinking.",
    "Comfort working hands-on in a fast-paced start-up environment.",
    "Curiosity about metrics, execution processes, and macro trends."
  ]
};

export default function CreateJob({ onClose, onCreated, draftJobId = null, initialDraft = null }) {
  const isEditingDraft = useMemo(() => Boolean(draftJobId), [draftJobId]);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const isBusy = isPublishing || isSavingDraft;
  const [error, setError] = useState("");
  const [formData, setFormData] = useState(DEFAULT_FORM_DATA);
  const [skillsDropdown, setSkillsDropdown] = useState(false);
  const [showSkillsForm, setShowSkillsForm] = useState(false);
  const [skillSearch, setSkillSearch] = useState("");

  // Helper function to convert ISO date to datetime-local format
  const toDateTimeLocal = (isoString) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${year}-${month}-${day}T${hours}:${minutes}`;
    } catch {
      return "";
    }
  };

  // Helper function to convert datetime-local to ISO string
  const toISOString = (dateTimeLocal) => {
    if (!dateTimeLocal) return null;
    try {
      return new Date(dateTimeLocal).toISOString();
    } catch {
      return null;
    }
  };

  useEffect(() => {
    if (!initialDraft) return;
    const fd = initialDraft?.formData || initialDraft;
    if (fd && typeof fd === "object") {
      // Convert ISO dates to datetime-local format for inputs
      const converted = {
        ...fd,
        shortDescription: fd.shortDescription ?? fd.short_description ?? "",
        startDate: fd.startDate ? toDateTimeLocal(fd.startDate) : "",
        applyBy: fd.applyBy ? toDateTimeLocal(fd.applyBy) : ""
      };
      setFormData((prev) => ({ ...prev, ...converted }));
    }
  }, [initialDraft]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      const dropdown = document.querySelector(".skills-dropdown-wrapper");
      if (dropdown && !dropdown.contains(event.target)) {
        setSkillsDropdown(false);
        setShowSkillsForm(false);
      }
    };

    if (showSkillsForm) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showSkillsForm]);

  const filteredSkills = useMemo(() => {
    if (!skillSearch.trim()) return [];
    return ALL_SKILLS.filter(
      (s) =>
        !formData.requiredSkills.includes(s) &&
        s.toLowerCase().includes(skillSearch.toLowerCase())
    ).slice(0, 15);
  }, [skillSearch, formData.requiredSkills]);

  const handleAddSkill = (skill) => {
    if (!formData.requiredSkills.includes(skill)) {
      setFormData((prev) => ({
        ...prev,
        requiredSkills: [...prev.requiredSkills, skill]
      }));
    }
    setSkillSearch("");
    setSkillsDropdown(false);
    setShowSkillsForm(false);
  };

  const handleRemoveSkill = (skill) => {
    setFormData((prev) => ({
      ...prev,
      requiredSkills: prev.requiredSkills.filter((s) => s !== skill)
    }));
  };

  const commonSkills = useMemo(
    () => COMMON_SKILLS.filter((s) => !formData.requiredSkills.includes(s)),
    [formData.requiredSkills]
  );

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
    if (!formData.jobTitle || !formData.location || !formData.jobDescription || !String(formData.salaryRange || "").trim()) {
      setError("Please fill in all required fields");
      return;
    }

    setIsPublishing(true);
    setError("");

    try {
      // Get user from localStorage
      const user = JSON.parse(localStorage.getItem("user"));
      if (!user || user.userType !== "recruiter") {
        throw new Error("You must be logged in as a recruiter");
      }

      // Prepare data for API
      const jobData = {
        title: formData.jobTitle,
        shortDescription: formData.shortDescription?.trim() || null,
        description: formData.jobDescription,
        location: formData.location,
        salaryRange: formData.salaryRange ? `${formData.salaryCurrency} ${formData.salaryRange}` : null,
        salaryCurrency: formData.salaryCurrency || null,
        opportunityType: formData.opportunityType || null,
        minExperienceYears: formData.minExperienceYears || null,
        jobType: formData.jobType || null,
        jobSite: formData.jobSite || null,
        openings: formData.openings || null,
        perks: formData.perks || null,
        jobPostingLink: formData.jobPostingLink || null,
        start_date: toISOString(formData.startDate),
        duration: formData.duration || null,
        apply_by: toISOString(formData.applyBy),
        status: "active",
        required_skills: formData.requiredSkills || [],
        nonNegotiables: formData.nonNegotiables.filter(req => req.trim() !== "")
      };

      const response = isEditingDraft
        ? await jobAPI.update(draftJobId, {
            ...jobData,
            status: "active",
            draft_data: null,
            draft_step: 1
          })
        : await jobAPI.create(jobData);

      if (response.success) {
        // After successful creation, redirect recruiter back to Jobs page.
        if (onCreated) {
          onCreated(response.job);
          return;
        }
        // Reset form
        setFormData({
          opportunityType: "job",
          jobTitle: "",
          shortDescription: "",
          jobPostingLink: "",
          minExperienceYears: "",
          jobType: "full-time",
          jobSite: "remote",
          openings: "",
          salaryCurrency: "Rs",
          salaryRange: "",
          perks: {
            joinerBonus: false,
            relocation: false,
            insurance: false,
            pf: false
          },
          location: "",
          jobDescription: "",
          nonNegotiables: []
        });
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
      const user = JSON.parse(localStorage.getItem("user"));
      if (!user || user.userType !== "recruiter") {
        throw new Error("You must be logged in as a recruiter");
      }

      const jobData = {
        title: formData.jobTitle?.trim() ? formData.jobTitle : "Untitled Draft",
        shortDescription: formData.shortDescription?.trim() || null,
        description: formData.jobDescription?.trim() ? formData.jobDescription : null,
        location: formData.location?.trim() ? formData.location : null,
        salaryRange: formData.salaryRange ? `${formData.salaryCurrency} ${formData.salaryRange}` : null,
        salaryCurrency: formData.salaryCurrency || null,
        opportunityType: formData.opportunityType || null,
        minExperienceYears: formData.minExperienceYears || null,
        jobType: formData.jobType || null,
        jobSite: formData.jobSite || null,
        openings: formData.openings || null,
        perks: formData.perks || null,
        jobPostingLink: formData.jobPostingLink || null,
        start_date: toISOString(formData.startDate),
        duration: formData.duration || null,
        apply_by: toISOString(formData.applyBy),
        required_skills: formData.requiredSkills || [],
        status: "draft",
        draft_data: { formData },
        draft_step: 1
      };

      const response = isEditingDraft ? await jobAPI.update(draftJobId, jobData) : await jobAPI.create(jobData);
      if (response.success) {
        // Redirect immediately (avoid blocking `alert()` which pauses navigation).
        onCreated?.(response.job, { to: "drafts" });
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
      <button type="button" className="job-back-btn" onClick={onClose}>
        <span>{"<-"}</span> Back
      </button>
      
      <div className="job-card">
        {/* Header */}
        <div className="form-header">
          <h2>
            Create New Job Posting
          </h2>
        </div>

        <div className="form-step">
          <h3 className="section-title">Job Details</h3>
          <div className="form-group">
            <label>Job Title <span className="required">*</span></label>
            <input
              type="text"
              value={formData.jobTitle}
              onChange={(e) => handleInputChange("jobTitle", e.target.value)}
              placeholder="Product Manager II"
            />
          </div>

          <div className="form-group">
            <label>Short Description</label>
            <input
              type="text"
              value={formData.shortDescription}
              onChange={(e) => handleInputChange("shortDescription", e.target.value)}
              placeholder="Backend-focused role with cloud and API work"
            />
          </div>

          <div className="form-group">
            <label>Job Posting Link (optional)</label>
            <input
              type="url"
              value={formData.jobPostingLink}
              onChange={(e) => handleInputChange("jobPostingLink", e.target.value)}
              placeholder="https://www.linkedin.com/jobs/view/4273598104"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Start Date</label>
              <input
                type="datetime-local"
                value={formData.startDate}
                onChange={(e) => handleInputChange("startDate", e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Duration</label>
              <input
                type="text"
                value={formData.duration}
                onChange={(e) => handleInputChange("duration", e.target.value)}
                placeholder="e.g., 6 months, 1 year, Permanent"
              />
            </div>
            <div className="form-group">
              <label>Apply By</label>
              <input
                type="datetime-local"
                value={formData.applyBy}
                onChange={(e) => handleInputChange("applyBy", e.target.value)}
              />
            </div>
          </div>

          <div className="form-row">
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
            <div className="form-group">
              <label>Number of Openings</label>
              <input
                type="number"
                min="1"
                step="1"
                value={formData.openings}
                onChange={(e) => handleInputChange("openings", e.target.value)}
                placeholder="1"
              />
            </div>
          </div>

          <div className="form-row">
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

          <div className="form-group">
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

          <div className="form-group">
            <label>Location <span className="required">*</span></label>
            <input
              type="text"
              value={formData.location}
              onChange={(e) => handleInputChange("location", e.target.value)}
              placeholder="Bangalore"
            />
          </div>

          <div className="form-group">
            <label>Job Description <span className="required">*</span></label>
            <textarea
              value={formData.jobDescription}
              onChange={(e) => handleInputChange("jobDescription", e.target.value)}
              onKeyDown={handleJobDescriptionKeyDown}
              placeholder="About the job\n\nRoles and Responsibilities:\nBuild Customer Empathy: PMs have to regularly meet and understand customer needs first-hand as well as stay on top of the customer pulse via secondary insights - both qualitative and quantitative.\n\nDevise Strategy: Define both long-term strategy and quarterly roadmap to achieve the product vision and create impact."
              rows="10"
            />
          </div>

          <div className="requirements-section">
            <div className="section-header">
              <h3>Non-Negotiables</h3>
              <span className="ai-badge">AI-extracted and editable</span>
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

          <div className="form-group">
            <label>
              Required Skills <span className="optional">(Optional)</span>
              {formData.requiredSkills.length > 0 && (
                <button 
                  type="button"
                  className="btn-add"
                  onClick={() => setShowSkillsForm(!showSkillsForm)}
                  style={{ marginLeft: "auto" }}
                >
                  + Add Skills
                </button>
              )}
            </label>
            
            <div className="skills-field">
              {formData.requiredSkills.length > 0 && (
                <div className="skills-display">
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

              {formData.requiredSkills.length === 0 && !showSkillsForm && (
                <button 
                  type="button"
                  className="btn-add"
                  onClick={() => setShowSkillsForm(true)}
                >
                  + Add Skills
                </button>
              )}

              <div className="skills-suggested">
                <div className="skills-suggested-title">Common skills</div>
                <div className="skills-suggested-list">
                  {commonSkills.length === 0 ? (
                    <span className="skills-suggested-empty">All common skills added</span>
                  ) : (
                    commonSkills.map((skill) => (
                      <button
                        key={`common-${skill}`}
                        type="button"
                        className="skill-suggestion-btn common"
                        onClick={() => handleAddSkill(skill)}
                      >
                        {skill} <span>+</span>
                      </button>
                    ))
                  )}
                </div>
              </div>

              {showSkillsForm && (
                <div className="skills-dropdown-wrapper">
                  <input
                    type="text"
                    placeholder="Search and add skills..."
                    value={skillSearch}
                    onChange={(e) => setSkillSearch(e.target.value)}
                    onFocus={() => setSkillsDropdown(true)}
                    className="skills-search-box"
                    autoFocus
                  />

                  {skillsDropdown && (
                    <div className="skills-dropdown">
                      {skillSearch.trim() === "" ? (
                        <div className="dropdown-empty">
                          Type to search skills...
                        </div>
                      ) : filteredSkills.length === 0 ? (
                        <div className="dropdown-empty">
                          No skills found
                        </div>
                      ) : (
                        filteredSkills.map((skill) => (
                          <button
                            key={skill}
                            className="dropdown-item"
                            onClick={() => {
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
              )}
            </div>
          </div>
        </div>

        <div className="form-step">
          <h3 className="section-title">Salary & Perks</h3>
          <div className="form-group">
            <label>Perks (optional)</label>
            <div className="option-row">
              <label className="checkbox-option">
                <input
                  type="checkbox"
                  checked={formData.perks.joinerBonus}
                  onChange={(e) => handleInputChange("perks", { ...formData.perks, joinerBonus: e.target.checked })}
                />
                Joining Bonus
              </label>
              <label className="checkbox-option">
                <input
                  type="checkbox"
                  checked={formData.perks.relocation}
                  onChange={(e) => handleInputChange("perks", { ...formData.perks, relocation: e.target.checked })}
                />
                Relocation Bonus
              </label>
              <label className="checkbox-option">
                <input
                  type="checkbox"
                  checked={formData.perks.insurance}
                  onChange={(e) => handleInputChange("perks", { ...formData.perks, insurance: e.target.checked })}
                />
                Health Insurance
              </label>
              <label className="checkbox-option">
                <input
                  type="checkbox"
                  checked={formData.perks.pf}
                  onChange={(e) => handleInputChange("perks", { ...formData.perks, pf: e.target.checked })}
                />
                PF
              </label>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div style={{ 
            padding: "12px", 
            background: "#f8d7da", 
            color: "#721c24", 
            borderRadius: "8px", 
            marginBottom: "16px" 
          }}>
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
