param(
    [string[]]$Characters = @("arona"),
    [string]$Dataset = "data\v3\retrain_20261016",
    [string]$Run = "retrain_20261016_seed42",
    [switch]$DryRun,
    [switch]$Resume,
    [string]$InitRun = "",
    [string]$Lr = ""
)
$ErrorActionPreference = "Stop"
$repoRoot = if ($env:AIGD_ROOT) { $env:AIGD_ROOT } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$py = Join-Path $repoRoot "env\Scripts\python.exe"
$logs = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$env:PYTHONUTF8 = "1"
$env:HF_HOME = Join-Path $repoRoot "cache\hf"
$env:TOKENIZERS_PARALLELISM = "false"
$stateFile = Join-Path $logs "$Run.status.json"
function Save-State($phase, $character, $detail = "") {
    @{ phase = $phase; character = $character; updated = (Get-Date).ToString("o"); pid = $PID; detail = $detail } |
        ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding utf8
}
Add-Type -Namespace AIGuideTraining -Name Wake -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);'
[AIGuideTraining.Wake]::SetThreadExecutionState([uint32]2147483649) | Out-Null
try {
    Set-Location -LiteralPath $repoRoot
    foreach ($character in $Characters) {
        $train = Join-Path $Dataset "sft\${character}_train.jsonl"
        $val = Join-Path $Dataset "sft\${character}_val.jsonl"
        $out = Join-Path $repoRoot "models\lora\${character}_$Run"
        foreach ($file in @($train, $val)) {
            if (-not (Test-Path -LiteralPath $file)) { throw "Missing dataset: $file" }
        }
        if ((Test-Path -LiteralPath (Join-Path $out "adapter_model.safetensors")) -and -not $DryRun) {
            if ($Resume -and (Test-Path -LiteralPath (Join-Path $out "train_summary.json"))) { continue }
            throw "Existing adapter must be preserved: $out"
        }
        Save-State "training" $character
        $provenanceFile = Join-Path $logs "${character}_$Run.provenance.json"
        if (-not (Test-Path -LiteralPath $provenanceFile)) {
            $hashes = @{}
            foreach ($inputFile in @($train, $val, "train/train_lora.py", "data/guide_common.py", "data/character_${character}.json")) {
                $hashes[$inputFile] = (Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash.ToLowerInvariant()
            }
            @{ character = $character; seed = 42; started_kst = (Get-Date).ToString("o"); sha256 = $hashes } |
                ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $provenanceFile -Encoding utf8
        }
        $trainingArgs = @("-u", "train/train_lora.py", "--train", $train, "--val", $val, "--out", $out, "--seed", "42", "--epochs", "2")
        if ($InitRun) {
            $initAdapter = Join-Path $repoRoot "models\lora\${character}_$InitRun"
            if (-not (Test-Path -LiteralPath (Join-Path $initAdapter "adapter_model.safetensors"))) { throw "Missing init adapter: $initAdapter" }
            $trainingArgs += @("--init-adapter", $initAdapter)
        }
        if ($Lr) { $trainingArgs += @("--lr", $Lr) }
        if ($DryRun) { $trainingArgs += "--dry-run" }
        if ($Resume -and -not $DryRun -and (Test-Path -LiteralPath $out)) {
            $checkpoint = Get-ChildItem -LiteralPath $out -Directory -Filter "checkpoint-*" |
                Where-Object { $_.Name -match '^checkpoint-\d+$' } |
                Sort-Object { [int]($_.Name -replace '^checkpoint-', '') } | Select-Object -Last 1
            if ($checkpoint) { $trainingArgs += @("--resume", $checkpoint.FullName) }
        }
        & $py @trainingArgs 1> (Join-Path $logs "${character}_$Run.out.log") 2> (Join-Path $logs "${character}_$Run.err.log")
        if ($LASTEXITCODE -ne 0) { throw "Training failed for $character (exit $LASTEXITCODE). See logs." }
        Save-State "character_complete" $character
    }
    Save-State "complete" ($Characters -join ",")
} catch {
    Save-State "failed" $character $_.Exception.Message
    throw
} finally {
    [AIGuideTraining.Wake]::SetThreadExecutionState([uint32]2147483648) | Out-Null
}
