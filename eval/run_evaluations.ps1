param(
    [string]$Dataset = "data\v3\retrain_20261016",
    [string[]]$Characters = @("rapi", "arona", "ner"),
    [float]$Temperature = 0,
    [switch]$Rescore
)
$ErrorActionPreference = "Stop"
$repoRoot = if ($env:AIGD_ROOT) { $env:AIGD_ROOT } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$py = Join-Path $repoRoot "env\Scripts\python.exe"
$logs = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$env:PYTHONUTF8 = "1"
Set-Location -LiteralPath $repoRoot
foreach ($character in $Characters) {
    $sets = @(Get-ChildItem -LiteralPath (Join-Path $Dataset "eval") -Filter "${character}_*.jsonl" | Sort-Object Name)
    if ($sets.Count -eq 0) { throw "No evaluation sets found for $character" }
    foreach ($set in $sets) {
        $suffix = $set.BaseName.Substring($character.Length + 1)
        foreach ($variant in @(@("B", "lora:base"), @("C3", "lora:$character"))) {
            $tempTag = if ($Temperature -eq 0) { "" } else { "t$($Temperature.ToString([cultureinfo]::InvariantCulture).Replace('.', 'p'))_" }
            $tag = "retrain_${character}_$($variant[0])_$tempTag$suffix"
            $arguments = @("-u", "eval/eval_offline.py", "--character", $character, "--model", $variant[1], "--tag", $tag, "--eval", $set.FullName, "--temperature", $Temperature)
            if ($Rescore) { $arguments += "--rescore" }
            & $py @arguments 1> (Join-Path $logs "eval_$tag.out.log") 2> (Join-Path $logs "eval_$tag.err.log")
            if ($LASTEXITCODE -ne 0) { throw "Evaluation failed: $tag (exit $LASTEXITCODE)" }
        }
    }
}
