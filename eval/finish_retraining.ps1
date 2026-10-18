param(
    [int]$WaitForProcess = 0,
    [string]$Run = "retrain_20261016_seed42",
    [string]$Dataset = "data\v3\retrain_20261016",
    [switch]$Resume,
    [switch]$PreflightOnly
)
$ErrorActionPreference = "Stop"
$repoRoot = if ($env:AIGD_ROOT) { $env:AIGD_ROOT } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$py = Join-Path $repoRoot "env\Scripts\python.exe"
$logs = Join-Path $repoRoot "logs"
$serverExe = Join-Path $repoRoot "tools\llama.cpp\bin\llama-server.exe"
$converter = Join-Path $repoRoot "tools\llama.cpp\src\convert_lora_to_gguf.py"
$base = Join-Path $repoRoot "models\gguf\kanana-2.1b-base-Q4_K_M.gguf"
$baseHf = Join-Path $repoRoot "models\base\kanana-1.5-2.1b-instruct-2505"
$statusFile = Join-Path $logs "$Run.evaluation.status.json"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$env:PYTHONUTF8 = "1"
function Save-Status($phase, $detail = "") {
    @{ phase = $phase; detail = $detail; pid = $PID; updated = (Get-Date).ToString("o") } |
        ConvertTo-Json | Set-Content -LiteralPath $statusFile -Encoding utf8
}
foreach ($file in @($py, $serverExe, $converter, $base, $baseHf, (Join-Path $repoRoot $Dataset))) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing dependency: $file" }
}
if ($PreflightOnly) { Write-Output "Post-training dependencies present; no GPU process started."; return }
$ownedServer = $null
Add-Type -Namespace AIGuideEvaluation -Name Wake -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);'
[AIGuideEvaluation.Wake]::SetThreadExecutionState([uint32]2147483649) | Out-Null
try {
    Save-Status "waiting_for_training"
    while ($WaitForProcess -gt 0 -and (Get-Process -Id $WaitForProcess -ErrorAction SilentlyContinue)) { Start-Sleep -Seconds 15 }
    Set-Location -LiteralPath $repoRoot
    $adapters = @()
    foreach ($character in @("rapi", "arona", "ner")) {
        $adapter = Join-Path $repoRoot "models\lora\${character}_$Run"
        foreach ($name in @("train_summary.json", "adapter_model.safetensors", "adapter_config.json")) {
            if (-not (Test-Path -LiteralPath (Join-Path $adapter $name))) { throw "Incomplete training: $character ($name)" }
        }
        $summary = Get-Content -LiteralPath (Join-Path $adapter "train_summary.json") -Raw -Encoding utf8 | ConvertFrom-Json
        if ($summary.seed -ne 42) { throw "Unexpected training seed: $character" }
        $gguf = Join-Path $repoRoot "models\gguf\lora_${character}_$Run-f16.gguf"
        $manifest = "$gguf.source.json"
        $sourceHash = (Get-FileHash -LiteralPath (Join-Path $adapter "adapter_model.safetensors") -Algorithm SHA256).Hash
        if (Test-Path -LiteralPath $gguf) {
            if (-not $Resume -or -not (Test-Path -LiteralPath $manifest)) { throw "Preserve existing export: $gguf" }
            $existing = Get-Content -LiteralPath $manifest -Raw -Encoding utf8 | ConvertFrom-Json
            if ($existing.adapter_sha256 -ne $sourceHash -or $existing.gguf_sha256 -ne (Get-FileHash -LiteralPath $gguf -Algorithm SHA256).Hash) { throw "Export provenance mismatch: $gguf" }
            $adapters += $gguf
            continue
        }
        Save-Status "exporting" $character
        $partial = "$gguf.partial"
        & $py $converter --base $baseHf --outtype f16 --outfile $partial $adapter 1> (Join-Path $logs "export_${character}_$Run.out.log") 2> (Join-Path $logs "export_${character}_$Run.err.log")
        if ($LASTEXITCODE -ne 0) { throw "Adapter export failed: $character" }
        Move-Item -LiteralPath $partial -Destination $gguf
        @{ adapter_sha256 = $sourceHash; gguf_sha256 = (Get-FileHash -LiteralPath $gguf -Algorithm SHA256).Hash; run = $Run; character = $character } |
            ConvertTo-Json | Set-Content -LiteralPath $manifest -Encoding utf8
        $adapters += $gguf
    }
    if (Get-NetTCPConnection -LocalPort 8083 -State Listen -ErrorAction SilentlyContinue) { throw "Port 8083 is occupied; no existing process was stopped." }
    Save-Status "starting_inference"
    $serverArgs = @("-m", ('"' + $base + '"'), "--host", "127.0.0.1", "--port", "8083", "-c", "4096", "-np", "1", "-ngl", "99")
    $serverArgs += @("--lora", ('"' + ($adapters -join ',') + '"'), "--lora-init-without-apply")
    $ownedServer = Start-Process -FilePath $serverExe -ArgumentList $serverArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "$Run.llama.out.log") -RedirectStandardError (Join-Path $logs "$Run.llama.err.log")
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($ownedServer.HasExited) { throw "Inference server exited before becoming ready." }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8083/health" -TimeoutSec 2
            if ($health.status -eq "ok") { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw "Inference health check timed out." }
    $loaded = Invoke-RestMethod -Uri "http://127.0.0.1:8083/lora-adapters" -TimeoutSec 5
    if ($loaded.Count -ne 3 -or ($loaded.id -join ',') -ne '0,1,2') { throw "Expected three adapters in rapi/arona/ner order." }
    Save-Status "evaluating"
    & (Join-Path $PSScriptRoot "run_evaluations.ps1") -Dataset $Dataset
    if ($LASTEXITCODE -ne 0) { throw "Evaluation failed." }
    Save-Status "evaluating_runtime_diversity"
    & $py (Join-Path $PSScriptRoot "run_runtime_evaluations.py") --dataset $Dataset
    if ($LASTEXITCODE -ne 0) { throw "Runtime diversity evaluation failed." }
    & $py (Join-Path $PSScriptRoot "summarize_v3.py") 1> (Join-Path $logs "$Run.summary.log")
    if ($LASTEXITCODE -ne 0) { throw "Summary failed." }
    Save-Status "complete"
} catch {
    Save-Status "failed" $_.Exception.Message
    throw
} finally {
    if ($ownedServer -and -not $ownedServer.HasExited) { Stop-Process -Id $ownedServer.Id }
    [AIGuideEvaluation.Wake]::SetThreadExecutionState([uint32]2147483648) | Out-Null
}
