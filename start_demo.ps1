param(
    [string]$Run = "storyft_20261017_seed42",
    [switch]$NoGame,
    [switch]$Recording
)
$ErrorActionPreference = "Stop"
$root = if ($env:AIGD_ROOT) { $env:AIGD_ROOT } else { $PSScriptRoot }
Set-Location -LiteralPath $root
$env:PYTHONUTF8 = "1"

$base = "models/gguf/kanana-2.1b-base-Q4_K_M.gguf"
$adapters = @("rapi", "arona", "ner") | ForEach-Object { "models/gguf/lora_${_}_$Run-f16.gguf" }
foreach ($f in @($base) + $adapters) { if (-not (Test-Path -LiteralPath $f)) { throw "Missing model file: $f" } }
foreach ($port in 8000, 8083) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "Port $port is already in use." }
}
New-Item -ItemType Directory -Force -Path logs | Out-Null

$llama = Start-Process -FilePath "tools/llama.cpp/bin/llama-server.exe" -PassThru -WindowStyle Minimized -ArgumentList @(
    "-m", $base, "--lora", ($adapters -join ","), "--lora-init-without-apply",
    "--host", "127.0.0.1", "--port", "8083", "-ngl", "99", "-c", "4096", "-np", "1")
$guide = Start-Process -FilePath "env/Scripts/python.exe" -PassThru -WindowStyle Minimized -ArgumentList @(
    "-m", "uvicorn", "server.guide_server:app", "--host", "127.0.0.1", "--port", "8000")

for ($i = 0; $i -lt 60; $i++) {
    try { if ((Invoke-RestMethod http://127.0.0.1:8083/health -TimeoutSec 2).status -eq "ok") { break } } catch { }
    Start-Sleep -Seconds 2
}
Write-Output "llama-server pid $($llama.Id), guide server pid $($guide.Id). 끝낼 때 두 창을 닫거나 Stop-Process -Id $($llama.Id),$($guide.Id)"

if (-not $NoGame) {
    $exe = "unity/AIGuideDemo/Builds/Windows/AIGuideDemo.exe"
    if (-not (Test-Path -LiteralPath $exe)) { throw "Build not found: $exe" }
    if ($Recording) { Start-Process -FilePath $exe -ArgumentList "-recording" } else { Start-Process -FilePath $exe }
}
