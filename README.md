# AI Resume Analyzer

AI Resume Analyzer is a full-stack project with:

- a FastAPI backend in `backend/`
- a React + Vite frontend in `frontend/`

## Scope and System Flow

The MVP supports two roles:

- recruiters create and manage jobs, define required skills, and review ranked applicants
- candidates browse jobs and apply once per job with a PDF or DOCX resume

The primary flow is:

```text
Recruiter creates job
  -> Candidate applies with resume
  -> Text extraction and structured parsing
  -> AI analysis and local embeddings
  -> Semantic and context-based scoring
  -> Explainable candidate ranking
  -> Recruiter dashboard
```

Required skills are always supplied explicitly by the recruiter. They are never
inferred from arbitrary job-description keywords.

## MVP Boundaries

Included:

- recruiter and candidate authentication with JWT role enforcement
- job CRUD and lifecycle management
- job-specific PDF/DOCX applications
- resume extraction, parsing, AI analysis, scoring, and ranking
- candidate and recruiter dashboards

Optional integrations:

- Gemini is the configured hosted AI provider
- local Sentence Transformers provide embeddings
- additional hosted AI providers may be added later, but are not required by the MVP

Explicitly excluded:

- profile-level resume uploads or matching
- interview scheduling, meeting links, calendars, and interview automation
- chatbots and recruiter assistants
- vector databases and cross-encoder reranking

## Non-functional Requirements

- Security: passwords are hashed, private APIs require JWT authentication, and
  recruiter/candidate permissions are enforced server-side.
- Reliability: upload and AI failures return controlled errors without corrupting
  application records.
- Data integrity: MySQL foreign keys and a unique candidate/job constraint prevent
  duplicate applications.
- Performance: common recruiter ranking and candidate history queries use compound
  indexes; generated embeddings and AI responses are cached.
- Maintainability: frontend API calls are centralized and backend responsibilities
  are separated into API, model, service, schema, and utility modules.
- Portability: uploaded-file paths are stored relative to the configured upload
  directory and frontend/backend URLs are configured through environment variables.
- Supported files: PDF and DOCX resumes up to 5 MB.

## Technology

- Frontend: React and Vite
- Backend: Python and FastAPI
- Database: MySQL with SQLAlchemy and PyMySQL
- AI: Gemini plus local Sentence Transformers

## Local Development

Apply database migrations before starting the API:

```bash
cd backend
alembic upgrade head
```

Backend only (port 8002):

```bash
python -m uvicorn --app-dir . backend.app.main:app --reload --host 127.0.0.1 --port 8002
```

Frontend only (port 5173):

```bash
cd frontend
npm install
$env:VITE_API_BASE_URL="http://127.0.0.1:8002"
npm run dev
```

## GitHub Actions

This repo now includes a basic CI workflow in `.github/workflows/ci.yml`.

It currently:

- installs frontend dependencies
- runs frontend lint
- runs frontend build
- installs backend dependencies
- verifies the backend app imports successfully

If you push this repo to GitHub, Actions should run automatically on pushes and pull requests.

## Architecture Notes

- Database schema changes are managed with Alembic in `backend/alembic/`; the FastAPI startup path does not create or alter tables at runtime.
- Long-running resume analysis progress is persisted in the `analysis_tasks` table instead of process memory, so polling survives API restarts and multi-worker deployments.
- Application statuses are normalized through canonical frontend and backend helpers. Valid statuses are `not-reviewed`, `shortlisted`, `on-hold`, and `rejected`.
- Candidate matching enters through `backend/app/services/matching_pipeline.py`, which delegates final scoring to the shared 45/25/20/10 scoring weights in `scoring_service.py`.
- Recruiter dashboard, jobs, and candidates screens use aggregate endpoints instead of per-job browser-side ranking loops:
  - `GET /recruiter/dashboard`
  - `GET /recruiter/jobs?include_stats=true`
  - `GET /recruiter/candidates?job_id=&status=&sort=&page=`
- Frontend shared helpers live under `frontend/src/shared/` for auth storage, status normalization, date formatting, score tones, polling, and skill display normalization.

## Environment Variables

Backend:

```env
DATABASE_URL=
SECRET_KEY=
GEMINI_API_KEY=
FRONTEND_ORIGINS=
```

Frontend:

```env
VITE_API_BASE_URL=http://127.0.0.1:8002
```
