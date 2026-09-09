"""Shared scripted model. Schema calls (intent/judge) are answered by rules so scripted answers only feed the loop."""
import asyncio
import json
import os
import sys
os.environ.setdefault('LULU_NO_LOCATE', '1')
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lulu import intent as intents  # noqa: E402
from lulu.models import ModelProvider, Reply, call  # noqa: E402
from lulu.loop import Agent  # noqa: E402
from lulu.files import Files  # noqa: E402
from lulu.store import Store  # noqa: E402
from lulu import websearch  # noqa: E402


class Scripted(ModelProvider):
    def __init__(self, answers=(), judge='asking', facts=None):
        super().__init__('scripted', 'http://127.0.0.1:1')
        self.answers = iter(answers)
        self.prompts = []
        self.schema_calls = []
        self.judge_verdict = judge
        self.facts = facts or []

    async def chat(self, messages, tools=None, *, schema=None, **kwargs):
        self.prompts.append(messages)
        if schema and schema.get('title') == 'intent':
            text = json.loads(messages[-1]['content'])['用户请求']
            self.schema_calls.append('intent')
            return Reply(content=json.dumps(intents.heuristic(text), ensure_ascii=False))
        if schema and schema.get('title') == 'judge':
            self.schema_calls.append('judge')
            return Reply(content=json.dumps({'verdict': self.judge_verdict}))
        if schema and schema.get('title') == 'queries':
            self.schema_calls.append('queries')
            return Reply(content=json.dumps({'queries': []}))
        if schema and schema.get('title') == 'facts':
            self.schema_calls.append('facts')
            return Reply(content=json.dumps({'facts': self.facts}, ensure_ascii=False))
        if schema and schema.get('title') == 'memory':
            self.schema_calls.append('memory')
            content = messages[-1]['content']
            return Reply(content=json.dumps({'key': content[:6], 'value': content}, ensure_ascii=False))
        if schema and schema.get('title') == 'candidates':
            self.schema_calls.append('candidates')
            return Reply(content=json.dumps({'candidates': getattr(self, 'candidates', [])}, ensure_ascii=False))
        self.calls.append({'scripted': True})
        return next(self.answers, Reply(content='无法完成，请补充信息。'))


@pytest.fixture(autouse=True)
def offline_web(request, monkeypatch):
    """No network in unit tests: search reports a typed failure unless a test overrides it."""
    if 'real_web' in request.keywords:
        return
    async def failing(query, count=8, engines=None, timeout=15, client=None):
        raise websearch.SearchError('network_unreachable', '无法连接任何搜索服务，请检查网络。')
    async def no_fetch(urls, max_chars=6000, timeout=15, concurrency=4, client=None):
        return [], [{'url': u, 'error': 'offline'} for u in urls]
    monkeypatch.setattr(websearch, 'search', failing)
    monkeypatch.setattr(websearch, 'fetch_many', no_fetch)


def online_web(monkeypatch, pages):
    """Pretend the web returned these pages: [{'url','title','text'}]."""
    async def searching(query, count=8, engines=None, timeout=15, client=None):
        return [{'title': p['title'], 'url': p['url'], 'snippet': p['text'][:80]} for p in pages], 'bing', []
    async def fetching(urls, max_chars=6000, timeout=15, concurrency=4, client=None):
        return [dict(p, fetched_at='2026-09-07T10:00:00') for p in pages if p['url'] in urls], []
    monkeypatch.setattr(websearch, 'search', searching)
    monkeypatch.setattr(websearch, 'fetch_many', fetching)


def run(tmp_path, text, answers, store=None, judge='asking', session=None, facts=None):
    store = store or Store(tmp_path/'db')
    files = Files(tmp_path/'files')
    tid = store.create_task(session or store.session(), text)
    provider = Scripted(answers, judge, facts)
    asyncio.run(Agent(store, files, provider).run(tid))
    return store, files, tid, provider


__all__ = ['Scripted', 'run', 'call', 'Reply', 'Agent', 'Files', 'Store', 'online_web']
