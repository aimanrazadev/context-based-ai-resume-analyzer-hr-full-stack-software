# Graph Report - .  (2026-07-15)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 566 nodes · 1293 edges · 26 communities (25 shown, 1 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 57 edges (avg confidence: 0.78)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `cfb90b81`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- job_handlers.py
- AppliedJobDetails.jsx
- auth_service.py
- resume_parser.py
- application_service.py
- package.json
- _run_scan_task
- ai_service.py
- scoring_service.py
- resume_extractor.py
- Candidates.jsx
- embedding_service.py
- api.js
- CreateJob.jsx
- __init__.py

## God Nodes (most connected - your core abstractions)
1. `Job` - 24 edges
2. `Application` - 21 edges
3. `_run_scan_task()` - 19 edges
4. `apply_from_scan()` - 18 edges
5. `parse_resume_text()` - 18 edges
6. `_job_to_public()` - 16 edges
7. `score_application()` - 16 edges
8. `_application_row()` - 15 edges
9. `create_job()` - 14 edges
10. `_application_details_payload()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `_find_or_create_candidate()` --indirect_call--> `User`  [INFERRED]
  backend/app/api/job_handlers.py → backend/app/models/user.py
- `_run_scan_task()` --indirect_call--> `Candidate`  [INFERRED]
  backend/app/api/job_handlers.py → backend/app/models/candidate.py
- `_run_scan_task()` --indirect_call--> `Job`  [INFERRED]
  backend/app/api/job_handlers.py → backend/app/models/job.py
- `scan_resume_async()` --indirect_call--> `Job`  [INFERRED]
  backend/app/api/job_handlers.py → backend/app/models/job.py
- `_application_row()` --calls--> `factual_candidate_summary_from_resume()`  [INFERRED]
  backend/app/api/recruiter.py → backend/app/services/application_service.py

## Import Cycles
- 3-file cycle: `backend/app/database.py -> backend/app/models/__init__.py -> backend/app/models/job.py -> backend/app/database.py`
- 3-file cycle: `backend/app/database.py -> backend/app/models/__init__.py -> backend/app/models/embedding.py -> backend/app/database.py`
- 3-file cycle: `backend/app/database.py -> backend/app/models/__init__.py -> backend/app/models/analysis_task.py -> backend/app/database.py`
- 3-file cycle: `backend/app/database.py -> backend/app/models/__init__.py -> backend/app/models/ai_resume_analysis.py -> backend/app/database.py`
- 3-file cycle: `backend/app/database.py -> backend/app/models/__init__.py -> backend/app/models/application.py -> backend/app/database.py`
- 3-file cycle: `backend/app/database.py -> backend/app/models/__init__.py -> backend/app/models/candidate.py -> backend/app/database.py`
- 3-file cycle: `backend/app/database.py -> backend/app/models/__init__.py -> backend/app/models/resume.py -> backend/app/database.py`
- 3-file cycle: `backend/app/database.py -> backend/app/models/__init__.py -> backend/app/models/user.py -> backend/app/database.py`

## Communities (26 total, 1 thin omitted)

### Community 0 - "job_handlers.py"
Cohesion: 0.06
Nodes (78): _already_applied_response(), _application_brief_payload(), application_details(), _application_details_payload(), ApplicationStatusUpdate, apply_from_scan(), ApplyFromScanRequest, create_job() (+70 more)

### Community 1 - "AppliedJobDetails.jsx"
Cohesion: 0.07
Nodes (44): App(), CandidateApp(), JobSearch(), SORT_OPTIONS, ApplicationDetailsPage(), AppliedJobDetails(), classifySkillSnapshot(), detailedReasoningText() (+36 more)

### Community 2 - "auth_service.py"
Cohesion: 0.06
Nodes (48): login(), Session, signup(), _normalize_database_url(), Normalize and validate the configured database URL for a MySQL-only backend., _require_mysql_database_url(), db_health(), global_exception_handler() (+40 more)

### Community 3 - "resume_parser.py"
Cohesion: 0.07
Nodes (45): ParsedResumeRaw, ParsedResumeStructured, BaseModel, build_parse_quality_meta(), _canonical_heading(), categorize_skills(), _chunk_section_lines(), _clean_structured_line() (+37 more)

### Community 4 - "application_service.py"
Cohesion: 0.11
Nodes (31): create_database_tables(), health_check(), on_startup(), Health check endpoint., canonical_skill(), classify_required_skills(), contains_skill(), deduplicate_skills() (+23 more)

### Community 5 - "package.json"
Cohesion: 0.05
Nodes (36): eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, dependencies, lucide-react, react, react-dom (+28 more)

### Community 6 - "_run_scan_task"
Cohesion: 0.11
Nodes (32): apply_status(), UploadFile, Scan-only: analyze resume vs job (AI + deterministic) without creating an Applic, Scan-only (no application saved):       - Returns a task_id immediately, _run_scan_task(), scan_resume_async(), _validated_extracted_text(), AnalysisTask (+24 more)

### Community 7 - "ai_service.py"
Cohesion: 0.12
Nodes (26): AIResumeInsight, BaseModel, AIClientError, AIClientHTTPError, AIClientTimeout, gemini_generate_content(), GeminiMeta, _list_models() (+18 more)

### Community 8 - "scoring_service.py"
Cohesion: 0.11
Nodes (29): evaluate_candidate_for_job(), MatchResult, Canonical scoring entry point for application matching., compute_final_score(), _context_tokens(), education_relevance_score(), experience_relevance_score(), extract_job_skill_tokens() (+21 more)

### Community 9 - "resume_extractor.py"
Cohesion: 0.11
Nodes (27): clean_extracted_text(), extract_and_clean_resume_text(), extract_text_from_docx(), extract_text_from_file(), extract_text_from_pdf_pages(), _fix_hyphenation(), _normalize_bullets(), _normalize_newlines() (+19 more)

### Community 10 - "Candidates.jsx"
Cohesion: 0.19
Nodes (17): testApplicationStatus(), testJobPayloadMapping(), testScoreTones(), StatusBadge(), FIELD_MAPPERS, toJobApiPayload(), ACTION_STATUS_OPTIONS, Candidates() (+9 more)

### Community 11 - "embedding_service.py"
Cohesion: 0.16
Nodes (18): embed_text(), _get_embedder(), get_or_create_embedding(), get_or_create_embedding_details(), normalize_text(), Any, Session, Embedding generation and persistence utilities.  This module is responsible fo (+10 more)

### Community 12 - "api.js"
Cohesion: 0.20
Nodes (13): LoginSignup(), AuthProvider(), AuthContext, clearStoredUser(), getStoredRole(), getStoredToken(), getStoredUser(), saveStoredUser() (+5 more)

### Community 13 - "CreateJob.jsx"
Cohesion: 0.21
Nodes (14): buildJobFormPayload(), DEFAULT_JOB_FORM_DATA, hasRequiredActiveJobFields(), toCreateJobResetData(), CreateJob(), NON_MATCHING_SKILL_KEYS, normalizeSkill(), skillKey() (+6 more)

## Knowledge Gaps
- **31 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `parse_resume_text()` connect `resume_parser.py` to `job_handlers.py`, `_run_scan_task`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Why does `get_error_message()` connect `auth_service.py` to `job_handlers.py`, `application_service.py`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `Job` (e.g. with `apply_from_scan()` and `_create_job_embedding_background()`) actually correct?**
  _`Job` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `Application` (e.g. with `application_details()` and `delete_application()`) actually correct?**
  _`Application` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `_run_scan_task()` (e.g. with `Candidate` and `Job`) actually correct?**
  _`_run_scan_task()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `apply_from_scan()` (e.g. with `Job` and `Path`) actually correct?**
  _`apply_from_scan()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _31 weakly-connected nodes found - possible documentation gaps or missing edges._