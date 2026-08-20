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

& $VenvPython (Join-Path $ProjectRoot "tools\osm_disaster_pipeline_gui.py")
if ($LASTEXITCODE -ne 0) {
    throw "OSM disaster pipeline GUI failed."
}
