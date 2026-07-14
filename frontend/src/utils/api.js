/**
 * API Layer
 *
 * - Auth and jobs use the configured FastAPI backend.
 * - Jobs use the FastAPI backend
 */

import { clearStoredUser, getStoredToken, getStoredUser } from "../shared/auth/storage";
import { toJobApiPayload } from "../features/jobs/api/jobPayloadMapper";

const DEFAULT_API_BASE_URL = import.meta.env.DEV ? "http://127.0.0.1:8002" : "";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, "");

function getAuthToken() {
  return getStoredToken();
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
    path.startsWith("/auth/signup");
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
      clearStoredUser();
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
 * Authentication API calls.
 */
export const authAPI = {
  health: async () => apiFetch("/health", { timeoutMs: 10000 }),
  signup: async ({ email, password, role, name }) =>
    apiFetch("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, role, name })
    }),
  login: async ({ email, password, role }) =>
    apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, role })
    })
};

/**
 * Job API calls (used by recruiter UI)
 */
export const jobAPI = {
  create: async (data) =>
    apiFetch("/jobs", {
      method: "POST",
      body: JSON.stringify(toJobApiPayload(data, { includeDefaults: true }))
    }),

  getAll: async (filters = {}) => {
    const user = getStoredUser();
    const role = user?.role || user?.userType;
    const mine = role === "recruiter" ? "true" : "false";
    const status = filters?.status ? `&status=${encodeURIComponent(filters.status)}` : "";
    return apiFetch(`/jobs?mine=${mine}${status}`);
  },

  getById: async (id) => apiFetch(`/jobs/${id}`),

  recruiterDashboard: async () => apiFetch("/recruiter/dashboard"),

  recruiterJobs: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters?.status) params.set("status", filters.status);
    if (filters?.includeStats) params.set("include_stats", "true");
    const qs = params.toString();
    return apiFetch(`/recruiter/jobs${qs ? `?${qs}` : ""}`);
  },

  recruiterCandidates: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters?.jobId != null) params.set("job_id", String(filters.jobId));
    if (filters?.status) params.set("status", filters.status);
    if (filters?.sort) params.set("sort", filters.sort);
    if (filters?.page) params.set("page", String(filters.page));
    const qs = params.toString();
    return apiFetch(`/recruiter/candidates${qs ? `?${qs}` : ""}`);
  },

  update: async (id, data) =>
    apiFetch(`/jobs/${id}`, {
      method: "PATCH",
      body: JSON.stringify(toJobApiPayload(data))
    }),

  delete: async (id) =>
    apiFetch(`/jobs/${id}`, {
      method: "DELETE"
    }),

  applyStatus: async (taskId) => apiFetch(`/jobs/apply_status/${taskId}`, { timeoutMs: 20000 }),

  // Candidate: scan resume (no application saved), returns task_id; poll with applyStatus
  scanResumeAsync: async (jobId, file) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch(`/jobs/${jobId}/scan_resume_async`, { method: "POST", body: form, timeoutMs: 120000 });
  },

  applyFromScan: async (jobId, taskId) =>
    apiFetch(`/jobs/${jobId}/apply_from_scan`, {
      method: "POST",
      body: JSON.stringify({ task_id: taskId }),
      timeoutMs: 60000
    }),

  // Candidate: list applied jobs (applications)
  myApplications: async () => apiFetch("/jobs/applied"),

  // Candidate: check whether current candidate already applied to one job
  myApplicationForJob: async (jobId) => apiFetch(`/jobs/${jobId}/my_application`),

  // Candidate + recruiter: one shared application detail flow
  applicationDetails: async (applicationId) => apiFetch(`/jobs/applications/${applicationId}`),

  // Recruiter: update candidate application status without recalculating scores
  updateApplicationStatus: async (applicationId, status) =>
    apiFetch(`/jobs/applications/${applicationId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    }),

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
    apiFetch(`/jobs/applications/${applicationId}`, { method: "DELETE" })
};
