$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BundledPython = "C:\Users\98286\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path $VenvPython)) {
    if (Test-Path $BundledPython) {
        & $BundledPython -m venv --system-site-packages (Join-Path $ProjectRoot ".venv")
    } else {
        throw "Virtual environment not found and bundled Python is unavailable."
    }
}

Write-Host "Using Python: $VenvPython"
& $VenvPython (Join-Path $ProjectRoot "src\rescue_planner.py")
& $VenvPython (Join-Path $ProjectRoot "tests\test_rescue_planner.py")

Write-Host ""
Write-Host "Outputs generated in: $(Join-Path $ProjectRoot 'outputs')"
