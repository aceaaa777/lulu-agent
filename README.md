# Lulu Agent 0.5 开发版（技能表）

2026-09-07 起，执行核心是 Lulu 自己的循环（`lulu/loop.py`），不再依赖 DeepSeek Harness、Node 和 nanobot。2026-09-08 起（0.6），**Lulu 是壳，模型是设置**：本地 Ollama（Qwen3 4B 两模型 / 8B 混合）、OpenAI 兼容 API、`claude -p`、任意命令行四种后端一个接口（`lulu/backends.py`），工作窗口“模型”页切换、体检、填钥匙、开关深度思考。记忆、任务、证据、文件全部保存在本机 SQLite 与工作目录。

## 技能表（0.5）

Lulu 只做九件事（0.6 加了翻译），每件事是一条固定程序，模型只在其中一两个槽位出场（`lulu/skills.py`）：转换格式、生成文档、总结/提取、记录（笔记或长期记忆）、提醒/闹钟（`lulu/timeparse.py` 解析中文时间与重复）、查询（本地文件 + 联网核对）、记忆问答（我记得什么 / 忘掉某条）、闲聊。路由规则优先（`route_rules()`），决定性句式命中就不调分类模型；问句一律算查询（有搜索钥匙就联网，没资料就按模型知识回答并标注）；生成文档必须先有材料或要点，否则零模型调用直接问；缺槽位（哪个文件、什么格式、什么时间、忘掉哪条）时程序发定向问题，带选项，用户答复后同一任务从原地继续。两件事写在一句里（既要记住又要生成文件）走通用循环兜底。

模型只剩五种提示词：起草、摘要、字段提取、联网事实核对、记忆命名，每种都有 schema 和程序验收（数字必须有来源、原文标签事实必须保留、引用必须逐字命中）。对话结束后程序按原话抽取"值得记住的事"作为候选，用户在记忆页采纳才会存。

## 这一版如何运行

每个任务按阶段推进并逐步落库：`classifying`（一次 schema 约束的意图分类，程序用规则校正）→ `planning`（证据需求与完成条件）→ `gathering`（固定流程、读取用户提到的文件、实时行情适配器）→ `executing`（模型工具循环，每步写入 `task_steps`）→ 验收 → 完成。任一阶段缺少必需信息时进入持久的 `awaiting_input`，用户答复后同一个任务从中断的阶段继续；已生成且哈希未变的产物不会重做。

撰写器返回结构化 JSON（`status / body_markdown / assumptions / questions`），由程序做三层验收：结构、与证据的一致性（统计数值回填、来源事实保留、实时任务必须有适配器或用户证据）、内容（伪正文正则命中时再由模型二选一判别，问卷/确认函/清单/模板类不拦）。撰写器自行确定的口径会写进文档末尾的"口径说明"。

联网走通用检索（`lulu/research.py` + `lulu/websearch.py`）：程序生成 1–3 条查询 → 依次尝试 Bing、DuckDuckGo、百度（无需密钥，可在 config 里调整顺序）→ 并发抓取前几页并提取正文与页面摘要 → 模型只能以"网页原文逐字引用"的形式列出事实，程序逐条核对引用确实出现在该网页里，核对不过的一律丢弃 → 撰写器只拿核对过的事实写作 → 正文里每个数字都必须来自核对过的原文或用户原话，否则打回重写；口头回答同理，含无来源数字的回答会被程序按核对过的事实重写并附来源。搜索失败按网络不通、引擎拒绝访问（需人工验证）、无结果、网页抓取失败、找不到可核对内容分类，用户可选择换个说法、上传资料或改为模板。

超时与上下文预算由 `lulu/budget.py` 按实测速度推导（`POST /api/budget/measure`），内存低于 12GB 的机器自动落到 A 档（4096 上下文、更短提示词）。

## 目录

- `lulu/loop.py` 循环与阶段；`lulu/intent.py` 意图；`lulu/writer.py` 起草与验收；`lulu/tools.py` 本地能力；`lulu/models.py` 模型适配器（Ollama / OpenAI 兼容）；`lulu/budget.py` 预算；`lulu/research.py` 联网检索与事实核对；`lulu/websearch.py` 搜索引擎与抓取；`lulu/store.py` SQLite（FTS5 记忆检索、精准删除、任务步骤与证据）；`lulu/server.py` 本机 API。
- `desktop/` Godot 窗口与桌宠：工作窗口的对话页有标签行（翻译 · 总结 · 改写润色 · 问文件 · 提取成表 · 按要点写 · 转格式 · 记一下 · 提醒 · 查一下 · 聊聊天）+ 选文件；点标签锁定技能。0.7 起浏览器面板已移除，只有桌面版。
- `tests/` 脚本模型回归；`tests/live_acceptance.py` 真实模型验收（低配报告 6 用例 + 两次原始失败 + 续办）。

## 开发环境

Python 3.11+，`pip install -r requirements.txt -c constraints.txt`；本地模型用 `安装本地模型.command`（Mac）或 `安装本地模型.cmd`（Windows）按内存拉 Qwen3 档位。走 API / `claude -p` / 其他命令行时不需要 Ollama。

```
python3 -m pytest tests -q                 # 脚本模型回归，无需 Ollama
python3 tests/live_acceptance.py           # 真实模型验收（断网也可跑，实时用例会验证"正确暂停"）
python3 tests/live_acceptance.py --online  # 联网：BTC 各平台价格 Word、带来源的问答、技术事实问答
python3 -m lulu.websearch 今日BTC价格        # 看每个搜索引擎在这台机器上能否用、抓到什么；解析失败的页面存到 ./search-debug
python3 run.py                             # 浏览器面板 http://127.0.0.1:8766
```

## 配置

`config.json`（0.6）：`{"backend":"ollama|api|claude_cli|cli","tier":"auto|4b|8b|custom","think":false,"ollama":{…},"api":{"preset":"dashscope","base":…,"model":…,"think_param":"enable_thinking"},"claude_cli":{"command":"claude"},"cli":{"command":"codex exec … {output_file}"},"search":{"provider":"auto|bocha|tavily|brave|engines|none"}}`。旧版 `{"model":"qwen2.5:7b"}` 仍能读（自动当作自定义档位）。钥匙一律存 `data/secrets.json`（0600）：`python -m lulu.backends secret api_key|bocha_key|tavily_key|brave_key`。命令行：`python -m lulu.backends status|probe|models|set backend=api api.preset=deepseek`；`python -m lulu.searchapi 今日新闻` 试搜索。走接口或命令行意味着请求和资料离开本机，状态栏和“模型”页会常驻提示。

## 尚未完成

Windows 安装包与低配实机验收；A 档（3B/4B）模型接入与复测；记忆自动抽取（当前只保存用户明确要求记住的内容）；DOCX 转 PDF 仍为文本重建。
