#!/usr/bin/env pwsh
# Start PolyTool Studio via Docker Compose and print the URL.
# Usage: .\scripts\studio_docker.ps1

$ErrorActionPreference = "Stop"

$port = if ($env:STUDIO_PORT) { $env:STUDIO_PORT } else { "8765" }

Write-Host ""
Write-Host "  PolyTool Studio  " -ForegroundColor Cyan
Write-Host "  Building and starting containers..." -ForegroundColor DarkGray
Write-Host ""

docker compose up --build -d

Write-Host ""
Write-Host "  Studio is running:" -ForegroundColor Green
Write-Host "    http://localhost:$port" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Stop with: docker compose down" -ForegroundColor DarkGray
Write-Host ""
