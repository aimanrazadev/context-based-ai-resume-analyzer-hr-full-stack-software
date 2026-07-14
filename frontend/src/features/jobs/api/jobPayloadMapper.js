const FIELD_MAPPERS = {
  title: (data) => data?.title,
  short_description: (data) => data?.shortDescription ?? data?.short_description,
  description: (data) => data?.description,
  location: (data) => data?.location,
  salary_range: (data) => data?.salaryRange ?? data?.salary_range,
  salary_currency: (data) => data?.salaryCurrency ?? data?.salary_currency,
  salary_min: (data) => data?.salaryMin ?? data?.salary_min,
  salary_max: (data) => data?.salaryMax ?? data?.salary_max,
  variable_min: (data) => data?.variableMin ?? data?.variable_min,
  variable_max: (data) => data?.variableMax ?? data?.variable_max,
  opportunity_type: (data) => data?.opportunityType ?? data?.opportunity_type,
  min_experience_years: (data) => data?.minExperienceYears ?? data?.min_experience_years,
  job_type: (data) => data?.jobType ?? data?.job_type,
  job_site: (data) => data?.jobSite ?? data?.job_site,
  non_negotiables: (data) => data?.nonNegotiables ?? data?.non_negotiables,
  additional_preferences: (data) => data?.additionalPreferences ?? data?.additional_preferences,
  apply_by: (data) => data?.apply_by ?? data?.applyBy,
  required_skills: (data) => data?.required_skills ?? data?.requiredSkills,
  status: (data) => data?.status,
  draft_data: (data) => data?.draft_data,
  draft_step: (data) => data?.draft_step,
};

export function toJobApiPayload(data, { includeDefaults = false } = {}) {
  const payload = {};

  Object.entries(FIELD_MAPPERS).forEach(([key, mapper]) => {
    const value = mapper(data);
    if (value !== undefined) {
      payload[key] = value;
    } else if (includeDefaults) {
      payload[key] = null;
    }
  });

  if (includeDefaults) {
    payload.status = payload.status ?? "active";
    payload.draft_step = payload.draft_step ?? 1;
  }

  return payload;
}
