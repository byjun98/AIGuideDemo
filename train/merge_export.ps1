param([string]$Lora = "rapi_guide_r16", [switch]$BaseOnly)
$ErrorActionPreference = "Stop"
$root = if ($env:AIGD_ROOT) { $env:AIGD_ROOT } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$py = "$root\env\Scripts\python.exe"
$conv = "$root\tools\llama.cpp\src\convert_hf_to_gguf.py"
$quant = "$root\tools\llama.cpp\bin\llama-quantize.exe"
$base = "$root\models\base\kanana-1.5-2.1b-instruct-2505"
New-Item -ItemType Directory -Force "$root\models\gguf" | Out-Null

function Check($what) {
  if ($LASTEXITCODE -ne 0) { Write-Error "$what 실패 (exit $LASTEXITCODE)"; exit $LASTEXITCODE }
}

if ($BaseOnly) {
  $name = "kanana-2.1b-base"
  $src = $base
} else {
  $name = "kanana-2.1b-$Lora"
  $src = "$root\models\merged\$Lora"
  if (-not (Test-Path "$root\models\lora\$Lora\adapter_model.safetensors")) {
    Write-Error "LoRA 가중치가 없습니다: $root\models\lora\$Lora"; exit 1
  }
  & $py -c @"
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
base = r'$base'; lora = r'$root\models\lora\$Lora'; out = r'$src'
m = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16, device_map='cpu')
m = PeftModel.from_pretrained(m, lora).merge_and_unload()
m.save_pretrained(out, safe_serialization=True)
AutoTokenizer.from_pretrained(base).save_pretrained(out)
print('merged ->', out)
"@
  Check "LoRA 병합"
}

$f16 = "$root\models\gguf\$name-f16.gguf"
& $py $conv $src --outtype f16 --outfile $f16
Check "GGUF 변환"
& $quant $f16 "$root\models\gguf\$name-Q4_K_M.gguf" Q4_K_M
Check "Q4_K_M 양자화"
Remove-Item $f16
Get-ChildItem "$root\models\gguf" | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB)}}
