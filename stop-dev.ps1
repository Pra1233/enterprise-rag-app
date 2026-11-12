<#
.SYNOPSIS
  Stops the infra containers started by start-dev.ps1.
  (The backend/worker/frontend run in their own windows — close those
  windows or Ctrl+C in them to stop those processes.)
#>

$root = $PSScriptRoot
Write-Host "Stopping infra containers (postgres, redis, qdrant, minio)..." -ForegroundColor Cyan
Push-Location $root
docker compose -f deployment/compose/docker-compose.dev.yml --env-file .env.development down
Pop-Location
Write-Host "Done. Data volumes were kept (not -v), so your documents/DB persist for next time." -ForegroundColor Green
