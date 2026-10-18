$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

$repoRoot = if ($env:AIGD_ROOT) { $env:AIGD_ROOT } else { (Resolve-Path (Join-Path $root "..")).Path }
& (Join-Path $repoRoot "env\Scripts\python.exe") -m uvicorn rag.api.main:app --host 127.0.0.1 --port 8001
exit $LASTEXITCODE
