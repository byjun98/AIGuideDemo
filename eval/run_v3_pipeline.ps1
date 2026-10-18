param([switch]$Resume)
$ErrorActionPreference = "Stop"
$repoRoot = if ($env:AIGD_ROOT) { $env:AIGD_ROOT } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$env:PYTHONUTF8 = "1"
New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot "logs") | Out-Null
& (Join-Path $repoRoot "train/start_retraining.ps1") -Characters @("rapi", "arona", "ner") -Resume:$Resume
if ($LASTEXITCODE -ne 0) { throw "Training failed" }
& (Join-Path $PSScriptRoot "finish_retraining.ps1") -Resume:$Resume
if ($LASTEXITCODE -ne 0) { throw "Export/evaluation failed" }
