#!/bin/zsh
# Lulu 一键安装并启动（macOS）。每次都可以双击：第一次补齐缺的东西，之后直接启动。
# 做的事：1) 动画资源包没有就下载并校验  2) 给未签名程序去掉隔离标记并本机签名  3) 准备运行环境
#         4) 没有 Ollama 就提示；有 Ollama 但没模型就问要不要现在下载  5) 启动 Lulu
set -u
cd "$(dirname "$0")"
ROOT="$PWD"
export PATH="/Applications/Ollama.app/Contents/Resources:/usr/local/bin:/opt/homebrew/bin:$PATH"
say() { printf '\n== %s\n' "$*"; }
fail() { printf '\n!! %s\n' "$*"; read '?按回车关闭'; exit 1; }
json_field() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],''))" "$1" "$2" 2>/dev/null; }

say "Lulu $(json_field release.json version) $(json_field release.json edition_name)"

# 1) 动画资源包 --------------------------------------------------------------
FRAMES="pet/frames.pck"
if [[ ! -f "$FRAMES" ]]; then
  URL="$(json_field release.json frames_url)"
  [[ -n "$URL" ]] || fail "缺少动画资源包 pet/frames.pck，且没有下载地址。请重新下载 Lulu。"
  say "动画资源包不在，补下载（约 400MB）…"
  curl -L --fail --progress-bar -o "$FRAMES.part" "$URL" || { rm -f "$FRAMES.part"; fail "下载失败。请检查网络后重试，或重新下载 Lulu。"; }
  mv "$FRAMES.part" "$FRAMES"
fi
if [[ -f pet/frames.sha256 ]]; then
  WANT="$(cut -d' ' -f1 pet/frames.sha256)"; HAVE="$(shasum -a 256 "$FRAMES" | cut -d' ' -f1)"
  if [[ "$WANT" != "$HAVE" ]]; then rm -f "$FRAMES"; fail "动画资源包校验不通过（文件不完整），已删除，请再运行一次重新下载。"; fi
fi

# 2) 未签名程序：去隔离标记 + 本机临时签名（不是 App Store 签名，只是让这台电脑允许运行） -------------
say "准备桌宠程序…"
xattr -cr pet runtime 2>/dev/null || true
if [[ -d pet/Lulu.app ]] && ! codesign -v pet/Lulu.app 2>/dev/null; then
  codesign --force --deep --sign - pet/Lulu.app 2>/dev/null || echo "（签名失败，若系统拒绝打开，请到 系统设置 → 隐私与安全性 里允许）"
fi
if [[ -d runtime ]]; then
  find runtime -type f \( -perm -u+x -o -name '*.so' -o -name '*.dylib' \) 2>/dev/null | while read -r f; do
    codesign -v "$f" 2>/dev/null || codesign --force --sign - "$f" 2>/dev/null || true
  done
fi

# 3) 运行环境：优先自带的 runtime；没有就用本机 Python 3.11+ 建 .venv ------------------------
if [[ -x runtime/LuluRuntime/LuluRuntime ]]; then
  LAUNCH=(runtime/LuluRuntime/LuluRuntime --root "$ROOT")
else
  pick_python() {
    for c in python3.12 python3.13 python3.11 /opt/homebrew/bin/python3 /usr/local/bin/python3 \
             /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 python3; do
      if command -v "$c" >/dev/null 2>&1 && [[ "$("$c" -c 'import sys;print(int(sys.version_info>=(3,11)))' 2>/dev/null)" == "1" ]]; then echo "$c"; return; fi
    done
  }
  say "这是源码版，需要 Python 3.11 或更新…"
  if [[ ! -x agent/.venv/bin/python ]]; then
    BASE="$(pick_python || true)"
    [[ -n "$BASE" ]] || fail "没有找到 Python 3.11+。请到 https://www.python.org/downloads/ 安装 3.12 后再双击本文件；或改用自带运行环境的安装包。"
    "$BASE" -m venv agent/.venv || fail "创建虚拟环境失败。"
  fi
  PY=agent/.venv/bin/python
  if ! "$PY" -c "import aiohttp,httpx,docx,openpyxl,pypdf,reportlab,jsonschema,filelock" 2>/dev/null; then
    say "安装依赖（一次性）…"
    "$PY" -m pip install -q -r agent/requirements.txt -c agent/constraints.txt || fail "依赖安装失败，请把上面的错误发给开发者。"
  fi
  LAUNCH=("$PY" agent/entry.py --root "$ROOT")
fi

# 4) 本地模型（可选：不装也能用 API / claude -p 等后端） ------------------------------------
if ! command -v ollama >/dev/null 2>&1; then
  say "没有检测到 Ollama（本地模型运行器）。不装也能打开 Lulu，在“设置”页改用 API 等后端。"
  echo "要用本地模型：到 https://ollama.com/download 安装后，再双击本文件即可自动下载模型。"
else
  MEM_GB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
  if (( MEM_GB >= 12 )); then NEED=qwen3:8b; else NEED=qwen3:4b-instruct-2507-q4_K_M; fi
  if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then open -a Ollama 2>/dev/null || (ollama serve >/dev/null 2>&1 &); sleep 2; fi
  if ! ollama list 2>/dev/null | grep -q "^${NEED}"; then
    say "本地模型还没下载（本机内存 ${MEM_GB}GB，需要 ${NEED}，约 2.5–5GB）。"
    read 'ANSWER?现在下载吗？[Y/n] '
    if [[ "${ANSWER:-Y}" != [nN]* ]]; then zsh agent/安装本地模型.command auto </dev/null || true; fi
  fi
fi

# 5) 启动 --------------------------------------------------------------------------
say "启动 Lulu…（日志在 ~/Library/Application Support/Lulu/logs/desktop.log）"
nohup "${LAUNCH[@]}" >/dev/null 2>&1 &
sleep 3
echo "桌宠出现在屏幕右下角；点“聊聊天”打开工作窗口。这个窗口可以关了。"
