$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "../train/start_retraining.ps1") -Characters @("ner")
