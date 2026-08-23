param(
  [ValidateSet("llm", "hybrid")]
  [string]$Extractor = "hybrid",
  [int]$MaxChunks = 0
)

if (-not $env:ATLAS_LLM_API_KEY) {
  $secureKey = Read-Host "Enter NVIDIA Build API key for this run" -AsSecureString
  $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
  )
  if (-not $plainKey) {
    Write-Error "No NVIDIA Build API key provided."
    exit 1
  }
  $env:ATLAS_LLM_API_KEY = $plainKey
}

$env:ATLAS_LLM_PROVIDER = "openai_compatible"
$env:ATLAS_LLM_BASE_URL = "https://integrate.api.nvidia.com/v1"
$env:ATLAS_LLM_MODEL = "minimaxai/minimax-m3"
$env:ATLAS_LLM_JSON_MODE = "0"
$env:ATLAS_LLM_MAX_TOKENS = "8192"
$env:ATLAS_LLM_TEMPERATURE = "1"
$env:ATLAS_LLM_TOP_P = "0.95"
$env:ATLAS_LLM_PROGRESS = "1"
$env:ATLAS_LLM_MAX_RETRIES = "5"
$env:ATLAS_LLM_RETRY_SLEEP_SECONDS = "12"
$env:ATLAS_LLM_REQUEST_SLEEP_SECONDS = "2"

$arguments = @(
  "-m", "graphrag_atlas", "index",
  "--extractor", $Extractor,
  "--config", "config/ontology.json",
  "--corpus", "data/corpus/sample",
  "--output", "outputs/graphrag_index"
)

if ($MaxChunks -gt 0) {
  $arguments += @("--max-chunks", "$MaxChunks")
}

Write-Host "NVIDIA Build LLM extraction starting..."
Write-Host "  extractor: $Extractor"
Write-Host "  model: minimaxai/minimax-m3"
Write-Host "  base_url: https://integrate.api.nvidia.com/v1"
Write-Host "  request_sleep_seconds: $env:ATLAS_LLM_REQUEST_SLEEP_SECONDS"
Write-Host "  max_retries: $env:ATLAS_LLM_MAX_RETRIES"
if ($MaxChunks -gt 0) {
  Write-Host "  max_chunks: $MaxChunks"
} else {
  Write-Host "  max_chunks: all"
}
Write-Host "Progress will print one line per chunk."

python @arguments
