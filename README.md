# HireEZ — AI Resume Analyzer

## Project Overview

HireEZ is a full-stack recruitment platform for recruiters and job candidates. Recruiters create jobs, define explicit required skills, and review ranked applications; candidates browse active jobs, scan a PDF or DOCX resume, and apply once per job. The backend extracts and structures resume content, generates AI-assisted insights, compares the resume with the job using local transformer embeddings, and stores one final match score for both dashboards. The result is a role-based workflow with transparent strengths, weaknesses, skill matches, recommendations, and application statuses.

## Problem Statement

Manual resume screening is slow, inconsistent, and difficult to scale across multiple job openings. Keyword-only filtering can miss relevant candidates whose resumes describe equivalent experience using different language. Recruiters also need more context than a single opaque score, while candidates need a clear view of their application outcome. HireEZ combines structured resume parsing, explicit recruiter requirements, semantic similarity, deterministic scoring, and Gemini-generated explanations. Scores and analysis are persisted with each application so recruiter and candidate views remain consistent and ranking does not depend on browser-side recalculation.

## Features

- **Authentication and authorization:** bcrypt password hashing, JWT access tokens, and recruiter/candidate route enforcement.
- **Job management:** recruiters can create, view, update, draft, activate, and delete jobs with required skills, compensation, location, experience, and non-negotiables.
- **Candidate portal:** candidates can browse active jobs, scan a resume before applying, track applications, view stored scores, and withdraw applications.
- **Resume processing:** validates PDF/DOCX uploads up to 5 MB, extracts text with PyMuPDF or python-docx, cleans noisy text, and rejects empty or scanned PDFs with a controlled error.
- **Structured parsing:** rule-based section detection plus spaCy signals extract skills, experience, projects, education, certifications, and achievements; skill aliases are normalized and deduplicated.
- **AI analysis:** Gemini produces structured candidate summaries, strengths, weaknesses, recommendations, and detailed reasoning, with timeout, retry, validation, and fallback handling.
- **Semantic matching:** `BAAI/bge-small-en-v1.5` Sentence Transformer embeddings and cosine similarity compare resume and job meaning.
- **Explainable scoring:** one stored score combines skills (45%), semantic similarity (25%), experience (20%), and AI recommendation (10%), with a reusable score breakdown.
- **Recruiter dashboard:** aggregate metrics, job-level statistics, filtering, stored-score ranking, application details, and `shortlisted`, `on-hold`, or `rejected` status updates.
- **Reliability and CI:** persistent analysis-task progress, database constraints, centralized error handling, frontend lint/build checks, and a MySQL-backed backend schema check in GitHub Actions.

## Architecture

### High-Level Architecture

```mermaid
flowchart LR
    U[Recruiter or Candidate] --> UI[React + Vite SPA]
    UI -->|REST + JWT| API[FastAPI API]
    API --> AUTH[Auth and role checks]
    API --> JOBS[Job and application services]
    JOBS --> FILES[PDF/DOCX storage and extraction]
    FILES --> PARSER[Rule-based parser + spaCy]
    PARSER --> AI[Gemini analysis]
    PARSER --> EMB[BGE local embeddings]
    EMB --> MATCH[Cosine similarity]
    AI --> SCORE[Weighted scoring pipeline]
    MATCH --> SCORE
    SCORE --> DB[(MySQL)]
    AUTH --> DB
    JOBS --> DB
    DB --> API
```

### Job Creation

```mermaid
sequenceDiagram
    actor R as Recruiter
    participant UI as React UI
    participant API as FastAPI
    participant DB as MySQL
    R->>UI: Enter job details and required skills
    UI->>API: POST /jobs with JWT
    API->>API: Validate recruiter role and payload
    API->>DB: Store job
    DB-->>API: Job record
    API-->>UI: Created job
```

### Resume Scan and Application

```mermaid
sequenceDiagram
    actor C as Candidate
    participant UI as React UI
    participant API as FastAPI
    participant P as Resume pipeline
    participant DB as MySQL
    C->>UI: Select PDF or DOCX for a job
    UI->>API: POST /jobs/{id}/scan_resume_async
    API->>P: Validate, store, extract, clean, and parse
    P-->>API: Structured resume and scan result
    API-->>UI: Pollable analysis result
    C->>UI: Apply after scan
    UI->>API: POST /jobs/{id}/apply_from_scan
    API->>DB: Store one candidate/job application
    API-->>UI: Application details
```

### AI Analysis and Scoring

```mermaid
sequenceDiagram
    participant P as Matching pipeline
    participant E as BGE embedder
    participant G as Gemini API
    participant S as Scoring service
    participant DB as MySQL
    P->>E: Embed resume and job text
    E-->>P: Cosine semantic score
    P->>G: Send structured resume and job context
    G-->>P: Summary, strengths, weaknesses, recommendation
    P->>S: Skills, experience, semantic, and AI signals
    S-->>P: Final score and breakdown
    P->>DB: Persist analysis, embeddings, and application score
```

### Recruiter Review

```mermaid
sequenceDiagram
    actor R as Recruiter
    participant UI as React UI
    participant API as FastAPI
    participant DB as MySQL
    R->>UI: Open candidates page
    UI->>API: GET /recruiter/candidates with filters
    API->>DB: Query applications ordered by stored score
    DB-->>API: Ranked candidates and analysis
    API-->>UI: Candidate cards and score breakdowns
    R->>UI: Change application status
    UI->>API: PATCH /jobs/applications/{id}/status
    API->>DB: Store shortlisted, on-hold, or rejected
```

## Tech Stack

| Layer | Implementation |
| --- | --- |
| Frontend | React 19, Vite, React Router, Lucide React, CSS |
| Backend | Python 3.11+, FastAPI, Pydantic, SQLAlchemy, Uvicorn |
| Database | MySQL with PyMySQL |
| Resume processing | PyMuPDF, python-docx, spaCy |
| AI/ML | Gemini API, Sentence Transformers, `BAAI/bge-small-en-v1.5`, PyTorch CPU, NumPy, cosine similarity |
| Security | bcrypt, JWT via python-jose, server-side role checks |
| CI | GitHub Actions: frontend lint/build and backend import/MySQL schema verification |

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 22+
- MySQL 8+
- A Gemini API key for hosted AI analysis

### Setup

```powershell
git clone https://github.com/aimanrazadev/context-based-ai-resume-analyzer-hr-full-stack-software.git
cd context-based-ai-resume-analyzer-hr-full-stack-software

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

cd frontend
npm install
cd ..
```

Create `backend/.env`:

```env
DATABASE_URL=mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/DATABASE_NAME
SECRET_KEY=replace-with-a-strong-secret
GEMINI_API_KEY=your-gemini-api-key
FRONTEND_ORIGINS=http://127.0.0.1:5173
```

Optional frontend override in `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8002
```

Run the backend and frontend in separate terminals. Database tables are created from the SQLAlchemy models during backend startup.

```powershell
# Terminal 1 — backend: http://127.0.0.1:8002
.\.venv\Scripts\python.exe -m uvicorn --app-dir . backend.app.main:app --host 127.0.0.1 --port 8002

# Terminal 2 — frontend: http://127.0.0.1:5173
cd frontend
npm run dev
```

Useful checks:

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

## Non-Functional Requirements

- **Performance:** cached embeddings avoid duplicate model work; recruiter ranking reads stored database scores through aggregate endpoints.
- **Security:** hashed passwords, JWT-protected APIs, server-side role authorization, upload type/size validation, and environment-based secrets.
- **Data integrity:** MySQL foreign keys, unique candidate/job applications, unique cached embeddings, and one AI analysis per application.
- **Reliability:** controlled extraction and AI errors, request timeouts/retries, persistent analysis progress, and global API error handling.
- **Maintainability:** separated API, service, model, schema, utility, and shared frontend layers with centralized API and status helpers.
- **Portability:** configurable origins, API URLs, model settings, upload directory, and database connection.

## Future Improvements

- Add OCR for scanned resumes; the current pipeline detects and rejects scanned PDFs.
- Add Alembic migrations instead of relying on startup-time schema creation.
- Add Redis for distributed caching and background task coordination.
- Containerize the frontend, backend, and MySQL services with Docker Compose.
- Add optional AI-provider adapters and explicit model failover beyond Gemini models.
- Expand automated integration and end-to-end tests for authentication, application, and ranking flows.

> Interview scheduling, calendar integration, meeting links, chatbots, vector databases, and cross-encoder reranking are intentionally outside the current implementation.
