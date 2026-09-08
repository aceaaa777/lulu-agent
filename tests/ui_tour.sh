#!/bin/sh
# Render the work window with a canned model and save a screenshot of every page/state to $LULU_SHOTS (default /tmp/lulu-shots).
# Needs: a Godot 4 binary (GODOT env or on PATH), the imported desktop assets, and — on a headless Linux box — xvfb-run.
set -eu
cd "$(dirname "$0")/.."
GODOT="${GODOT:-$(command -v godot || echo /tmp/Godot_v4.4.1-stable_linux.x86_64)}"
HOME_DIR="${LULU_TOUR_HOME:-/tmp/lulu-tour-home}"; rm -rf "$HOME_DIR"; mkdir -p "$HOME_DIR/workspace"
# sample files the tours pick from the file chooser
printf '会议纪要\n日期：2026-09-01\n参会：陆遥、周文、何晴\n决定：项目代号青松731，负责人：陆遥，预算：18650，截止日期：2026-11-23，参与人数：17。\n下一步：周文整理需求，何晴联系供应商。\n' > "$HOME_DIR/workspace/纪要.md"
printf '甲方：青松公司。乙方：陆遥工作室。付款期限：签约后 30 天内付清。违约金：合同总额的 5%%。\n' > "$HOME_DIR/workspace/合同.md"
printf '陆遥 13800000001 预算 18650\n周文 13900000002 预算 9200\n何晴 13700000003 预算 4100\n' > "$HOME_DIR/workspace/名单.md"
printf '# 报告\n\n第一段正文。\n\n第二段，共 3 条。\n' > "$HOME_DIR/workspace/报告.md"
printf '第一章 安装\n把设备接上电源，等待指示灯变绿。\n第二章 使用\n每天使用不超过 3 小时。\n' > "$HOME_DIR/workspace/说明.md"
TOUR="${TOUR:-screenshot_tour}"
PY="${PY:-.venv/bin/python}"
LULU_FAKE_MODEL=1 "$PY" entry.py --server --no-browser --port 8791 --data-dir "$HOME_DIR" >"$HOME_DIR/server.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
for i in $(seq 1 40); do [ -f "$HOME_DIR/data/connection.json" ] && break; sleep 0.25; done
export LULU_CONNECTION="$HOME_DIR/data/connection.json" LULU_SHOTS="${LULU_SHOTS:-/tmp/lulu-shots}"
rm -rf "$LULU_SHOTS"
if command -v xvfb-run >/dev/null 2>&1 && [ -z "${DISPLAY:-}" ]; then
  xvfb-run -a -s "-screen 0 1600x1000x24" "$GODOT" --path desktop --rendering-driver opengl3 -s res://tests/$TOUR.gd 2>&1 | grep -E "SHOT|TOUR|CASE|SCRIPT ERROR" || true
else
  "$GODOT" --path desktop -s res://tests/$TOUR.gd 2>&1 | grep -E "SHOT|TOUR|CASE|SCRIPT ERROR" || true
fi
ls "$LULU_SHOTS"
