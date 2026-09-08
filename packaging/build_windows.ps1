# Run on Windows; the resulting folder includes runtimes for end users.
param(
 [Parameter(Mandatory=$true)][string]$Godot,
 [Parameter(Mandatory=$true)][string]$OllamaFolder,
 [string]$ModelStore="$env:USERPROFILE\.ollama\models",
 [string]$Tier='4b'   # 4b: qwen3:4b-instruct-2507 + qwen3:4b-thinking-2507 (8GB machines); 8b: qwen3:8b hybrid (16GB+)
)
$ErrorActionPreference='Stop'
$Root=Split-Path $PSScriptRoot -Parent
$Output=Join-Path $Root 'dist\Lulu Windows Preview'
Set-Location $Root
if (-not (Test-Path '.venv\Scripts\python.exe')) { py -3.12 -m venv .venv }
$Python=Join-Path $Root '.venv\Scripts\python.exe'
& $Python -m pip install -r requirements.txt -c constraints.txt pyinstaller==6.19.0
if ($LASTEXITCODE) { throw 'Python build dependencies failed' }
& $Godot --headless --path (Join-Path $Root 'desktop') --editor --import
if ($LASTEXITCODE) { throw 'Desktop import failed' }
& $Python -m PyInstaller --noconfirm --name Lulu --onedir --noconsole --distpath build\windows --workpath build\windows-work entry.py
if ($LASTEXITCODE) { throw 'Windows freeze failed' }
New-Item -ItemType Directory -Force $Output | Out-Null
Copy-Item build\windows\Lulu\* $Output -Recurse -Force
New-Item -ItemType Directory -Force "$Output\agent","$Output\runtime" | Out-Null
Copy-Item config.json "$Output\agent" -Force
& $Python packaging\desktop_payload.py desktop (Join-Path $Output 'desktop')
if ($LASTEXITCODE) { throw 'Desktop resource packaging failed' }
Copy-Item $Godot "$Output\runtime\godot.exe" -Force
Copy-Item "$OllamaFolder\*" "$Output\runtime" -Recurse -Force
if ($Tier -eq '8b') { $Tags=@('qwen3:8b') } else { $Tags=@('qwen3:4b-instruct-2507-q4_K_M','qwen3:4b-thinking-2507-q4_K_M') }
New-Item -ItemType Directory -Force "$Output\models\blobs" | Out-Null
foreach ($Tag in $Tags) {
 $Name,$Version=$Tag.Split(':')
 $Manifest=Join-Path $ModelStore "manifests\registry.ollama.ai\library\$Name\$Version"
 if (-not (Test-Path $Manifest)) { throw "本机没有 $Tag，先运行 ollama pull $Tag" }
 $Model=Get-Content -Raw $Manifest | ConvertFrom-Json
 New-Item -ItemType Directory -Force "$Output\models\manifests\registry.ollama.ai\library\$Name" | Out-Null
 Copy-Item $Manifest "$Output\models\manifests\registry.ollama.ai\library\$Name\$Version"
 @($Model.config)+@($Model.layers) | ForEach-Object {
  $Blob=$_.digest.Replace(':','-')
  Copy-Item (Join-Path $ModelStore "blobs\$Blob") "$Output\models\blobs\$Blob" -Force
 }
}
Set-Content -Path "$Output\agent\config.json" -Value (@{backend='ollama';tier=$Tier;think=$false} | ConvertTo-Json) -Encoding UTF8
Copy-Item THIRD-PARTY-NOTICES.md $Output
Write-Host "Built: $Output\Lulu.exe. Validate on a clean Windows machine before release."
