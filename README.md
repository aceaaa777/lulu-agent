# Lulu Agent

[English](README.en.md) · [下载安装包](https://github.com/aceaaa777/lulu-agent/releases) · [反馈问题](https://github.com/aceaaa777/lulu-agent/issues)

**一只陪你待在桌面上的小水豚，也帮你处理手边的小事。**

Lulu（噜噜）住在桌面右下角。它会看书、打瞌睡、挥手，也会在晚上提醒你休息。打开旁边的工作窗口，就能让它翻译一段话、整理一份文件、按要点写封邮件，或记下明天要做的事。

它面向日常办公和学习，提供十一项常用任务。默认模型在你自己的电脑上运行，也可以在设置里接入自己的 API 或命令行工具。macOS 和 Windows 各有中文、英文安装包，均包含全部动画和运行环境，**不需要安装 Python**。

## 先选一个包

在 [Releases](https://github.com/aceaaa777/lulu-agent/releases) 中下载与你的系统和语言对应的 ZIP：

| 系统 | 中文界面 | English interface |
| --- | --- | --- |
| macOS · Apple 芯片 / Intel | `Lulu-1.1-macos.zip` | `Lulu-1.1-en-macos.zip` |
| Windows 10/11 · 64 位 | `Lulu-1.1-windows.zip` | `Lulu-1.1-en-windows.zip` |

macOS 包约 500MB，Windows 包约 470MB；每个包都有对应的 `.sha256` 校验文件。中文和英文通过下载不同的包选择，目前没有界面内的语言切换。

**当前验证范围：**中文 macOS 版做过真机完整测试；英文 macOS 版已验证启动并通过演示模型的英文自动化测试，尚未由英语母语用户试用。Windows 两个包由 CI 构建并通过冒烟测试，尚未在真实 Windows 电脑上安装验收。

## 三步开始

1. **完整解压 ZIP**，把整个文件夹放到你想保存的位置，不要在压缩包里直接运行。
2. **双击启动脚本**：中文包是 `安装并启动 Lulu.command`（Mac）或 `安装并启动 Lulu.cmd`（Windows）；英文包是 `Install and start Lulu.command` 或 `Install and start Lulu.cmd`。
3. **选择回答方式**。想在本机运行模型，先安装 [Ollama](https://ollama.com/download)，再按启动提示下载 Qwen3；已有 API 或命令行工具，也可以先打开 Lulu，在“设置 → 模型”里配置。

之后每次双击同一个脚本即可启动。桌宠出现后，点旁边的“聊聊天”打开工作窗口。

### 第一次被系统拦住怎么办

**macOS：**这版没有 Apple 开发者签名与公证。实测首次双击可能提示“无法验证”，只显示“完成”；点“完成”后再双击一次。若仍被拦，可到“系统设置 → 隐私与安全性 → 仍要打开”。安装脚本会移除隔离标记并在本机签名。

**Windows：**这版没有代码签名证书，SmartScreen 可能显示“Windows 已保护你的电脑”。确认下载自本项目后，点“更多信息 → 仍要运行”。

具体步骤和日志位置见包内的 `先看这里.md` / `Start here.md`。

## 试着交给 Lulu 一件事

在输入框上方选一个任务标签，再贴文字或选文件。标签会固定任务类型，并显示相应选项；也可以直接输入需求。

| 任务 | 可以怎么用 |
| --- | --- |
| 翻译 | 贴一段文字或选文件，选择目标语言；长文分段处理。 |
| 总结 | 把内容整理成一句话、几条要点或一段话，直接显示或保存为文档。 |
| 改写润色 | 更自然、更正式、更客气，或精简、扩写、整理成要点、校对错别字和标点。 |
| 问文件 | 选文件，问里面的事；回答附原文引用，没找到时会说明。 |
| 提取成表 | 指定“姓名、日期、金额”等列，把文本中的记录整理成 Excel / CSV。 |
| 按要点写 | 提供要点和材料，起草邮件、通知、周报、会议纪要、说明、计划或清单。没有材料时先问，也可以明确要求空模板。 |
| 转格式 | 在支持的文本、Markdown、Word、PDF、Excel、CSV 等格式间转换；复杂版式不会完整保留。 |
| 记一下 | 记到今天的笔记，或保存为以后聊天时可参考的长期记忆。 |
| 提醒 | 比如“30分钟后提醒我喝水”“每周五下午三点提醒我交周报”。设好后核对回复里的时间。 |
| 查一下 | 按关键词找本地文件，或上网查资料并查看来源。 |
| 聊聊天 | 随便聊聊，Lulu 会参考相关的长期记忆。 |

比如，你可以先选“按要点写”，输入：

> 写封邮件给同学：周五下午三点讨论小组作业，请大家提前读完第二章，地点还没定。

Lulu 会检查部分输出中的数字、日期和原文引用，发现不一致时尝试重做。**这些检查能减少错误，但不能保证回答都正确**；交出去的文件和重要提醒时间，仍值得看一眼。

## 忙的时候帮忙，闲的时候陪着

处理任务时，Lulu 会思考、敲键盘；完成时说“搞定啦”，需要你补充时也会有对应动作。平时可以拖动它、让它陪你看书。启动时它会按你所在城市的天气，用晴、雨或阴的开场打个招呼；城市自动按 IP 查找，也可以手动选择。

没人理它的时候，它会看看两边、挥挥手、闹一会儿脾气，两分钟后自己睡着，睡半小时再醒。晚上六点以后每小时会犯一次困提醒你休息，每运行四小时会讨一次糖。看书和吃糖各有两套动作，轮着来。

工作窗口默认使用“大”号界面，还可选“标准”或“特大”。在文件、记忆、提醒和“没做完的”页面，可以找回产物、管理记下的内容，或继续尚未完成的任务。

聊天中发现的记忆候选，只有你点“记住”才会保存。已存记忆可以修改、删除；删除前请留意界面说明中对相关对话的影响。

## 用哪个模型，由你选

在“设置 → 模型”中配置，并用“检查连接”确认是否可用。

| 回答方式 | 需要准备什么 | 模型请求发往哪里 |
| --- | --- | --- |
| 本地 Qwen3（默认） | Ollama 和本地模型 | 默认在本机处理 |
| OpenAI 兼容 API | 服务地址、模型名称及所需密钥；预设含通义千问、DeepSeek、OpenRouter、LM Studio | 所配置的地址；LM Studio 可在本机运行 |
| Claude 命令行 | 已安装并登录的 `claude -p`，使用自己的订阅 | Anthropic |
| 其他命令行 | 可运行的命令，例如 `codex exec` | 由所选工具决定 |

本地模型按内存自动选择：**16GB 及以上使用 `qwen3:8b`**，约 5GB；以下使用 `qwen3:4b-instruct-2507` 和 `qwen3:4b-thinking-2507` 两个模型，合计约 5GB。安装包包含动画和运行环境，模型需要另行下载。

“深度思考”默认关闭。开启后会多想一会儿，本地 4B / 8B 模型可能需要多等一两分钟。实际速度取决于电脑和任务。

不安装 Ollama 也能打开 Lulu，并配置其他回答方式。外部服务的账号、订阅或 API 费用由对应服务决定。

## 数据放在哪里

对话、笔记、记忆、提醒和生成的文件保存在本机：

- macOS：`~/Library/Application Support/Lulu/`
- Windows：`%LOCALAPPDATA%\Lulu\`

密钥单独存放在该目录下的 `data/secrets.json`，不打进安装包或仓库。程序的本机服务只监听 `127.0.0.1`。

**本地存储不等于完全不联网。**默认本地模型在本机推理；选择外部 API 或命令行服务时，请求及相关资料可能发往所选服务，界面会显示提示。联网搜索会访问搜索服务和网页，城市定位与天气也会访问网络。首次下载模型同样需要联网。

卸载时退出 Lulu，删除安装文件夹即可；数据目录会保留。更新或重新安装程序时，不要删除这份数据目录。

## 使用前知道这些

- 不支持扫描 PDF 的 OCR，也不适合需要保留多栏、嵌套表格等复杂排版的文档转换。
- 小模型可能在长文本、多步任务中出错；找不到或无法核对资料时，Lulu 可能先停下来请你补充。
- 无密钥联网搜索依赖搜索引擎页面，可能慢、失败或随页面变化失效；可配置博查、Tavily 或 Brave 的密钥。
- 提醒只在 Lulu 运行时弹出；关闭期间错过的提醒，会在下次打开时补送。
- 目前没有手机端、语音或多用户功能。
- 8GB 内存、无独显的 Windows 电脑是设计目标，尚未在该配置上完成验收，不能据此承诺流畅度。

## 验证情况

1.0 是 Lulu 的第一个公开版本，1.1 只调整了桌宠的作息。截至 2026-09-11，项目记录的验证范围如下：

| 范围 | 已做的验证 |
| --- | --- |
| 中文 macOS | 在 Apple M5 / 24GB Mac 上完成真机测试，发现的程序问题已修；发布包由开发者再次双击验证启动。 |
| 英文 macOS | 开发者验证启动；演示模型端到端测试覆盖提醒增删查看、翻译、总结、问文件、记一下和聊天；尚无英语母语用户试用。 |
| 中文 / 英文 Windows | CI 构建及冻结运行环境冒烟测试通过；尚未在真实 Windows 机器安装验收。 |
| 自动化 | 回归测试在 Windows、macOS CI 上通过；Godot 脚本另有语法和语义检查。桌宠作息由状态机测试覆盖（中文、英文两套源码各 670 项）。 |

如果遇到问题，欢迎到 [Issues](https://github.com/aceaaa777/lulu-agent/issues) 留下系统、包名、操作步骤和报错。日志可能包含个人内容，分享前请先检查。

## 关于这个项目

Lulu 是独立开发者做的开源小项目，希望让普通上班族和学生少花点时间配环境，多一个能帮忙处理日常小事的桌面伙伴。后端使用 Python，桌宠和工作窗口由 Godot 4.4 构建。

代码采用 [MIT 许可证](LICENSE)，第三方组件见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。桌宠动画版权归项目作者。

---

## 给开发者

### 技能表

界面上的十一个标签对应 `lulu/skills.py` 里的技能表：翻译、总结、改写润色、问文件、提取成表、按要点写、转格式、记一下、提醒（`lulu/timeparse.py` 解析中文时间与重复，英文包走 `lulu/timeparse_en.py`）、查一下（本地文件 + 联网核对）、聊聊天，外加一个"记忆问答"（我记得什么 / 忘掉某条）。每件事是一条固定程序，模型只在其中一两个槽位出场。路由规则优先（`route_rules()`），决定性句式命中就不调分类模型；问句一律算查询（有搜索钥匙就联网，没资料就按模型知识回答并标注）；生成文档必须先有材料或要点，否则零模型调用直接问；缺槽位（哪个文件、什么格式、什么时间、忘掉哪条）时程序发定向问题，带选项，用户答复后同一任务从原地继续。两件事写在一句里（既要记住又要生成文件）走通用循环兜底。

模型只剩五种提示词：起草、摘要、字段提取、联网事实核对、记忆命名，每种都有 schema 和程序验收（数字必须有来源、原文标签事实必须保留、引用必须逐字命中）。对话结束后程序按原话抽取"值得记住的事"作为候选，用户在记忆页采纳才会存。

### 这一版如何运行

每个任务按阶段推进并逐步落库：`classifying`（一次 schema 约束的意图分类，程序用规则校正）→ `planning`（证据需求与完成条件）→ `gathering`（固定流程、读取用户提到的文件、实时行情适配器）→ `executing`（模型工具循环，每步写入 `task_steps`）→ 验收 → 完成。任一阶段缺少必需信息时进入持久的 `awaiting_input`，用户答复后同一个任务从中断的阶段继续；已生成且哈希未变的产物不会重做。

撰写器返回结构化 JSON（`status / body_markdown / assumptions / questions`），由程序做三层验收：结构、与证据的一致性（统计数值回填、来源事实保留、实时任务必须有适配器或用户证据）、内容（伪正文正则命中时再由模型二选一判别，问卷/确认函/清单/模板类不拦）。撰写器自行确定的口径会写进文档末尾的"口径说明"。

联网走通用检索（`lulu/research.py` + `lulu/websearch.py`）：程序生成 1–3 条查询 → 依次尝试 Bing、DuckDuckGo、百度（无需密钥，可在 config 里调整顺序）→ 并发抓取前几页并提取正文与页面摘要 → 模型只能以"网页原文逐字引用"的形式列出事实，程序逐条核对引用确实出现在该网页里，核对不过的一律丢弃 → 撰写器只拿核对过的事实写作 → 正文里每个数字都必须来自核对过的原文或用户原话，否则打回重写；口头回答同理，含无来源数字的回答会被程序按核对过的事实重写并附来源。搜索失败按网络不通、引擎拒绝访问（需人工验证）、无结果、网页抓取失败、找不到可核对内容分类，用户可选择换个说法、上传资料或改为模板。

超时与上下文预算由 `lulu/budget.py` 按实测速度推导（`POST /api/budget/measure`），内存低于 12GB 的机器自动落到 A 档（4096 上下文、更短提示词）。

### 目录

- `lulu/loop.py` 循环与阶段；`lulu/intent.py` 意图；`lulu/writer.py` 起草与验收；`lulu/tools.py` 本地能力；`lulu/models.py` 模型适配器（Ollama / OpenAI 兼容）；`lulu/budget.py` 预算；`lulu/research.py` 联网检索与事实核对；`lulu/websearch.py` 搜索引擎与抓取；`lulu/store.py` SQLite（FTS5 记忆检索、精准删除、任务步骤与证据）；`lulu/server.py` 本机 API。
- `desktop/` Godot 窗口与桌宠：工作窗口的对话页有标签行（翻译 · 总结 · 改写润色 · 问文件 · 提取成表 · 按要点写 · 转格式 · 记一下 · 提醒 · 查一下 · 聊聊天）+ 选文件；点标签锁定技能。只有桌面版，没有浏览器面板。
- `tests/` 脚本模型回归；`tests/live_acceptance.py` 真实模型验收（低配报告 6 用例 + 两次原始失败 + 续办）。

### 开发环境

Python 3.11+，`pip install -r requirements.txt -c constraints.txt`；本地模型用 `安装本地模型.command`（Mac）或 `安装本地模型.cmd`（Windows）按内存拉 Qwen3 档位。走 API / `claude -p` / 其他命令行时不需要 Ollama。

```
python3 -m pytest tests -q                 # 脚本模型回归，无需 Ollama
python3 tests/live_acceptance.py           # 真实模型验收（断网也可跑，实时用例会验证"正确暂停"）
python3 tests/live_acceptance.py --online  # 联网：BTC 各平台价格 Word、带来源的问答、技术事实问答
python3 -m lulu.websearch 今日BTC价格        # 看每个搜索引擎在这台机器上能否用、抓到什么；解析失败的页面存到 ./search-debug
```

### 配置：接自己的模型

Lulu 的"壳"（桌宠 + 工作窗口 + 后端）和模型是分开的，模型是一个设置。装好后不下载本地模型也能用，四种后端任选：

| 后端 | 用法 | 资料去向 |
| --- | --- | --- |
| 本地模型（默认） | Ollama 上的 Qwen3，按内存自动选 4B / 8B 档 | 全在本机 |
| API 接口 | 任何 OpenAI 兼容接口。预设了通义千问（百炼 / 国际站）、DeepSeek、OpenRouter、LM Studio（本机） | 发给接口所在的服务商 |
| Claude 命令行 | 本机的 `claude -p`，用你自己的订阅登录 | 发给 Anthropic |
| 其他命令行 | 任意命令，比如 `codex exec`；提示词从参数或标准输入进，回答从文件或标准输出出 | 由那个工具决定 |

**在界面里改**：工作窗口 → 设置 → 模型页，选后端、填地址 / 模型名 / 钥匙，点"检查连接"，能答一句话就算通。切换在当前任务结束后生效；"深度思考"开关随时可调。选了会把资料发出去的后端，界面会明说。

**改配置文件**：设置存在数据目录的 `config.json`（macOS `~/Library/Application Support/Lulu/`，Windows `%LOCALAPPDATA%\Lulu\`），钥匙单独在 `data/secrets.json`（权限 0600，不进配置、不进包）。例如接 DeepSeek：

```json
{"backend": "api", "api": {"preset": "deepseek", "base": "https://api.deepseek.com/v1", "model": "deepseek-chat", "thinking_model": "deepseek-reasoner"}}
```

**命令行（源码运行时）**：`python -m lulu.backends` 提供 `status`（当前配置）、`probe`（四种后端 + 联网搜索哪个能用）、`set`、`secret`、`models`。数据目录用环境变量 `LULU_HOME` 指定，不给就用仓库目录。

```
python -m lulu.backends set backend=api api.preset=openrouter api.model=qwen/qwen3-235b-a22b-2507
python -m lulu.backends secret api_key            # 交互输入，不回显；也可 secret api_key sk-xxx
python -m lulu.backends set backend=claude_cli claude_cli.command=claude
python -m lulu.backends set backend=cli "cli.command=codex exec --skip-git-repo-check --output-last-message {output_file}"
python -m lulu.backends set search.provider=tavily && python -m lulu.backends secret tavily_key
python -m lulu.backends probe
```

`cli.command` 里可用占位符 `{output_file}`（回答写到这个文件）；`cli.prompt_via` 取 `arg` / `stdin`，`cli.output` 取 `file` / `stdout`。安装包里的 `后端体检.command|.cmd` 就是 `probe` 的双击版。

本地模型也能只换模型不换后端：`set ollama.instruct=qwen3:8b ollama.thinking=qwen3:8b`（4B 档用两个模型，8B 档一个混合模型加开关）；`ollama.base` 可指向别的机器上的 Ollama。

### 打包

桌宠是 Godot 导出版，动画帧单独打成 `frames.pck`；Python 运行环境用 PyInstaller 冻结；用户拿到的是一个文件夹，双击 `安装并启动 Lulu.command`（macOS）/ `.cmd`（Windows）。每个平台两个包：中文包直接用仓库源码；英文包由 `packaging/localize.py` 按 `packaging/i18n/en.csv` 生成 `build/src-en`（整字面量替换 + 文件改名 + `lulu/lang.py` 置为 `en`），再走同样的导出、冻结、组装。

```
python packaging/extract_strings.py                 # 列出仓库里所有含中文的字面量（改了文案后跑一下，新句子补进 en.csv）
python packaging/localize.py --lang en --out build/src-en
python packaging/export_pet.py                      # 导出桌宠：build/pet/{linux,windows,macos}/ + frames.pck（首次自动下载导出模板 1.2GB）
python packaging/export_pet.py --project build/src-en/desktop --out build/pet-en --targets macos
python packaging/build_release.py --platform macos             # 组装 dist/Lulu-<版本>-macos/ + zip + sha256（--runtime 指向冻结的 LuluRuntime 则不需 Python）
python build/src-en/packaging/build_release.py --platform macos --pet build/pet-en/macos --frames build/pet/frames.pck   # 英文包，名字自动带 -en-
```

`.github/workflows/release.yml`：推 `v*` 标签或手动运行，CI 导出两种语言的桌宠、在 windows/macos 各冻结两种语言的运行环境、组装四个包挂到草稿 Release。动画包放在名为 `assets-v1` 的 Release 里（`gh release create assets-v1 build/pet/frames.pck`）。

### 尚未完成

Windows 真机安装验收（SmartScreen、低配 8GB 机器）；英文包的母语用户试用；付费签名与公证（现在 macOS 第一次双击会被拦一次）；DOCX 转 PDF 仍为文本重建；4B 档在真实低配机上的复测。
