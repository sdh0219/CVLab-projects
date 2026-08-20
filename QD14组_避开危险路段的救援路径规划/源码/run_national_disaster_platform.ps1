$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Write-Host "Starting National Disaster Response Platform..."
Write-Host "URL: http://127.0.0.1:8765"
Write-Host ""

& $Python ".\national_disaster_platform\server.py"
