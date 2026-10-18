param(
    [Parameter(Mandatory = $true)][int]$WaitForProcess,
    [string]$CompletedCharacter = "arona",
    [string[]]$NextCharacters = @("ner")
)
$ErrorActionPreference = "Stop"
$repoRoot = if ($env:AIGD_ROOT) { $env:AIGD_ROOT } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$stateFile = Join-Path $repoRoot "logs\retrain_20261016_seed42.status.json"
while (Get-Process -Id $WaitForProcess -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 10 }
$state = Get-Content -LiteralPath $stateFile -Raw -Encoding utf8 | ConvertFrom-Json
if ($state.phase -ne "complete" -or -not (Test-Path -LiteralPath (Join-Path $repoRoot "models\lora\${CompletedCharacter}_retrain_20261016_seed42\train_summary.json"))) {
    throw "Previous training did not complete successfully; queued training was not started."
}
& (Join-Path $PSScriptRoot "start_retraining.ps1") -Characters $NextCharacters
