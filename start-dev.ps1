<#
.SYNOPSIS
  One-command local dev startup for the RAG application.

.DESCRIPTION
  1. Starts Docker Desktop (if not already running) and waits for it.
  2. Brings up the infra containers (Postgres, Redis, Qdrant, MinIO) via
     docker-compose.dev.yml.
  3. Starts the FastAPI backend, Celery worker, and Vite frontend, each in
     its own PowerShell window so they keep running independently of this
     script and you can see each one's logs.

.USAGE
  From the repository root:
    .\start-dev.ps1

  First run only (once per machine / fresh DB):
    cd backend
    .venv\Scripts\Activate.ps1
    alembic upgrade head
    $env:ADMIN_PASSWORD = "ChangeMe123!"
    python -m src.scripts.seed_users
#>

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "=== RAG application: starting dev environment ===" -ForegroundColor Cyan

# --- 1. Docker Desktop ---------------------------------------------------
function Test-DockerReady {
    try {
        docker info --format "{{.ServerVersion}}" *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

if (-not (Test-DockerReady)) {
    Write-Host "Docker daemon not responding - launching Docker Desktop..." -ForegroundColor Yellow
    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Start-Process $dockerExe
    } else {
        Write-Host "Could not find Docker Desktop at '$dockerExe'. Start it manually, then re-run this script." -ForegroundColor Red
        exit 1
    }

    Write-Host "Waiting for Docker to become ready (this can take 1-2 minutes)..." -NoNewline
    $deadline = (Get-Date).AddMinutes(3)
    while (-not (Test-DockerReady)) {
        if ((Get-Date) -gt $deadline) {
            Write-Host ""
            Write-Host "Docker did not become ready within 3 minutes. Check Docker Desktop and re-run this script." -ForegroundColor Red
            exit 1
        }
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 5
    }
    Write-Host " ready." -ForegroundColor Green
} else {
    Write-Host "Docker is already running." -ForegroundColor Green
}

# --- 2. Infra containers ---------------------------------------------------
Write-Host "`nStarting infra containers (postgres, redis, qdrant, minio)..." -ForegroundColor Cyan
Push-Location $root
docker compose -f deployment/compose/docker-compose.dev.yml --env-file .env.development up -d postgres redis qdrant minio
Pop-Location

Write-Host "Waiting for infra health checks..." -NoNewline
$deadline = (Get-Date).AddMinutes(2)
while ($true) {
    $statuses = docker compose -f "$root/deployment/compose/docker-compose.dev.yml" --env-file "$root/.env.development" ps --format "{{.Health}}" 2>$null
    if ($statuses -and -not ($statuses -match "starting|unhealthy")) { break }
    if ((Get-Date) -gt $deadline) {
        Write-Host ""
        Write-Host "Infra containers didn't report healthy in time - check 'docker compose ps' manually." -ForegroundColor Yellow
        break
    }
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 3
}
Write-Host " done." -ForegroundColor Green

# --- 3. Backend (FastAPI) ---------------------------------------------------
Write-Host "`nStarting backend (FastAPI, port 8000) in a new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\backend'; .\.venv\Scripts\python.exe -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"
)

# --- 4. Celery worker --------------------------------------------------------
Write-Host "Starting Celery worker in a new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\backend'; .\.venv\Scripts\python.exe -m celery -A src.ingestion.worker.celery_app worker --loglevel=info --pool=solo"
)

# --- 5. Frontend (Vite) -------------------------------------------------------
Write-Host "Starting frontend (Vite, port 5173) in a new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\frontend'; npm run dev"
)

Write-Host "`n=== All services starting ===" -ForegroundColor Cyan
Write-Host "  Frontend:     http://localhost:5173"
Write-Host "  Backend API:  http://localhost:8000"
Write-Host "  API docs:     http://localhost:8000/docs"
Write-Host "  MinIO console:http://localhost:9001"
Write-Host "  Qdrant UI:    http://localhost:6333/dashboard"
Write-Host "`nEach service runs in its own window - close that window (or Ctrl+C in it) to stop it."
Write-Host "To stop the infra containers: docker compose -f deployment/compose/docker-compose.dev.yml --env-file .env.development down"
