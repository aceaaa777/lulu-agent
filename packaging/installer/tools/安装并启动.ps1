# Lulu 一键安装并启动（Windows）。由“安装并启动 Lulu.cmd”调用；每次都可以双击：第一次补齐缺的东西，之后直接启动。
# 做的事：1) 动画资源包没有就下载并校验  2) 解除“来自网络”的锁定  3) 准备运行环境
#         4) 没有 Ollama 就提示；有 Ollama 但没模型就问要不要现在下载  5) 启动 Lulu
$ErrorActionPreference = 'Continue'  # 出错由脚本自己判断（native 命令的 stderr 在 Stop 模式下会误报）
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
function Say($m) { Write-Host "`n== $m" }
function Fail($m) { Write-Host "`n!! $m"; Read-Host '按回车关闭' | Out-Null; exit 1 }
$Release = @{}
if (Test-Path release.json) { $Release = Get-Content -Raw -Encoding UTF8 release.json | ConvertFrom-Json }
Say "Lulu $($Release.version) $($Release.edition_name)"

# 1) 动画资源包 --------------------------------------------------------------
$Frames = Join-Path $Root 'pet\frames.pck'
if (-not (Test-Path $Frames)) {
  $Url = $Release.frames_url
  if (-not $Url) { Fail '缺少动画资源包 pet\frames.pck，且没有下载地址。请重新下载 Lulu。' }
  Say '动画资源包不在，补下载（约 400MB）…'
  try {
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) { & curl.exe -L --fail --progress-bar -o "$Frames.part" $Url; if ($LASTEXITCODE) { throw 'curl' } }
    else { Invoke-WebRequest -Uri $Url -OutFile "$Frames.part" -UseBasicParsing }
    Move-Item -Force "$Frames.part" $Frames
  } catch { Remove-Item -Force "$Frames.part" -ErrorAction SilentlyContinue; Fail '下载失败。请检查网络后重试，或重新下载 Lulu。' }
}
if (Test-Path 'pet\frames.sha256') {
  $Want = (Get-Content 'pet\frames.sha256' -Raw).Trim().Split(' ')[0].ToLower()
  $Have = (Get-FileHash -Algorithm SHA256 $Frames).Hash.ToLower()
  if ($Want -ne $Have) { Remove-Item -Force $Frames; Fail '动画资源包校验不通过（文件不完整），已删除，请再运行一次重新下载。' }
}

# 2) 解除下载文件的“来自网络”锁定，避免 SmartScreen 反复拦 -----------------------------
Say '准备程序…'
Get-ChildItem -Recurse -File pet, runtime, agent -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue

# 3) 运行环境：优先自带的 runtime；没有就用本机 Python 3.11+ 建 .venv ------------------------
if (Test-Path 'runtime\LuluRuntime\LuluRuntime.exe') {
  $Exe = Join-Path $Root 'runtime\LuluRuntime\LuluRuntime.exe'; $LaunchArgs = @('--root', $Root)
} else {
  Say '这是源码版，需要 Python 3.11 或更新…'
  $Py = Join-Path $Root 'agent\.venv\Scripts\python.exe'
  if (-not (Test-Path $Py)) {
    $Base = $null
    foreach ($c in @('py -3.12', 'py -3.13', 'py -3.11', 'python')) {
      $exe, $arg = $c.Split(' ', 2)
      if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
      $v = & $exe $arg -c 'import sys;print(int(sys.version_info>=(3,11)))' 2>$null
      if ("$v".Trim() -eq '1') { $Base = $c; break }
    }
    if (-not $Base) {
      if (Get-Command winget -ErrorAction SilentlyContinue) {
        Say '没有 Python 3.11+。用 winget 安装 Python 3.12（会弹出确认）…'
        winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
        if (Get-Command py -ErrorAction SilentlyContinue) { $Base = 'py -3.12' }
      }
      if (-not $Base) { Start-Process 'https://www.python.org/downloads/windows/'; Fail '请安装 Python 3.12（勾选 Add to PATH 和 py launcher）后再双击本文件；或改用自带运行环境的安装包。' }
    }
    $exe, $arg = $Base.Split(' ', 2)
    & $exe $arg -m venv (Join-Path $Root 'agent\.venv'); if ($LASTEXITCODE) { Fail '创建虚拟环境失败。' }
  }
  & $Py -c 'import aiohttp,httpx,docx,openpyxl,pypdf,reportlab,jsonschema,filelock' 2>$null
  if ($LASTEXITCODE) {
    Say '安装依赖（一次性）…'
    & $Py -m pip install -q -r agent\requirements.txt -c agent\constraints.txt; if ($LASTEXITCODE) { Fail '依赖安装失败，请把上面的错误发给开发者。' }
  }
  $Exe = $Py; $LaunchArgs = @((Join-Path $Root 'agent\entry.py'), '--root', $Root)
}

# 4) 本地模型（可选：不装也能用 API / claude -p 等后端） ------------------------------------
$OllamaExe = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $OllamaExe) { $local = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'; if (Test-Path $local) { $env:Path = "$(Split-Path $local);$env:Path"; $OllamaExe = Get-Command ollama -ErrorAction SilentlyContinue } }
if (-not $OllamaExe) {
  Say '没有检测到 Ollama（本地模型运行器）。不装也能打开 Lulu，在“设置”页改用 API 等后端。'
  Write-Host '要用本地模型：到 https://ollama.com/download 安装后，再双击本文件即可自动下载模型。'
} else {
  $memGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
  $Need = if ($memGB -ge 12) { 'qwen3:8b' } else { 'qwen3:4b-instruct-2507-q4_K_M' }
  try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null } catch { Start-Process -FilePath 'ollama' -ArgumentList 'serve' -WindowStyle Hidden; Start-Sleep 2 }
  $have = (& ollama list 2>$null) -join "`n"
  if ($have -notmatch [regex]::Escape($Need)) {
    Say "本地模型还没下载（本机内存 ${memGB}GB，需要 $Need，约 2.5–5GB）。"
    $answer = Read-Host '现在下载吗？[Y/n]'
    if ($answer -notmatch '^[nN]') { & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'agent\安装本地模型.ps1') -Tier auto }
  }
}

# 5) 启动 --------------------------------------------------------------------------
Say "启动 Lulu…（日志在 $env:LOCALAPPDATA\Lulu\logs\desktop.log）"
Start-Process -FilePath $Exe -ArgumentList $LaunchArgs -WorkingDirectory $Root -WindowStyle Hidden
Start-Sleep 3
Write-Host '桌宠出现在屏幕右下角；点“聊聊天”打开工作窗口。这个窗口可以关了。'
Start-Sleep 2
