/**
 * API Layer
 *
 * - Auth uses the FastAPI backend (default: http://127.0.0.1:8000)
 * - Jobs use the FastAPI backend
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function getStoredUser() {
  try {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function getAuthToken() {
  return getStoredUser()?.token || null;
}

function normalizeApiErrorMessage(raw, status) {
  // Handle string error messages
  if (typeof raw === "string" && raw.trim()) {
    return raw;
  }

  // Handle backend's standardized error format
  if (raw && typeof raw === "object") {
    // Check for error field (from our error_handlers)
    if (typeof raw.error === "string" && raw.error.trim()) {
      return raw.error;
    }
    
    // Check for detail field (FastAPI default)
    if (typeof raw.detail === "string" && raw.detail.trim()) {
      return raw.detail;
    }
    
    // Check for message field
    if (typeof raw.message === "string" && raw.message.trim()) {
      return raw.message;
    }
    
    // Check for msg field (validation errors)
    if (typeof raw.msg === "string" && raw.msg.trim()) {
      return raw.msg;
    }
  }

  // FastAPI validation errors often come back as a list of objects:
  // [{ loc: [...], msg: "...", type: "..." }, ...]
  if (Array.isArray(raw) && raw.length > 0) {
    const first = raw.find((x) => x && typeof x === "object" && typeof x.msg === "string");
    if (first?.msg) {
      // Include field location if available
      if (Array.isArray(first.loc) && first.loc.length > 0) {
        const field = first.loc[first.loc.length - 1];
        return `${field}: ${first.msg}`;
      }
      return first.msg;
    }
    // Try to stringify if we can't parse
    try {
      return JSON.stringify(raw);
    } catch {
      // Fallback to generic message
    }
  }

  // Provide user-friendly messages based on status codes
  const statusMessages = {
    400: "Invalid request. Please check your input.",
    401: "Authentication required. Please log in.",
    403: "Access denied. You don't have permission for this action.",
    404: "Resource not found.",
    409: "This resource already exists.",
    413: "File is too large. Maximum size is 5MB.",
    422: "Validation error. Please check your input.",
    429: "Too many requests. Please try again later.",
    500: "Server error. Please try again later.",
    503: "Service temporarily unavailable. Please try again in a moment."
  };

  return statusMessages[status] || `Request failed (${status})`;
}

async function apiFetch(path, options = {}) {
  const token = getAuthToken();
  const { timeoutMs = 30000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const isAuthEndpoint =
    path === "/health" ||
    path.startsWith("/auth/login") ||
    path.startsWith("/auth/signup") ||
    path.startsWith("/auth/logout");
  const isFormData =
    typeof FormData !== "undefined" && fetchOptions?.body && fetchOptions.body instanceof FormData;

  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        // Don't attach bearer tokens to auth/bootstrap endpoints; avoids confusing 401 handling.
        ...(token && !isAuthEndpoint ? { Authorization: `Bearer ${token}` } : {}),
        ...(fetchOptions.headers || {})
      }
    });
  } catch (err) {
    if (err?.name === "AbortError") {
      throw new Error("Request timed out. Please check your internet connection and try again.");
    }
    // Network errors
    if (err?.message?.includes("fetch")) {
      throw new Error("Unable to connect to server. Please ensure the backend is running.");
    }
    throw new Error(err?.message || "Network error. Please try again.");
  } finally {
    clearTimeout(timeoutId);
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    // ignore
  }

  if (!res.ok) {
    // Only treat 401 as "session expired" when hitting protected endpoints.
    // For /auth/login, a 401 typically means "invalid credentials".
    if (res.status === 401 && !isAuthEndpoint) {
      // Token expired/invalid: clear session and send user back to login.
      try {
        localStorage.removeItem("user");
      } catch {
        // ignore
      }
      try {
        if (window.location) {
          window.location.href = "/login";
        }
      } catch {
        // ignore
      }
      throw new Error("Your session has expired. Please log in again.");
    }
    
    // Extract error message from response
    const raw = data?.error ?? data?.detail ?? data?.message;
    const msg = normalizeApiErrorMessage(raw, res.status);
    
    // Create error object with additional context
    const error = new Error(msg);
    error.status = res.status;
    error.data = data;
    throw error;
  }

  return data;
}

/**
 * Auth API calls (kept for compatibility; UI currently uses local mock login)
 */
export const authAPI = {
  health: async () => apiFetch("/health"),
  signup: async ({ email, password, role, name }) =>
    apiFetch("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, role, name })
    }),
  login: async ({ email, password, role }) =>
    apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, role })
    }),
  logout: async () => ({ success: true })
};

/**
 * Job API calls (used by recruiter UI)
 */
export const jobAPI = {
  create: async (data) =>
    apiFetch("/jobs", {
      method: "POST",
      body: JSON.stringify({
        title: data?.title,
        short_description: data?.shortDescription ?? data?.short_description ?? null,
        description: data?.description,
        location: data?.location ?? null,
        salary_range: data?.salaryRange ?? data?.salary_range ?? null,
        salary_currency: data?.salaryCurrency ?? data?.salary_currency ?? null,
        salary_min: data?.salaryMin ?? data?.salary_min ?? null,
        salary_max: data?.salaryMax ?? data?.salary_max ?? null,
        variable_min: data?.variableMin ?? data?.variable_min ?? null,
        variable_max: data?.variableMax ?? data?.variable_max ?? null,
        opportunity_type: data?.opportunityType ?? data?.opportunity_type ?? null,
        min_experience_years: data?.minExperienceYears ?? data?.min_experience_years ?? null,
        job_type: data?.jobType ?? data?.job_type ?? null,
        job_site: data?.jobSite ?? data?.job_site ?? null,
        openings: data?.openings ?? null,
        perks: data?.perks ?? null,
        non_negotiables: data?.nonNegotiables ?? data?.non_negotiables ?? null,
        additional_preferences: data?.additionalPreferences ?? data?.additional_preferences ?? null,
        screening_availability: data?.screeningAvailability ?? data?.screening_availability ?? null,
        screening_phone: data?.screeningPhone ?? data?.screening_phone ?? null,
        start_date: data?.start_date ?? data?.startDate ?? null,
        duration: data?.duration ?? null,
        apply_by: data?.apply_by ?? data?.applyBy ?? null,
        job_link: data?.jobPostingLink ?? data?.job_link ?? null,
        required_skills: data?.required_skills ?? data?.requiredSkills ?? null,
        status: data?.status ?? "active",
        draft_data: data?.draft_data ?? null,
        draft_step: data?.draft_step ?? 1
      })
    }),

  getAll: async (filters = {}) => {
    const user = getStoredUser();
    const role = user?.role || user?.userType;
    const mine = role === "recruiter" ? "true" : "false";
    const status = filters?.status ? `&status=${encodeURIComponent(filters.status)}` : "";
    return apiFetch(`/jobs?mine=${mine}${status}`);
  },

  getById: async (id) => apiFetch(`/jobs/${id}`),

  update: async (id, data) =>
    apiFetch(`/jobs/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        title: data?.title,
        short_description: data?.shortDescription ?? data?.short_description,
        description: data?.description,
        location: data?.location,
        salary_range: data?.salaryRange ?? data?.salary_range,
        salary_currency: data?.salaryCurrency ?? data?.salary_currency,
        salary_min: data?.salaryMin ?? data?.salary_min,
        salary_max: data?.salaryMax ?? data?.salary_max,
        variable_min: data?.variableMin ?? data?.variable_min,
        variable_max: data?.variableMax ?? data?.variable_max,
        opportunity_type: data?.opportunityType ?? data?.opportunity_type,
        min_experience_years: data?.minExperienceYears ?? data?.min_experience_years,
        job_type: data?.jobType ?? data?.job_type,
        job_site: data?.jobSite ?? data?.job_site,
        openings: data?.openings,
        perks: data?.perks,
        non_negotiables: data?.nonNegotiables ?? data?.non_negotiables,
        additional_preferences: data?.additionalPreferences ?? data?.additional_preferences,
        screening_availability: data?.screeningAvailability ?? data?.screening_availability,
        screening_phone: data?.screeningPhone ?? data?.screening_phone,
        start_date: data?.start_date ?? data?.startDate ?? null,
        duration: data?.duration ?? null,
        apply_by: data?.apply_by ?? data?.applyBy ?? null,
        job_link: data?.jobPostingLink ?? data?.job_link,
        required_skills: data?.required_skills ?? data?.requiredSkills ?? null,
        status: data?.status,
        draft_data: data?.draft_data,
        draft_step: data?.draft_step
      })
    }),

  delete: async (id) =>
    apiFetch(`/jobs/${id}`, {
      method: "DELETE"
    }),

  // Candidate: upload resume for a specific job and get match score + explanation
  applyWithResume: async (jobId, file) => {
    const form = new FormData();
    form.append("file", file);
    // Resume analysis can take longer (OCR, embeddings first-time init, AI retries).
    // Keep UI responsive by allowing a longer request window.
    return apiFetch(`/jobs/${jobId}/apply`, { method: "POST", body: form, timeoutMs: 120000 });
  },

  // Candidate (preferred): start analysis in background and poll progress.
  applyWithResumeAsync: async (jobId, file) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch(`/jobs/${jobId}/apply_async`, { method: "POST", body: form, timeoutMs: 120000 });
  },

  // Candidate: save application (no scoring). Optionally include a resume file.
  applySaveOnly: async (jobId, file) => {
    const form = new FormData();
    if (file) form.append("file", file);
    return apiFetch(`/jobs/${jobId}/apply_save`, { method: "POST", body: form, timeoutMs: 60000 });
  },

  applyStatus: async (taskId) => apiFetch(`/jobs/apply_status/${taskId}`, { timeoutMs: 20000 }),

  // Candidate: scan resume (no application saved), returns task_id; poll with applyStatus
  scanResumeAsync: async (jobId, file) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch(`/jobs/${jobId}/scan_resume_async`, { method: "POST", body: form, timeoutMs: 120000 });
  },

  // Candidate: list applied jobs (applications)
  myApplications: async () => apiFetch("/jobs/applied"),

  // Candidate: check whether already applied to a specific job
  myApplicationForJob: async (jobId) => apiFetch(`/jobs/${jobId}/my_application`),

  // Candidate: application details
  applicationDetails: async (applicationId) => apiFetch(`/jobs/applications/${applicationId}`),

  // Candidate + Recruiter: shared application details
  applicationDetailsShared: async (applicationId) => apiFetch(`/jobs/applications/${applicationId}/shared`),

  // Candidate + Recruiter: download resume for an application (JWT-auth via fetch -> blob)
  downloadApplicationResume: async (applicationId) => {
    const token = getAuthToken();
    if (!token) throw new Error("Session expired. Please log in again.");
    const res = await fetch(`${API_BASE_URL}/jobs/applications/${applicationId}/resume`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) {
      let data = null;
      try {
        data = await res.json();
      } catch {
        // ignore
      }
      const raw = data?.detail ?? data?.message ?? `Download failed (${res.status})`;
      const msg = normalizeApiErrorMessage(raw, res.status);
      throw new Error(msg);
    }
    const blob = await res.blob();
    return blob;
  },

  // Candidate: delete application
  deleteApplication: async (applicationId) =>
    apiFetch(`/jobs/applications/${applicationId}`, { method: "DELETE" }),

  // Recruiter: ranked candidates per job (Module 10)
  rankedCandidates: async (jobId) => apiFetch(`/jobs/${jobId}/ranked_candidates`)
};

/**
 * Resume API calls (candidate resume upload & listing)
 */
export const resumeAPI = {
  listMine: async () => apiFetch("/resumes/mine"),
  upload: async (file) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch("/resumes/upload", { method: "POST", body: form });
  },
  // NOTE: direct URL downloads won't include Authorization header in most browsers.
  // Prefer jobAPI.downloadApplicationResume for application-specific resume downloads.
  downloadUrl: (id) => `${API_BASE_URL}/resumes/${id}/download`,
};

/**
 * Interview API calls (Module 11)
 */
export const interviewAPI = {
  // Recruiter: schedule interview for an application (invite)
  scheduleInterview: async (payload) =>
    apiFetch("/interviews/schedule", { method: "POST", body: JSON.stringify(payload || {}) }),

  // Recruiter: update schedule / notes
  updateInterview: async (interviewId, payload) =>
    apiFetch(`/interviews/${interviewId}`, { method: "PATCH", body: JSON.stringify(payload || {}) }),

  // Recruiter: mark completed + feedback
  completeInterview: async (interviewId, payload) =>
    apiFetch(`/interviews/${interviewId}/complete`, { method: "POST", body: JSON.stringify(payload || {}) }),

  // Recruiter: evaluate outcome + remarks
  evaluateInterview: async (interviewId, payload) =>
    apiFetch(`/interviews/${interviewId}/evaluate`, { method: "POST", body: JSON.stringify(payload || {}) }),

  myInterviews: async () => apiFetch("/interviews/mine"),

  jobInterviews: async (jobId) => apiFetch(`/interviews/job/${jobId}`),

  interviewDetails: async (interviewId) => apiFetch(`/interviews/${interviewId}`),
};
