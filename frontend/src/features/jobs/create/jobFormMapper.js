import { toIsoDate } from "../../../shared/utils/dates";

export const DEFAULT_JOB_FORM_DATA = {
  opportunityType: "job",
  jobTitle: "",
  shortDescription: "",
  applyBy: "",
  minExperienceYears: "",
  jobType: "full-time",
  jobSite: "remote",
  salaryCurrency: "Rs",
  salaryRange: "",
  location: "",
  jobDescription: "",
  requiredSkills: [],
  nonNegotiables: [
    "Candidate should communicate clearly with team members and stakeholders.",
    "Candidate should collaborate well in a team environment.",
    "Candidate should solve problems independently and think critically.",
  ],
};

export function hasRequiredActiveJobFields(formData) {
  return Boolean(
    formData?.jobTitle &&
      formData?.location &&
      formData?.jobDescription &&
      String(formData?.salaryRange || "").trim()
  );
}

export function buildJobFormPayload(formData, status) {
  const isDraft = status === "draft";
  const nonNegotiables = Array.isArray(formData?.nonNegotiables)
    ? formData.nonNegotiables.map((value) => String(value || "").trim()).filter(Boolean)
    : [];

  return {
    title: formData?.jobTitle?.trim() || (isDraft ? "Untitled Draft" : ""),
    shortDescription: formData?.shortDescription?.trim() || null,
    description: formData?.jobDescription?.trim() || null,
    location: formData?.location?.trim() || null,
    salaryRange: formData?.salaryRange
      ? `${formData.salaryCurrency || "Rs"} ${formData.salaryRange}`
      : null,
    salaryCurrency: formData?.salaryCurrency || null,
    opportunityType: formData?.opportunityType || null,
    minExperienceYears: formData?.minExperienceYears || null,
    jobType: formData?.jobType || null,
    jobSite: formData?.jobSite || null,
    apply_by: toIsoDate(formData?.applyBy),
    required_skills: formData?.requiredSkills || [],
    nonNegotiables,
    status,
    draft_data: isDraft ? { formData } : null,
    draft_step: 1,
  };
}

export function toCreateJobResetData() {
  return {
    ...DEFAULT_JOB_FORM_DATA,
    nonNegotiables: [...DEFAULT_JOB_FORM_DATA.nonNegotiables],
    requiredSkills: [],
  };
}
