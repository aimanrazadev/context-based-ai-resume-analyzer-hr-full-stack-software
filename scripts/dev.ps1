$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonCmd = if (Test-Path $venvPython) { "`"$venvPython`"" } else { "python" }

$backendCommand = "Set-Location '$repoRoot'; `$env:PYTHONPYCACHEPREFIX='$repoRoot\.pycache'; $pythonCmd -m uvicorn --app-dir '$repoRoot' backend.app.main:app --reload --host 127.0.0.1 --port 8000"

Start-Process powershell `
  -ArgumentList "-NoExit", "-Command", $backendCommand `
  -WorkingDirectory $repoRoot `
  -WindowStyle Normal

Set-Location $repoRoot
npm --prefix frontend run dev
