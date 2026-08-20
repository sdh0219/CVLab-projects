param(
    [Parameter(Mandatory = $true)]
    [string]$Config,

    [switch]$Overwrite,
    [switch]$NoCache,
    [switch]$SkipFetch,
    [switch]$SkipPlanning,
    [switch]$SkipVisual
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BundledPython = "C:\Users\98286\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not [System.IO.Path]::IsPathRooted($Config)) {
    $Config = Join-Path $ProjectRoot $Config
}

if (-not (Test-Path $VenvPython)) {
    if (Test-Path $BundledPython) {
        & $BundledPython -m venv --system-site-packages (Join-Path $ProjectRoot ".venv")
    } else {
        throw "Virtual environment not found and bundled Python is unavailable."
    }
}

$ArgsList = @(
    (Join-Path $ProjectRoot "tools\run_osm_disaster_pipeline.py"),
    "--config",
    $Config
)

if ($Overwrite) { $ArgsList += "--overwrite" }
if ($NoCache) { $ArgsList += "--no-cache" }
if ($SkipFetch) { $ArgsList += "--skip-fetch" }
if ($SkipPlanning) { $ArgsList += "--skip-planning" }
if ($SkipVisual) { $ArgsList += "--skip-visual" }

& $VenvPython @ArgsList
if ($LASTEXITCODE -ne 0) {
    throw "OSM disaster pipeline failed."
}
