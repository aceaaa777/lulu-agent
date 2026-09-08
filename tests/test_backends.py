"""Backend layer: config shapes, tiers, think flag in payloads, command-line providers, secrets, probe, search providers."""
import asyncio
import json
import os
import stat
import sys

import pytest

from conftest import Scripted, run, Reply, online_web
from lulu import backends, searchapi, websearch, research as researching
from lulu.models import OllamaProvider, OpenAICompatibleProvider, CommandProvider, ClaudeCliProvider, extract_json, split_thinking, flatten_messages


# ------------------------------------------------------------------ config
def test_default_config_and_legacy_upgrade(tmp_path):
    config = backends.load_config(tmp_path)
    assert config['backend'] == 'ollama' and config['think'] is False and config['tier'] == 'auto'
    (tmp_path/'config.json').write_text(json.dumps({'model': 'qwen2.5:7b'}), encoding='utf-8')
    legacy = backends.load_config(tmp_path)
    assert legacy['backend'] == 'ollama' and legacy['tier'] == 'custom' and legacy['ollama']['instruct'] == 'qwen2.5:7b'
    (tmp_path/'config.json').write_text(json.dumps({'provider': 'openai', 'model': 'local', 'base': 'http://127.0.0.1:1234/v1'}), encoding='utf-8')
    api = backends.load_config(tmp_path)
    assert api['backend'] == 'api' and api['api']['base'] == 'http://127.0.0.1:1234/v1'


def test_tier_follows_memory_and_explicit_choice():
    config = backends.load_config('/nonexistent')
    assert backends.resolve_tier(config, memory_gb=8) == '4b'
    assert backends.resolve_tier(config, memory_gb=16) == '8b'
    assert backends.resolve_tier(config, memory_gb=0) == '8b'  # unknown memory: the default order wins
    assert backends.resolve_tier(dict(config, tier='4b'), memory_gb=64) == '4b'
    four = backends.tier_models(dict(config, tier='4b'))
    assert four['instruct'].startswith('qwen3:4b-instruct') and four['thinking'].startswith('qwen3:4b-thinking') and not four['hybrid']
    eight = backends.tier_models(dict(config, tier='8b'))
    assert eight['instruct'] == eight['thinking'] == 'qwen3:8b' and eight['hybrid']


def test_build_provider_shapes():
    config = backends.load_config('/nonexistent')
    local = backends.build_provider(dict(config, tier='4b'))
    assert isinstance(local, OllamaProvider) and local.thinking_model.startswith('qwen3:4b-thinking') and not local.hybrid and local.profile['supports_think']
    hybrid = backends.build_provider(dict(config, tier='8b'))
    assert hybrid.hybrid and hybrid.thinking_model == '' and hybrid.profile['supports_think']
    api = backends.build_provider(dict(config, backend='api'), {'api_key': 'sk-test'})
    assert isinstance(api, OpenAICompatibleProvider) and api.api_key == 'sk-test' and api.leaves_device and 'dashscope' in api.base
    claude = backends.build_provider(dict(config, backend='claude_cli'))
    assert isinstance(claude, ClaudeCliProvider) and '--output-format json' in claude.command and claude.leaves_device
    cli = backends.build_provider(dict(config, backend='cli'))
    assert isinstance(cli, CommandProvider) and cli.executable == 'codex'


def test_apply_update_validates():
    config = backends.load_config('/nonexistent')
    with pytest.raises(ValueError):
        backends.apply_update(config, {'backend': 'magic'})
    with pytest.raises(ValueError):
        backends.apply_update(config, {'api': {'base': 'dashscope.aliyuncs.com'}})
    updated = backends.apply_update(config, {'backend': 'api', 'think': True, 'api': {'preset': 'deepseek'}})
    assert updated['backend'] == 'api' and updated['think'] and updated['api']['model'] == 'deepseek-chat' and updated['api']['thinking_model'] == 'deepseek-reasoner'
    custom = backends.apply_update(config, {'ollama': {'instruct': 'qwen3.5:4b', 'thinking': 'qwen3.5:4b', 'hybrid': True}})
    assert custom['tier'] == 'custom' and backends.tier_models(custom)['hybrid'] and backends.tier_models(custom)['instruct'] == 'qwen3.5:4b'


def test_secrets_are_separate_and_private(tmp_path):
    backends.set_secret(tmp_path, 'api_key', 'sk-abcdefghijkl')
    assert backends.load_secrets(tmp_path)['api_key'] == 'sk-abcdefghijkl'
    assert 'sk-' not in (tmp_path/'config.json').read_text(encoding='utf-8') if (tmp_path/'config.json').exists() else True
    if os.name != 'nt':
        mode = stat.S_IMODE(backends.secrets_path(tmp_path).stat().st_mode)
        assert mode == 0o600
    assert backends.masked(backends.load_secrets(tmp_path))['api_key'].startswith('sk-') and 'abcdefghijkl' not in backends.masked(backends.load_secrets(tmp_path))['api_key']
    backends.set_secret(tmp_path, 'api_key', '')
    assert 'api_key' not in backends.load_secrets(tmp_path)
    with pytest.raises(ValueError):
        backends.set_secret(tmp_path, 'password', 'x')


# ----------------------------------------------------------------- payloads
def test_ollama_payload_think_shapes():
    two = OllamaProvider('qwen3:4b-instruct-2507-q4_K_M', thinking_model='qwen3:4b-thinking-2507-q4_K_M')
    plain = two.build_payload([{'role': 'user', 'content': '你好'}], max_tokens=100)
    assert plain['model'].startswith('qwen3:4b-instruct') and 'think' not in plain and plain['options']['num_predict'] == 100
    deep = two.build_payload([{'role': 'user', 'content': '你好'}], max_tokens=100, think=True)
    assert deep['model'].startswith('qwen3:4b-thinking') and deep['think'] is True and deep['options']['num_predict'] > 100
    hybrid = OllamaProvider('qwen3:8b', hybrid=True)
    assert hybrid.build_payload([{'role': 'user', 'content': 'x'}])['think'] is False
    assert hybrid.build_payload([{'role': 'user', 'content': 'x'}], think=True)['think'] is True and hybrid.build_payload([{'role': 'user', 'content': 'x'}], think=True)['model'] == 'qwen3:8b'
    old = OllamaProvider('qwen2.5:7b')
    assert 'think' not in old.build_payload([{'role': 'user', 'content': 'x'}], think=True)  # no thinking support: silently plain


def test_api_payload_think_shapes():
    dashscope = OpenAICompatibleProvider('qwen-plus', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'k', think_param='enable_thinking')
    assert 'enable_thinking' not in dashscope.build_payload([{'role': 'user', 'content': 'x'}])
    assert dashscope.build_payload([{'role': 'user', 'content': 'x'}], think=True)['enable_thinking'] is True
    deepseek = OpenAICompatibleProvider('deepseek-chat', 'https://api.deepseek.com/v1', 'k', think_param='', thinking_model='deepseek-reasoner')
    assert deepseek.build_payload([{'role': 'user', 'content': 'x'}], think=True)['model'] == 'deepseek-reasoner'
    assert deepseek.build_payload([{'role': 'user', 'content': 'x'}])['model'] == 'deepseek-chat'
    local = OpenAICompatibleProvider('local', 'http://127.0.0.1:1234/v1')
    assert not local.leaves_device


def test_thinking_text_never_reaches_content():
    content, thought = split_thinking('<think>先想想</think>答案是三。')
    assert content == '答案是三。' and thought == '先想想'
    assert split_thinking('没有思考标签') == ('没有思考标签', '')
    assert extract_json('好的，结果如下：\n```json\n{"a": 1, "b": "x}"}\n```\n谢谢') == '{"a": 1, "b": "x}"}'
    assert extract_json('纯文本没有对象') is None
    flat = flatten_messages([{'role': 'system', 'content': '要求'}, {'role': 'user', 'content': '你好'}], schema={'title': 't', 'type': 'object'})
    assert '【要求】' in flat and '【用户】' in flat and 'JSON Schema' in flat


# ------------------------------------------------------------- CLI backend
def test_command_provider_runs_a_real_command_and_parses_json(tmp_path):
    script = tmp_path/'echo_model.py'
    script.write_text('import sys,json\nprompt=sys.stdin.read()\nprint("前言 "+json.dumps({"answer":"收到 "+str(len(prompt))+" 字"},ensure_ascii=False))\n', encoding='utf-8')
    provider = CommandProvider(f'{sys.executable} {script}', model='echo', prompt_via='stdin', output='stdout')
    assert provider.available()
    reply = asyncio.run(provider.chat([{'role': 'user', 'content': '你好'}], schema={'title': 'answer', 'type': 'object'}))
    assert not reply.failed and json.loads(reply.content)['answer'].startswith('收到')
    plain = asyncio.run(provider.chat([{'role': 'user', 'content': '你好'}]))
    assert plain.content.startswith('前言')
    file_script = tmp_path/'file_model.py'
    file_script.write_text('import sys\nopen(sys.argv[1],"w",encoding="utf-8").write("写到文件的答复")\n', encoding='utf-8')
    via_file = CommandProvider(f'{sys.executable} {file_script} {{output_file}}', prompt_via='stdin', output='file')
    assert asyncio.run(via_file.chat([{'role': 'user', 'content': 'x'}])).content == '写到文件的答复'


def test_command_provider_reports_missing_and_failing_commands(tmp_path):
    missing = CommandProvider('definitely-not-a-command-xyz')
    reply = asyncio.run(missing.chat([{'role': 'user', 'content': 'x'}]))
    assert reply.failed and '找不到命令' in reply.content and missing.last_error
    bad = tmp_path/'bad.py'
    bad.write_text('import sys\nsys.stderr.write("boom")\nsys.exit(2)\n', encoding='utf-8')
    failing = CommandProvider(f'{sys.executable} {bad}', prompt_via='stdin')
    reply = asyncio.run(failing.chat([{'role': 'user', 'content': 'x'}]))
    assert reply.failed and 'boom' in reply.content


def test_claude_cli_provider_parses_result_json(tmp_path):
    # a stand-in for `claude -p` written in Python so the test runs on Windows too (no /bin/sh there)
    fake = tmp_path/'fake_claude.py'
    fake.write_text('import sys,json\nsys.stdin.read()\nprint(json.dumps({"type":"result","is_error":False,"result":json.dumps({"answer":"来自命令行"},ensure_ascii=False)},ensure_ascii=False))\n', encoding='utf-8')
    provider = ClaudeCliProvider(f'"{sys.executable}" "{fake}"', model='claude-sonnet-4-5')
    assert provider.available() and '--model {model}' in provider.command and provider.build_command('p', '/tmp/o')[0][-1] == 'claude-sonnet-4-5'
    assert provider.executable == sys.executable
    reply = asyncio.run(provider.chat([{'role': 'user', 'content': '问'}], schema={'title': 'answer', 'type': 'object'}))
    assert not reply.failed and json.loads(reply.content)['answer'] == '来自命令行'
    error = tmp_path/'fake_claude_err.py'
    error.write_text('import sys,json\nsys.stdin.read()\nprint(json.dumps({"type":"result","is_error":True,"result":"Not logged in"}))\n', encoding='utf-8')
    reply = asyncio.run(ClaudeCliProvider(f'"{sys.executable}" "{error}"').chat([{'role': 'user', 'content': '问'}]))
    assert reply.failed and 'Not logged in' in reply.content


def test_command_split_keeps_windows_paths(monkeypatch):
    monkeypatch.setattr(os, 'name', 'nt')
    parts = CommandProvider.split(r'"C:\Program Files\Python\python.exe" C:\tools\model.py --flag "a b"')
    assert parts == [r'C:\Program Files\Python\python.exe', r'C:\tools\model.py', '--flag', 'a b']
    monkeypatch.setattr(os, 'name', 'posix')
    assert CommandProvider.split('"/usr/bin/python3" /tmp/model.py "a b"') == ['/usr/bin/python3', '/tmp/model.py', 'a b']


# -------------------------------------------------------------------- probe
def test_probe_reports_every_backend_offline(tmp_path, monkeypatch):
    config = backends.load_config(tmp_path)
    monkeypatch.setenv('LULU_OLLAMA_BASE', 'http://127.0.0.1:1')
    report = asyncio.run(backends.probe(config, {}, memory_gb=8))
    local = report['backends']['ollama']
    assert not local['ok'] and 'Ollama' in local['detail'] and local['tier'] == '4b' and local['tiers']['4b']['fits'] and not local['tiers']['8b']['fits']
    assert not report['backends']['api']['ok'] and '钥匙' in report['backends']['api']['detail']
    assert 'claude_cli' in report['backends'] and 'cli' in report['backends']
    assert report['search']['provider'] == 'engines'
    summary = backends.summarize_probe(report)
    assert '本地模型（当前）' in summary and '联网搜索' in summary


def test_describe_carries_privacy_line_and_keys():
    config = backends.load_config('/nonexistent')
    info = backends.describe(dict(config, backend='api'), backends.build_provider(dict(config, backend='api'), {'api_key': 'sk-1234567890'}), secrets={'api_key': 'sk-1234567890'})
    assert info['leaves_device'] and info['note'] and info['keys']['api_key'].endswith('890') and '1234567' not in info['keys']['api_key']
    local = backends.describe(config, backends.build_provider(dict(config, tier='4b')))
    assert not local['leaves_device'] and local['tier'] == backends.resolve_tier(config)


# ------------------------------------------------------------------ search
def test_search_provider_choice_and_status():
    config = backends.load_config('/nonexistent')
    assert searchapi.choose(config, {}).name == 'engines'
    assert searchapi.choose(config, {'tavily_key': 't'}).name == 'tavily'
    assert searchapi.choose(config, {'bocha_key': 'b', 'tavily_key': 't'}).name == 'bocha'
    explicit = dict(config, search={'provider': 'brave'})
    assert searchapi.choose(explicit, {}) is None and '钥匙' in searchapi.status(explicit, {})['detail']
    assert searchapi.choose(explicit, {'brave_key': 'k'}).name == 'brave'
    assert searchapi.choose(dict(config, search={'provider': 'none'}), {'brave_key': 'k'}) is None


def test_search_provider_parsers():
    bocha = searchapi.Bocha('k').parse({'code': 200, 'data': {'webPages': {'value': [{'name': '标题', 'url': 'https://a.example/x', 'summary': '摘要'}, {'name': '内网', 'url': 'http://192.168.1.1/'}]}}})
    assert searchapi._clean(bocha, 5) == [{'title': '标题', 'url': 'https://a.example/x', 'snippet': '摘要'}]
    results, answer = searchapi.Tavily('k').parse({'answer': 'BTC 是 65000', 'results': [{'title': 'T', 'url': 'https://t.example/1', 'content': '正文'}]})
    assert answer == 'BTC 是 65000' and results[0]['snippet'] == '正文'
    brave = searchapi.Brave('k').parse({'web': {'results': [{'title': 'B', 'url': 'https://b.example/1', 'description': '描述'}]}})
    assert brave[0]['snippet'] == '描述'


def test_research_uses_keyed_provider_answer_as_quotable_page(tmp_path, monkeypatch):
    class Fake(searchapi.SearchProvider):
        name, label = 'tavily', 'Tavily'
        async def search(self, query, count=8, client=None, engines=None):
            return {'results': [{'title': 'Bitcoin price', 'url': 'https://example.com/btc', 'snippet': 'Binance BTC/USDT 65,001.2'}], 'answer': '币安 BTC 现价 65,001.2 USDT。', 'provider': 'tavily', 'failures': []}
    async def no_fetch(urls, max_chars=6000, timeout=15, concurrency=4, client=None):
        return [], [{'url': u, 'error': 'offline'} for u in urls]
    monkeypatch.setattr(websearch, 'fetch_many', no_fetch)
    provider = Scripted([], facts=[{'claim': '币安价格 65,001.2', 'quote': '币安 BTC 现价 65,001.2 USDT', 'source': 2}])
    from lulu import budget as budgeting
    report = asyncio.run(researching.research(provider, '现在BTC多少钱', {'needs_realtime': True, 'symbols': ['BTC']}, budgeting.default_budget('x'), searcher=Fake()))
    assert report['provider'] == 'tavily' and any(p['url'].startswith('answer://') for p in report['pages'])
    assert report['facts'] and report['facts'][0]['url'].startswith('answer://')


def test_query_through_agent_with_keyed_provider(tmp_path, monkeypatch):
    class Fake(searchapi.SearchProvider):
        name, label = 'bocha', '博查'
        async def search(self, query, count=8, client=None, engines=None):
            return {'results': [{'title': 'NVDA', 'url': 'https://example.com/nvda', 'snippet': 'NVDA closed at 181.50 on 2026-09-04'}], 'answer': '', 'provider': 'bocha', 'failures': []}
    pages = [{'url': 'https://example.com/nvda', 'title': 'NVDA', 'text': 'NVIDIA (NVDA) closed at 181.50 on 2026-09-04.'}]
    async def fetching(urls, max_chars=6000, timeout=15, concurrency=4, client=None):
        return [dict(p, fetched_at='2026-09-07T10:00:00') for p in pages if p['url'] in urls], []
    monkeypatch.setattr(websearch, 'fetch_many', fetching)
    from lulu.loop import Agent
    from lulu.files import Files
    from lulu.store import Store
    s = Store(tmp_path/'db'); f = Files(tmp_path/'files')
    tid = s.create_task(s.session(), '查一下今天英伟达的股价')
    p = Scripted([Reply(content=json.dumps({'answer': '英伟达最近收盘价 181.50 美元（来源：example.com）'}))], facts=[{'claim': '收盘 181.50', 'quote': 'closed at 181.50', 'source': 1}])
    asyncio.run(Agent(s, f, p, searcher=Fake()).run(tid))
    assert s.task(tid)['status'] == 'completed' and '181.50' in s.task(tid)['answer']
    started = [json.loads(e['detail']) for e in s.rows("SELECT detail FROM events WHERE task=? AND kind='research_started'", (tid,))]
    assert started and started[0]['provider'] == 'bocha'


def test_url_guard_async_rejects_private_targets_without_blocking():
    async def scenario():
        for bad in ('http://127.0.0.1/x', 'http://localhost/x', 'http://10.0.0.5/x', 'ftp://example.com/x'):
            with pytest.raises(ValueError):
                await websearch.check_url_async(bad)
        # the loop keeps serving while a lookup is in flight: a timer fires during the (thread-based) resolution
        ticks = []
        async def ticker():
            for _ in range(3):
                await asyncio.sleep(0.01); ticks.append(1)
        await asyncio.gather(ticker(), asyncio.gather(*(websearch.check_url_async('http://192.168.1.9/'+str(i)) for i in range(3)), return_exceptions=True))
        assert len(ticks) == 3
    asyncio.run(scenario())
