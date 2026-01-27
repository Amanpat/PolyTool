$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$smokeScript = Join-Path $scriptRoot "smoke\smoke_api_contract.py"

if (-not (Test-Path $smokeScript)) {
  Write-Error "Smoke script not found: $smokeScript"
  exit 1
}

python $smokeScript @args
