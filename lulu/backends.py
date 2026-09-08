"""Where the words come from. One config, four backends, one status.

Lulu is the shell: pet, work window, memory, files, reminders. The model behind it is a setting the user owns.
    ollama      local Qwen3 — 4B tier = two models (instruct + thinking), 8B tier = one hybrid model with the think flag
    api         any OpenAI-compatible endpoint (通义/DashScope, DeepSeek, OpenRouter, LM Studio …) with the user's own key
    claude_cli  Claude Code headless (`claude -p`) on the user's subscription login
    cli         any other command-line tool, e.g. `codex exec`
Keys live in secrets.json (0600) inside the data folder — never in config.json, never in the package.
"""
import asyncio
import json
import os
import shutil
import stat
import sys
from pathlib import Path

from . import budget as budgeting
from .models import OllamaProvider, OpenAICompatibleProvider, CommandProvider, ClaudeCliProvider

TIERS = {
    '4b': {'label': 'Qwen3 4B · 两个模型（作答 + 深度思考）', 'instruct': 'qwen3:4b-instruct-2507-q4_K_M', 'thinking': 'qwen3:4b-thinking-2507-q4_K_M',
           'hybrid': False, 'min_memory_gb': 0, 'download_gb': 5.0, 'note': '8GB 内存、无独显的电脑用这一档。'},
    '8b': {'label': 'Qwen3 8B · 一个混合模型（思考用开关）', 'instruct': 'qwen3:8b', 'thinking': 'qwen3:8b',
           'hybrid': True, 'min_memory_gb': 12, 'download_gb': 5.2, 'note': '16GB 内存起；8B 没有拆开的 2507 版，只有混合型。'},
}
DEFAULT_TIER_ORDER = ['8b', '4b']
BACKENDS = {
    'ollama': {'label': '本地模型', 'leaves_device': False, 'note': '模型和资料都留在这台电脑上。'},
    'api': {'label': 'API 接口', 'leaves_device': True, 'note': '你的请求和资料会发到接口地址所在的服务商。'},
    'claude_cli': {'label': 'Claude 命令行', 'leaves_device': True, 'note': '通过本机的 claude 命令调用 Anthropic，用你的订阅登录；资料会发给 Anthropic。'},
    'cli': {'label': '其他命令行', 'leaves_device': True, 'note': '通过你指定的命令调用（例如 codex exec）；资料去向由那个工具决定。'},
}
API_PRESETS = {
    'dashscope': {'label': '通义千问（阿里云百炼）', 'base': 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'model': 'qwen-plus', 'think_param': 'enable_thinking'},
    'dashscope_intl': {'label': '通义千问（国际站）', 'base': 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', 'model': 'qwen-plus', 'think_param': 'enable_thinking'},
    'deepseek': {'label': 'DeepSeek', 'base': 'https://api.deepseek.com/v1', 'model': 'deepseek-chat', 'think_param': '', 'thinking_model': 'deepseek-reasoner'},
    'openrouter': {'label': 'OpenRouter', 'base': 'https://openrouter.ai/api/v1', 'model': 'qwen/qwen3-235b-a22b-2507', 'think_param': ''},
    'lmstudio': {'label': 'LM Studio（本机）', 'base': 'http://127.0.0.1:1234/v1', 'model': 'local', 'think_param': ''},
}
DEFAULT_CONFIG = {
    'backend': 'ollama',
    'think': False,
    'tier': 'auto',
    'ollama': {'base': 'http://127.0.0.1:11434', 'instruct': '', 'thinking': '', 'hybrid': None},
    'api': {'preset': 'dashscope', 'base': API_PRESETS['dashscope']['base'], 'model': API_PRESETS['dashscope']['model'], 'think_param': 'enable_thinking', 'thinking_model': ''},
    'claude_cli': {'command': 'claude', 'model': ''},
    'cli': {'command': 'codex exec --skip-git-repo-check --output-last-message {output_file}', 'model': '', 'prompt_via': 'arg', 'output': 'file'},
    'search': {'provider': 'auto'},
}
SECRET_NAMES = {'api': 'api_key', 'bocha': 'bocha_key', 'tavily': 'tavily_key', 'brave': 'brave_key'}


# ------------------------------------------------------------------ config
def _merge(base, extra):
    out = json.loads(json.dumps(base))
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            out[key] = value
    return out


def upgrade_legacy(raw):
    """0.4/0.5 config was {"model": "qwen2.5:7b", "provider": "ollama"|"openai", ...}. Map it onto the new shape."""
    if 'backend' in raw:
        return raw
    config = {}
    provider = raw.get('provider', 'ollama')
    if provider == 'openai':
        config['backend'] = 'api'
        config['api'] = {'preset': 'custom', 'base': raw.get('base', API_PRESETS['lmstudio']['base']), 'model': raw.get('model', 'local'), 'think_param': ''}
    else:
        config['backend'] = 'ollama'
        model = raw.get('model', '')
        if model and not model.startswith('qwen3'):
            config['ollama'] = {'instruct': model, 'thinking': '', 'hybrid': False, 'base': raw.get('base', DEFAULT_CONFIG['ollama']['base'])}
            config['tier'] = 'custom'
    for key in ('context', 'search_engines'):
        if key in raw:
            config[key] = raw[key]
    return config


def load_config(home):
    path = Path(home)/'config.json'
    raw = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            raw = {}
    return _merge(DEFAULT_CONFIG, upgrade_legacy(raw if isinstance(raw, dict) else {}))


def save_config(home, config):
    path = Path(home)/'config.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)
    return config


def secrets_path(home):
    return Path(home)/'data'/'secrets.json'


def load_secrets(home):
    path = secrets_path(home)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def set_secret(home, name, value):
    if name not in SECRET_NAMES.values():
        raise ValueError('未知的钥匙名称')
    path = secrets_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_secrets(home)
    value = (value or '').strip()
    if value:
        data[name] = value
    else:
        data.pop(name, None)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        temp.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    temp.replace(path)
    return {'saved': bool(value), 'name': name}


def masked(secrets):
    return {k: (v[:3]+'…'+v[-3:] if len(v) > 8 else '已设置') for k, v in secrets.items() if v}


# ------------------------------------------------------------------- tiers
def resolve_tier(config, memory_gb=None):
    """Which local pair to use: an explicit tier, or the biggest one this machine's memory allows."""
    tier = str(config.get('tier') or 'auto')
    custom = config.get('ollama') or {}
    if tier == 'custom' or (tier == 'auto' and custom.get('instruct') and custom['instruct'] not in {t['instruct'] for t in TIERS.values()}):
        return 'custom'
    if tier in TIERS:
        return tier
    memory = budgeting.physical_memory_gb() if memory_gb is None else memory_gb
    for name in DEFAULT_TIER_ORDER:
        if memory <= 0 or memory >= TIERS[name]['min_memory_gb']:
            return name
    return '4b'


def tier_models(config, memory_gb=None):
    name = resolve_tier(config, memory_gb)
    custom = config.get('ollama') or {}
    if name == 'custom':
        instruct = custom.get('instruct') or TIERS['4b']['instruct']
        thinking = custom.get('thinking') or ''
        hybrid = bool(custom.get('hybrid')) if custom.get('hybrid') is not None else (instruct == thinking and bool(thinking))
        return {'tier': 'custom', 'instruct': instruct, 'thinking': thinking, 'hybrid': hybrid, 'label': '自定义：'+instruct}
    spec = TIERS[name]
    return {'tier': name, 'instruct': spec['instruct'], 'thinking': spec['thinking'], 'hybrid': spec['hybrid'], 'label': spec['label']}


# ---------------------------------------------------------------- provider
def build_provider(config, secrets=None, memory_gb=None, workdir=''):
    secrets = secrets or {}
    backend = config.get('backend', 'ollama')
    if backend == 'fake' or os.environ.get('LULU_FAKE_MODEL'):
        from .fakemodel import FakeProvider
        return FakeProvider()
    context = int(config.get('context', 8192))
    if backend == 'api':
        api = config.get('api') or {}
        return OpenAICompatibleProvider(api.get('model') or 'qwen-plus', api.get('base') or API_PRESETS['dashscope']['base'], secrets.get('api_key', ''), context,
                                        think_param=api.get('think_param', ''), thinking_model=api.get('thinking_model', ''))
    if backend == 'claude_cli':
        cc = config.get('claude_cli') or {}
        return ClaudeCliProvider(cc.get('command') or 'claude', cc.get('model', ''), context, workdir=workdir)
    if backend == 'cli':
        cli = config.get('cli') or {}
        return CommandProvider(cli.get('command') or DEFAULT_CONFIG['cli']['command'], cli.get('model', ''), cli.get('prompt_via', 'arg'), cli.get('output', 'file'), context, workdir=workdir)
    models = tier_models(config, memory_gb)
    return OllamaProvider(models['instruct'], (config.get('ollama') or {}).get('base') or DEFAULT_CONFIG['ollama']['base'], context,
                          thinking_model=models['thinking'] if not models['hybrid'] else '', hybrid=models['hybrid'])


def describe(config, provider, budget=None, secrets=None, installed=None):
    """One dictionary the work window shows on the 模型 page and in the status line."""
    backend = config.get('backend', 'ollama')
    spec = BACKENDS.get(backend, BACKENDS['ollama'])
    info = provider.describe()
    info.update(backend=backend, label=spec['label'], note=spec['note'], leaves_device=provider.leaves_device, think=bool(config.get('think')),
                tier=tier_models(config)['tier'] if backend == 'ollama' else '', tier_label=tier_models(config)['label'] if backend == 'ollama' else '',
                api_base=getattr(provider, 'base', '') if backend == 'api' else '', api_preset=(config.get('api') or {}).get('preset', 'custom'),
                command=getattr(provider, 'command', '') if backend in ('cli', 'claude_cli') else '',
                keys=masked(secrets or {}), search_provider=(config.get('search') or {}).get('provider', 'auto'))
    if installed is not None:
        info['installed'] = installed
    if budget is not None:
        info['speed'] = {'generate_tps': budget.generate_tps, 'prefill_tps': budget.prefill_tps, 'tier': budget.tier, 'context': budget.context, 'measured_at': budget.measured_at}
    return info


def apply_update(config, data):
    """Validate a settings change from the UI/CLI and return the new config. Raises ValueError with a Chinese message."""
    out = json.loads(json.dumps(config))
    if 'backend' in data:
        if data['backend'] not in BACKENDS:
            raise ValueError('未知后端：'+str(data['backend']))
        out['backend'] = data['backend']
    if 'think' in data:
        out['think'] = bool(data['think'])
    if 'tier' in data:
        if data['tier'] not in ('auto', 'custom', *TIERS):
            raise ValueError('未知模型档位：'+str(data['tier']))
        out['tier'] = data['tier']
    if isinstance(data.get('ollama'), dict):
        for key in ('base', 'instruct', 'thinking'):
            if key in data['ollama']:
                out['ollama'][key] = str(data['ollama'][key]).strip()
        if 'hybrid' in data['ollama']:
            out['ollama']['hybrid'] = bool(data['ollama']['hybrid']) if data['ollama']['hybrid'] is not None else None
        if out['ollama'].get('instruct') and out['tier'] == 'auto':
            out['tier'] = 'custom'
    if isinstance(data.get('api'), dict):
        api = data['api']
        if api.get('preset') in API_PRESETS:
            preset = API_PRESETS[api['preset']]
            out['api'].update(preset=api['preset'], base=preset['base'], model=preset['model'], think_param=preset.get('think_param', ''), thinking_model=preset.get('thinking_model', ''))
        elif api.get('preset'):
            out['api']['preset'] = 'custom'
        for key in ('base', 'model', 'think_param', 'thinking_model'):
            if key in api and api[key] is not None:
                out['api'][key] = str(api[key]).strip()
        if not out['api']['base'].startswith(('http://', 'https://')):
            raise ValueError('接口地址要以 http:// 或 https:// 开头')
        out['api']['base'] = out['api']['base'].rstrip('/')
    if isinstance(data.get('claude_cli'), dict):
        for key in ('command', 'model'):
            if key in data['claude_cli']:
                out['claude_cli'][key] = str(data['claude_cli'][key]).strip()
    if isinstance(data.get('cli'), dict):
        for key in ('command', 'model', 'prompt_via', 'output'):
            if key in data['cli']:
                out['cli'][key] = str(data['cli'][key]).strip()
        if out['cli'].get('prompt_via') not in ('arg', 'stdin'):
            raise ValueError('prompt_via 只能是 arg 或 stdin')
    if isinstance(data.get('search'), dict) and 'provider' in data['search']:
        from . import searchapi
        if data['search']['provider'] not in searchapi.PROVIDERS and data['search']['provider'] not in ('auto', 'none'):
            raise ValueError('未知搜索提供方：'+str(data['search']['provider']))
        out['search']['provider'] = data['search']['provider']
    return out


# ------------------------------------------------------------------- probe
async def probe(config, secrets=None, memory_gb=None, workdir=''):
    """Check every backend the user could switch to. Nothing here changes settings; it only reports."""
    secrets = secrets or {}
    report = {'backends': {}, 'memory_gb': round(budgeting.physical_memory_gb() if memory_gb is None else memory_gb, 1)}
    # local
    models = tier_models(config, memory_gb)
    local = build_provider(dict(config, backend='ollama'), secrets, memory_gb)
    names = await local.models()
    entry = {'label': BACKENDS['ollama']['label'], 'ok': False, 'tier': models['tier'], 'tier_label': models['label'], 'instruct': models['instruct'], 'thinking': models['thinking'] or models['instruct']}
    if names is None:
        entry['detail'] = 'Ollama 没有运行或无法连接（'+local.base+'）。请先安装并启动 Ollama。'
        entry['ollama_installed'] = shutil.which('ollama') is not None
    else:
        have = set(names)
        needed = [models['instruct']]+([models['thinking']] if models['thinking'] and not models['hybrid'] else [])
        missing = [m for m in needed if m not in have and m+':latest' not in have]
        entry['installed_models'] = sorted(have)[:30]
        entry['missing'] = missing
        entry['ok'] = not missing
        entry['detail'] = ('已就绪：'+'、'.join(needed)) if not missing else ('Ollama 在运行，但缺少模型：'+'、'.join(missing)+'。运行安装脚本，或在终端执行 ollama pull '+' 和 ollama pull '.join(missing))
    entry['tiers'] = {name: {**spec, 'fits': report['memory_gb'] <= 0 or report['memory_gb'] >= spec['min_memory_gb']} for name, spec in TIERS.items()}
    report['backends']['ollama'] = entry
    # api
    api_cfg = config.get('api') or {}
    api = build_provider(dict(config, backend='api'), secrets, memory_gb)
    entry = {'label': BACKENDS['api']['label'], 'ok': False, 'base': api.base, 'model': api.model, 'key_set': bool(secrets.get('api_key')), 'preset': api_cfg.get('preset', 'custom')}
    if not secrets.get('api_key') and not api.base.startswith('http://127.0.0.1') and not api.base.startswith('http://localhost'):
        entry['detail'] = '还没有填 API 钥匙。'
    else:
        listed = await api.models()
        if listed is None:
            entry['detail'] = '连不上 '+api.base+'，或钥匙无效。'
        else:
            entry['ok'] = True
            entry['detail'] = '接口可用，'+(f'共 {len(listed)} 个模型' if listed else '已连接')+('；当前模型 '+api.model+(' 在列表中' if api.model in listed else ' 未出现在列表中（部分服务商不列出，可忽略）'))
    report['backends']['api'] = entry
    # claude cli
    cc = build_provider(dict(config, backend='claude_cli'), secrets, memory_gb, workdir)
    entry = {'label': BACKENDS['claude_cli']['label'], 'ok': False, 'command': cc.claude_command}
    if not cc.available():
        entry['detail'] = '找不到 '+cc.claude_command+' 命令。安装 Claude Code 并登录后再用。'
    else:
        version = await _run([cc.claude_command, '--version'])
        entry['ok'] = version is not None
        entry['detail'] = ('已找到：'+version.strip()[:80]) if version is not None else '命令存在但无法运行。'
    report['backends']['claude_cli'] = entry
    # generic cli
    cli = build_provider(dict(config, backend='cli'), secrets, memory_gb, workdir)
    entry = {'label': BACKENDS['cli']['label'], 'ok': cli.available(), 'command': cli.command}
    entry['detail'] = ('已找到命令 '+cli.executable) if cli.available() else ('找不到命令 '+(cli.executable or '(空)')+'。')
    report['backends']['cli'] = entry
    # search
    try:
        from . import searchapi
        report['search'] = searchapi.status(config, secrets)
    except ImportError:
        report['search'] = {}
    report['current'] = config.get('backend', 'ollama')
    return report


async def _run(parts, timeout=15):
    try:
        process = await asyncio.create_subprocess_exec(*parts, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.DEVNULL)
        out, err = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except (OSError, asyncio.TimeoutError):
        return None
    if process.returncode != 0:
        return None
    return (out or err).decode('utf-8', 'replace')


def summarize_probe(report):
    lines = []
    for key in ('ollama', 'api', 'claude_cli', 'cli'):
        item = report['backends'].get(key, {})
        mark = '✓' if item.get('ok') else '✗'
        current = '（当前）' if report.get('current') == key else ''
        lines.append(f"{mark} {item.get('label', key)}{current}：{item.get('detail', '')}")
        if key == 'ollama' and item.get('tier_label'):
            lines.append(f"   档位：{item['tier_label']}；本机内存 {report.get('memory_gb', 0)} GB")
    search = report.get('search') or {}
    if search:
        lines.append(('✓' if search.get('ok') else '·')+' 联网搜索：'+search.get('detail', ''))
    return '\n'.join(lines)


# --------------------------------------------------------------------- cli
def _home():
    if os.environ.get('LULU_HOME'):
        return Path(os.environ['LULU_HOME'])
    root = Path(__file__).resolve().parents[1]
    return root


def main(argv=None):
    """python -m lulu.backends status | probe | set key=value … | secret <name> | models"""
    argv = list(sys.argv[1:] if argv is None else argv)
    home = _home()
    config = load_config(home)
    secrets = load_secrets(home)
    command = argv[0] if argv else 'status'
    if command == 'status':
        provider = build_provider(config, secrets)
        print(json.dumps(describe(config, provider, secrets=secrets), ensure_ascii=False, indent=2))
    elif command == 'probe':
        report = asyncio.run(probe(config, secrets))
        print(summarize_probe(report))
        if '--json' in argv:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    elif command == 'models':
        print(json.dumps(tier_models(config), ensure_ascii=False, indent=2))
    elif command == 'set':
        data = {}
        for item in argv[1:]:
            key, _, value = item.partition('=')
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            section, _, field = key.partition('.')
            if field:
                data.setdefault(section, {})[field] = value
            else:
                data[key] = value
        config = apply_update(config, data)
        save_config(home, config)
        print('已保存：', json.dumps({k: config[k] for k in data}, ensure_ascii=False))
    elif command == 'secret':
        if len(argv) < 2:
            raise SystemExit('用法：python -m lulu.backends secret api_key|bocha_key|tavily_key|brave_key')
        import getpass
        value = argv[2] if len(argv) > 2 else getpass.getpass('粘贴钥匙（不会显示）：')
        print(set_secret(home, argv[1], value))
    else:
        raise SystemExit('用法：python -m lulu.backends status|probe|models|set|secret')


if __name__ == '__main__':
    main()
