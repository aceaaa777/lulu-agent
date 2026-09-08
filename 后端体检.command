#!/bin/zsh
# 检查四种后端（本地 Ollama / API 接口 / claude -p / 其他命令行）和联网搜索哪个能用。
cd "$(dirname "$0")"
export PATH="/Applications/Ollama.app/Contents/Resources:/usr/local/bin:/opt/homebrew/bin:$HOME/.nvm/versions/node/$(ls "$HOME/.nvm/versions/node" 2>/dev/null | tail -1)/bin:$PATH"
if [[ ! -x .venv/bin/python ]]; then echo '还没有 .venv，先双击“从源码启动 Lulu（新Agent）.command”。'; read '?按回车关闭'; exit 1; fi
.venv/bin/python -m lulu.backends probe
echo
echo "改后端：.venv/bin/python -m lulu.backends set backend=ollama|api|claude_cli|cli"
echo "填钥匙：.venv/bin/python -m lulu.backends secret api_key   （或 bocha_key / tavily_key / brave_key）"
echo "试搜索：.venv/bin/python -m lulu.searchapi 今日新闻"
read '?按回车关闭'
