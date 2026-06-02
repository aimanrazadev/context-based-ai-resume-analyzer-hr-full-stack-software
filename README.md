# AI Resume Analyzer

AI Resume Analyzer is a full-stack project with:

- a FastAPI backend in `backend/`
- a React + Vite frontend in `frontend/`

## Local Development

Backend only:

```bash
python -m uvicorn --app-dir . backend.app.main:app --reload
```

Frontend only:

```bash
cd frontend
npm install
npm run dev
```

Start backend and frontend together from the repo root:

PowerShell:

```powershell
.\scripts\dev.ps1
```

Command Prompt:

```bat
scripts\dev.bat
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
VITE_API_BASE_URL=http://127.0.0.1:8000
```
