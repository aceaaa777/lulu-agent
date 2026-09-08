# 装好 Lulu 的本地模型（Qwen3），按这台电脑的内存自动选档：
#   16GB 及以上 → 8B 档：qwen3:8b（一个混合模型，深度思考用开关）
#   16GB 以下   → 4B 档：qwen3:4b-instruct-2507 + qwen3:4b-thinking-2507（两个模型）
# 用法：双击“安装本地模型.cmd”；或 powershell -File 安装本地模型.ps1 -Tier 4b|8b
param([string]$Tier = 'auto')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host '== Lulu 本地模型安装 =='

function Test-Ollama { try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null; return $true } catch { return $false } }

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
  $local = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
  if (Test-Path $local) { $env:PATH = "$(Split-Path $local);$env:PATH"; $ollama = Get-Command ollama -ErrorAction SilentlyContinue }
}
if (-not $ollama) {
  Write-Host '没有找到 Ollama。'
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host '用 winget 安装：winget install Ollama.Ollama'
    Read-Host '按回车开始安装（Ctrl+C 取消）' | Out-Null
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
    $env:PATH = "$(Join-Path $env:LOCALAPPDATA 'Programs\Ollama');$env:PATH"
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
  }
  if (-not $ollama) {
    Write-Host '请到 https://ollama.com/download 安装 Ollama，装好后再运行本脚本。'
    Start-Process 'https://ollama.com/download'
    Read-Host '按回车关闭' | Out-Null; exit 1
  }
}

if (-not (Test-Ollama)) {
  Write-Host '启动 Ollama…'
  Start-Process -FilePath 'ollama' -ArgumentList 'serve' -WindowStyle Hidden
  for ($i = 0; $i -lt 40 -and -not (Test-Ollama); $i++) { Start-Sleep -Milliseconds 500 }
}
if (-not (Test-Ollama)) { Write-Host 'Ollama 没有起来，请手动打开 Ollama 后重试。'; Read-Host '按回车关闭' | Out-Null; exit 1 }

$memGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
if ($Tier -eq 'auto') { if ($memGB -ge 12) { $Tier = '8b' } else { $Tier = '4b' } }
Write-Host "本机内存 ${memGB}GB → 档位 $Tier"
if ($Tier -eq '8b') { $models = @('qwen3:8b') } else { $models = @('qwen3:4b-instruct-2507-q4_K_M', 'qwen3:4b-thinking-2507-q4_K_M') }
foreach ($m in $models) {
  Write-Host "拉取 $m …（首次要下载 2.5–5GB）"
  & ollama pull $m
  if ($LASTEXITCODE) { Write-Host "拉取 $m 失败，请检查网络后重试。"; Read-Host '按回车关闭' | Out-Null; exit 1 }
}

$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path $py) {
  Write-Host '写入设置并体检…'
  & $py -m lulu.backends set backend=ollama "tier=$Tier" | Out-Null
  & $py -m lulu.backends probe
} else {
  Write-Host '（还没有 .venv，先双击“安装依赖.cmd”；设置会在 Lulu 里的“模型”页完成。）'
}
Write-Host '完成。打开 Lulu 后到“模型”页点“体检”确认。'
Read-Host '按回车关闭' | Out-Null
