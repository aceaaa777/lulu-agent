#!/bin/zsh
# 装好 Lulu 的本地模型（Qwen3），按这台 Mac 的内存自动选档：
#   16GB 及以上 → 8B 档：qwen3:8b（一个混合模型，深度思考用开关）
#   16GB 以下   → 4B 档：qwen3:4b-instruct-2507 + qwen3:4b-thinking-2507（两个模型）
# 用法：双击运行；或在终端 ./安装本地模型.command 4b|8b 强制指定档位。
set -u
cd "$(dirname "$0")"
export PATH="/Applications/Ollama.app/Contents/Resources:/usr/local/bin:/opt/homebrew/bin:$PATH"

echo "== Lulu 本地模型安装 =="
if ! command -v ollama >/dev/null 2>&1; then
  echo "没有找到 Ollama。"
  if command -v brew >/dev/null 2>&1; then
    echo "用 Homebrew 安装：brew install --cask ollama"
    read '?按回车开始安装（Ctrl+C 取消）'
    brew install --cask ollama || { echo "安装失败，请到 https://ollama.com/download 手动安装后重试。"; read '?按回车关闭'; exit 1; }
  else
    echo "请到 https://ollama.com/download 安装 Ollama，装好后再双击本脚本。"
    open "https://ollama.com/download" 2>/dev/null || true
    read '?按回车关闭'; exit 1
  fi
fi

if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "启动 Ollama…"
  open -a Ollama 2>/dev/null || (ollama serve >/dev/null 2>&1 &)
  for i in {1..40}; do curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break; sleep 0.5; done
fi
curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || { echo "Ollama 没有起来，请手动打开 Ollama 后重试。"; read '?按回车关闭'; exit 1; }

MEM_GB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
TIER="${1:-auto}"
if [[ "$TIER" == "auto" ]]; then
  if (( MEM_GB >= 12 )); then TIER=8b; else TIER=4b; fi
fi
echo "本机内存 ${MEM_GB}GB → 档位 ${TIER}"
if [[ "$TIER" == "8b" ]]; then
  MODELS=(qwen3:8b)
else
  MODELS=(qwen3:4b-instruct-2507-q4_K_M qwen3:4b-thinking-2507-q4_K_M)
fi
for m in "${MODELS[@]}"; do
  echo "拉取 $m …（首次要下载 2.5–5GB）"
  ollama pull "$m" || { echo "拉取 $m 失败，请检查网络后重试。"; read '?按回车关闭'; exit 1; }
done

PY=.venv/bin/python
if [[ -x "$PY" ]]; then
  echo "写入设置并体检…"
  "$PY" -m lulu.backends set backend=ollama tier="$TIER" >/dev/null
  "$PY" -m lulu.backends probe
else
  echo "（还没有 .venv，先双击“从源码启动 Lulu（新Agent）.command”装依赖；设置会在 Lulu 里的“模型”页完成。）"
fi
echo "完成。打开 Lulu 后到“模型”页点“体检”确认。"
read '?按回车关闭'
