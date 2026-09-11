# Lulu Agent

[中文](README.md) · [Download](https://github.com/aceaaa777/lulu-agent/releases) · [Report an issue](https://github.com/aceaaa777/lulu-agent/issues)

**A little capybara on your desktop, ready to keep you company and help with everyday tasks.**

Lulu lives in the bottom-right corner of your screen. It reads, naps, waves hello, and reminds you to rest in the evening. Open its work window to translate a passage, make sense of a file, draft an email from your notes, or remember something for tomorrow.

Built for everyday work and study, Lulu has eleven task tabs. The default model runs on your own computer, and you can also connect your own API or command-line tool. Chinese and English packages are available for macOS and Windows. Every package includes all animations and the runtime. **No Python installation needed.**

## Choose your download

Get the ZIP for your system and language from [Releases](https://github.com/aceaaa777/lulu-agent/releases).

| System | English interface | 中文界面 |
| --- | --- | --- |
| macOS · Apple silicon / Intel | `Lulu-1.1-en-macos.zip` | `Lulu-1.1-macos.zip` |
| Windows 10/11 · 64-bit | `Lulu-1.1-en-windows.zip` | `Lulu-1.1-windows.zip` |

macOS downloads are about 500 MB; Windows downloads are about 470 MB. Each ZIP has a matching `.sha256` checksum file. Choose the language by downloading the corresponding package; there is no language switch in the app yet.

**Testing so far:** the Chinese macOS edition has undergone full testing on a real Mac. The English macOS edition has been launched by the developer and passed automated tests with a demo model, but hasn't been tried by a native English speaker. Both Windows packages are built and smoke-tested in CI; neither has been installed and checked on a real Windows PC yet.

## Get started in three steps

1. **Extract the entire ZIP** and keep the folder together. Don't run Lulu from inside the archive.
2. **Double-click the launcher:** `Install and start Lulu.command` on Mac, or `Install and start Lulu.cmd` on Windows. In the Chinese package, the filename starts with `安装并启动 Lulu`.
3. **Choose how Lulu answers.** For a local model, install [Ollama](https://ollama.com/download) first, then follow the launcher's prompts to download Qwen3. You can also open Lulu without a local model and connect your API or command-line tool under Settings → Model.

Use the same launcher next time. Once the pet appears, click “Chat” beside it to open the work window.

### If your system blocks the first launch

**macOS:** this release is not developer-signed or notarized by Apple. In testing, the first attempt could show a “cannot verify” message with only a “Done” button. Click Done, then try double-clicking again. If it's still blocked, go to System Settings → Privacy & Security → Open Anyway. The installer removes the quarantine flag and signs the app locally.

**Windows:** this release has no code-signing certificate, so SmartScreen may show “Windows protected your PC”. If you downloaded it from this project, choose More info → Run anyway.

See `Start here.md` / `先看这里.md` in your package for details and log locations.

## Give Lulu something to do

Pick a task tab above the message box, then paste some text or choose a file. Each tab fixes the task type and shows its own options. You can also type a request directly.

| Task | What you can do |
| --- | --- |
| Translate | Paste text or choose a file and a target language. Longer texts are translated in sections. |
| Summarize | Get one sentence, a few key points, or a paragraph. Read it in chat or save it as a document. |
| Rewrite | Make text more natural, formal, polite, brief, or detailed. Turn it into bullet points, or fix spelling and punctuation. |
| Ask about a file | Ask a question about a file and get a supporting quote. Lulu tells you when it can't find the answer. |
| Make a table | Choose columns such as Name, Date, and Amount, then extract records into Excel / CSV. |
| Write from notes | Draft emails, notices, weekly reports, meeting notes, explanations, plans, or checklists from your material. Without enough information, Lulu asks first. You can request a blank template instead. |
| Convert | Convert between supported text, Markdown, Word, PDF, Excel, and CSV formats. Complex layouts won't be fully preserved. |
| Remember this | Save something to today's notes or to long-term memory for future chats. |
| Remind me | Try “Remind me to drink water in 30 minutes” or “Remind me every Friday at 3 PM to submit my weekly report”. Check the time shown in the reply. |
| Look it up | Search local files by keyword, or look up information online with sources. |
| Chat | Have a conversation. Lulu can refer to relevant long-term memories. |

For example, choose “Write from notes” and say:

> Write an email to my classmates: let's discuss the group project on Friday at 3 PM. Please read chapter two beforehand. We haven't picked a room yet.

Lulu checks numbers, dates, and source quotations in some outputs and retries when it finds a mismatch. **These checks can reduce mistakes, but don't guarantee a correct answer.** Read important documents and check reminder times before relying on them.

## A little company while you work

Lulu thinks and types while working, celebrates when a task is done, and reacts when it needs more details. Between tasks, you can move it around or let it read beside you. At startup it greets you with a sunny, rainy, or cloudy opening that follows your city's weather. The city is found by IP, or you can choose it yourself.

Left alone, it looks around, waves, sulks for a while, and falls asleep after two minutes, waking half an hour later. From 6 pm it yawns once an hour to remind you to rest, and every four hours of running it asks for a candy. Reading and candy each come in two takes that alternate.

The work window defaults to Large, with Standard and Extra large sizes also available. Use Files, Memory, Reminders, and Unfinished tasks to find your output, manage saved information, and pick up work you've left unfinished.

Memories suggested from a chat are saved only when you click “Remember”. You can edit or delete saved memories. Before deleting one, read the dialog explaining how related chats are affected.

## Choose your model

Set it up under Settings → Model, then use “Check connection”.

| Option | What you need | Where model requests go |
| --- | --- | --- |
| Local Qwen3 (default) | Ollama and downloaded models | Processed on your computer by default |
| OpenAI-compatible API | An endpoint, model name, and any required key; presets include Qwen, DeepSeek, OpenRouter, and LM Studio | To your configured endpoint; LM Studio can run locally |
| Claude command line | An installed and signed-in `claude -p`, using your subscription | Anthropic |
| Other command line | A working command, such as `codex exec` | Depends on the tool |

Local models are chosen by RAM: **16 GB or more uses `qwen3:8b`**, about 5 GB. Below that, Lulu uses `qwen3:4b-instruct-2507` and `qwen3:4b-thinking-2507`, about 5 GB combined. Animations and the runtime are bundled; models are downloaded separately.

“Deep thinking” is off by default. Turning it on gives the model more time before answering. Local 4B / 8B models may take an extra minute or two. Speed depends on your computer and the task.

You can open Lulu without Ollama and configure another option. Accounts, subscriptions, and API charges are handled by the service you choose.

## Your data

Chats, notes, memories, reminders, and generated files are stored locally:

- macOS: `~/Library/Application Support/Lulu/`
- Windows: `%LOCALAPPDATA%\Lulu\`

Keys are stored separately in `data/secrets.json` inside that folder, not in the installation package or repository. Lulu's local service listens only on `127.0.0.1`.

**Local storage doesn't mean the app never uses the internet.** The default local model processes requests on your computer. An external API or command-line service may receive your requests and relevant material; the interface shows a notice. Web search contacts search services and websites. City lookup, weather, and the initial model download also use the internet.

To uninstall, quit Lulu and delete the installation folder. The data folder remains. Keep it when updating or reinstalling if you want to retain your data.

## Before you rely on it

- Scanned-PDF OCR isn't supported. Document conversion isn't suitable for preserving complex layouts such as multiple columns or nested tables.
- Small models can struggle with long texts and multi-step tasks. If Lulu can't find or verify information, it may pause and ask you for more.
- Key-free web search depends on search-engine pages and can be slow, fail, or break when those pages change. You can configure a Bocha, Tavily, or Brave key.
- Reminders appear only while Lulu is running. Missed reminders are delivered next time you open it.
- There is no mobile app, voice support, or multi-user mode.
- Windows PCs with 8 GB RAM and no dedicated GPU are a design target, not a configuration that has completed acceptance testing. Smooth performance on that hardware isn't promised.

## Testing status

1.0 is Lulu's first public release; 1.1 only changes the pet's routine. Project validation recorded as of September 11, 2026:

| Area | Coverage |
| --- | --- |
| Chinese macOS | Full testing on an Apple M5 Mac with 24 GB RAM; the program issues found were fixed. The developer checked that the release package launches. |
| English macOS | Developer launch check; demo-model end-to-end tests for adding/listing/deleting reminders, translation, summarization, file Q&A, notes, and chat. No native English user trial yet. |
| Chinese / English Windows | CI builds and frozen-runtime smoke tests passed. No installation acceptance on a real Windows PC yet. |
| Automation | Regression tests pass on Windows and macOS CI, plus separate Godot syntax and semantic checks. The pet's routine is covered by state-machine tests (670 checks each on the Chinese and English source trees). |

Found a problem? [Open an issue](https://github.com/aceaaa777/lulu-agent/issues) with your system, package name, steps, and error message. Check logs for personal information before sharing them.

## About Lulu

Lulu is an open-source project by an independent developer, made for people who want a little help with everyday work and study without setting up a development environment. The backend uses Python; the pet and work window are built with Godot 4.4.

The code uses the [MIT license](LICENSE). See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) for third-party components. Desktop pet animations are copyrighted by the project author.

## For developers

Python 3.11+, `pip install -r requirements.txt -c constraints.txt`; `python -m pytest tests -q` runs the regression suite without a model server. The desktop pet is a Godot 4.4 project under `desktop/`; `packaging/export_pet.py` exports it, `packaging/build_release.py` assembles a package, `packaging/localize.py` produces the English source tree from `packaging/i18n/en.csv`, and `.github/workflows/release.yml` does all of it on CI for both languages. Two packages per platform: the Chinese one is built from this tree, the English one from `build/src-en` that `packaging/localize.py` derives from `packaging/i18n/en.csv`. Architecture notes (in Chinese) are in the developer section of `README.md`.

### Configuration: bring your own model

Lulu's shell — the pet, the work window and the backend — is separate from the model; the model is a setting. You can skip the local model entirely and pick one of four backends:

| Backend | What it is | Where your data goes |
| --- | --- | --- |
| Local model (default) | Qwen3 on Ollama, 4B or 8B tier picked by RAM | Stays on this machine |
| API | Any OpenAI-compatible endpoint. Presets for Qwen (DashScope CN / intl), DeepSeek, OpenRouter, LM Studio (local) | To that provider |
| Claude CLI | The local `claude -p`, signed in with your own subscription | To Anthropic |
| Other CLI | Any command, e.g. `codex exec`; prompt goes in by argument or stdin, the answer comes back by file or stdout | Decided by that tool |

**In the UI**: work window → Settings → Model page; choose the backend, fill in base URL / model / key, click *Check connection* — one answered sentence means it works. A switch takes effect after the current task; the *Deep thinking* toggle is immediate. Backends that send data off the machine say so in the UI.

**In the config file**: settings live in `config.json` in the data folder (`~/Library/Application Support/Lulu/` on macOS, `%LOCALAPPDATA%\Lulu\` on Windows); keys live separately in `data/secrets.json` (mode 0600, never in the config, never in the package). DeepSeek, for example:

```json
{"backend": "api", "api": {"preset": "deepseek", "base": "https://api.deepseek.com/v1", "model": "deepseek-chat", "thinking_model": "deepseek-reasoner"}}
```

**From the command line (source checkout)**: `python -m lulu.backends` offers `status`, `probe` (which of the four backends and web search work here), `set`, `secret` and `models`. Point `LULU_HOME` at the data folder; without it the repo folder is used.

```
python -m lulu.backends set backend=api api.preset=openrouter api.model=qwen/qwen3-235b-a22b-2507
python -m lulu.backends secret api_key            # prompted, not echoed; or: secret api_key sk-xxx
python -m lulu.backends set backend=claude_cli claude_cli.command=claude
python -m lulu.backends set backend=cli "cli.command=codex exec --skip-git-repo-check --output-last-message {output_file}"
python -m lulu.backends set search.provider=tavily && python -m lulu.backends secret tavily_key
python -m lulu.backends probe
```

`cli.command` accepts the placeholder `{output_file}` (the answer is written there); `cli.prompt_via` is `arg` or `stdin`, `cli.output` is `file` or `stdout`. `Check backend.command|.cmd` inside the package is the double-click version of `probe`.

You can also keep the local backend and just change models: `set ollama.instruct=qwen3:8b ollama.thinking=qwen3:8b` (the 4B tier uses two models, the 8B tier one hybrid model plus the toggle); `ollama.base` may point at Ollama on another machine.

## License

MIT. Third-party components are listed in `THIRD-PARTY-NOTICES.md`.
