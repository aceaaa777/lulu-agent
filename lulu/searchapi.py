"""Web search providers behind one call. Official APIs with the user's own key; the keyless engine scraper is the fallback.

    bocha    博查 — mainland-friendly, pay per call            POST https://api.bochaai.com/v1/web-search
    tavily   Tavily — answer + sources, free monthly quota   POST https://api.tavily.com/search
    brave    Brave Search API — free monthly quota          GET  https://api.search.brave.com/res/v1/web/search
    engines  the built-in Bing/DuckDuckGo/Baidu page scraper (no key; least reliable)

A provider returns {'results': [{'title','url','snippet'}], 'answer': str, 'provider': name}. `answer`, when a
provider gives one, is treated by research.py as one more page the model may quote from — it still has to quote.
"""
import json
import sys

import httpx

from . import websearch

PROVIDERS = {
    'bocha': {'label': '博查（国内）', 'key': 'bocha_key', 'home': 'https://open.bochaai.com', 'note': '按次计费，大陆直连。'},
    'tavily': {'label': 'Tavily', 'key': 'tavily_key', 'home': 'https://tavily.com', 'note': '带答案和来源，有免费月度额度。'},
    'brave': {'label': 'Brave Search', 'key': 'brave_key', 'home': 'https://brave.com/search/api/', 'note': '有免费月度额度。'},
    'engines': {'label': '无钥匙抓取（Bing/DuckDuckGo/百度）', 'key': '', 'home': '', 'note': '不需要钥匙，但页面结构变了就会失效。'},
}
ORDER = ['bocha', 'tavily', 'brave']


class SearchProvider:
    name = 'engines'
    label = PROVIDERS['engines']['label']

    def __init__(self, key='', timeout=15):
        self.key, self.timeout = key, timeout

    async def search(self, query, count=8, client=None, engines=None):
        results, engine, failures = await websearch.search(query, count=count, engines=engines, client=client)
        return {'results': results, 'answer': '', 'provider': 'engines:'+engine, 'failures': failures}

    async def _post(self, url, payload, headers, client=None):
        async def go(c):
            return await c.post(url, json=payload, headers=headers)
        return await self._call(go, client)

    async def _get(self, url, params, headers, client=None):
        async def go(c):
            return await c.get(url, params=params, headers=headers)
        return await self._call(go, client)

    async def _call(self, go, client):
        try:
            if client is not None:
                response = await go(client)
            else:
                async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as c:
                    response = await go(c)
        except httpx.ConnectError:
            raise websearch.SearchError('network_unreachable', f'连不上 {self.label} 的接口')
        except httpx.TimeoutException:
            raise websearch.SearchError('timeout', f'{self.label} 响应超时')
        except httpx.HTTPError as exc:
            raise websearch.SearchError('engine_error', str(exc)[:120])
        if response.status_code in (401, 403):
            raise websearch.SearchError('engine_blocked', f'{self.label} 拒绝了钥匙（HTTP {response.status_code}），请检查钥匙或额度')
        if response.status_code == 429:
            raise websearch.SearchError('engine_blocked', f'{self.label} 额度用完或请求过快（HTTP 429）')
        if response.status_code >= 400:
            raise websearch.SearchError('engine_error', f'{self.label} HTTP {response.status_code}：{response.text[:100]}')
        try:
            return response.json()
        except ValueError:
            raise websearch.SearchError('engine_error', f'{self.label} 返回的不是 JSON')


def _acceptable(url):
    """Cheap guard (no DNS): http(s), a hostname, not localhost or a private IP literal. Fetching re-checks with DNS."""
    from urllib.parse import urlparse
    import ipaddress
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or '').lower()
    if parsed.scheme not in ('http', 'https') or not host or host == 'localhost':
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved)


def _clean(results, count):
    out, seen = [], set()
    for r in results:
        url = str(r.get('url') or '')
        if url in seen or not _acceptable(url):
            continue
        seen.add(url)
        out.append({'title': str(r.get('title') or '')[:200], 'url': url, 'snippet': str(r.get('snippet') or '')[:600]})
        if len(out) >= count:
            break
    return out


class Bocha(SearchProvider):
    name = 'bocha'
    label = PROVIDERS['bocha']['label']

    def parse(self, data):
        body = data.get('data') if isinstance(data.get('data'), dict) else data
        pages = ((body or {}).get('webPages') or {}).get('value') or []
        results = [{'title': p.get('name'), 'url': p.get('url'), 'snippet': p.get('summary') or p.get('snippet')} for p in pages if isinstance(p, dict)]
        return results

    async def search(self, query, count=8, client=None, engines=None):
        data = await self._post('https://api.bochaai.com/v1/web-search', {'query': query, 'count': min(count, 10), 'summary': True},
                                {'Authorization': 'Bearer '+self.key, 'Content-Type': 'application/json'}, client)
        results = _clean(self.parse(data), count)
        if not results:
            raise websearch.SearchError('no_results', '博查没有返回结果')
        return {'results': results, 'answer': '', 'provider': 'bocha', 'failures': []}


class Tavily(SearchProvider):
    name = 'tavily'
    label = PROVIDERS['tavily']['label']

    def parse(self, data):
        results = [{'title': r.get('title'), 'url': r.get('url'), 'snippet': r.get('content')} for r in data.get('results') or [] if isinstance(r, dict)]
        return results, str(data.get('answer') or '')

    async def search(self, query, count=8, client=None, engines=None):
        data = await self._post('https://api.tavily.com/search', {'query': query, 'max_results': min(count, 10), 'include_answer': True, 'search_depth': 'basic'},
                                {'Authorization': 'Bearer '+self.key, 'Content-Type': 'application/json'}, client)
        results, answer = self.parse(data)
        results = _clean(results, count)
        if not results and not answer:
            raise websearch.SearchError('no_results', 'Tavily 没有返回结果')
        return {'results': results, 'answer': answer, 'provider': 'tavily', 'failures': []}


class Brave(SearchProvider):
    name = 'brave'
    label = PROVIDERS['brave']['label']

    def parse(self, data):
        web = (data.get('web') or {}).get('results') or []
        return [{'title': r.get('title'), 'url': r.get('url'), 'snippet': r.get('description')} for r in web if isinstance(r, dict)]

    async def search(self, query, count=8, client=None, engines=None):
        data = await self._get('https://api.search.brave.com/res/v1/web/search', {'q': query, 'count': min(count, 20)},
                               {'Accept': 'application/json', 'X-Subscription-Token': self.key}, client)
        results = _clean(self.parse(data), count)
        if not results:
            raise websearch.SearchError('no_results', 'Brave 没有返回结果')
        return {'results': results, 'answer': '', 'provider': 'brave', 'failures': []}


CLASSES = {'bocha': Bocha, 'tavily': Tavily, 'brave': Brave, 'engines': SearchProvider}


def choose(config, secrets):
    """The provider the settings point at: an explicit one, or the first with a key, else the keyless scraper."""
    wanted = ((config or {}).get('search') or {}).get('provider', 'auto')
    secrets = secrets or {}
    if wanted in CLASSES and wanted != 'engines':
        key = secrets.get(PROVIDERS[wanted]['key'], '')
        if key:
            return CLASSES[wanted](key)
        return None  # explicitly chosen but no key: research reports it instead of silently falling back
    if wanted == 'none':
        return None
    if wanted == 'auto':
        for name in ORDER:
            key = secrets.get(PROVIDERS[name]['key'], '')
            if key:
                return CLASSES[name](key)
    return SearchProvider()


def status(config, secrets):
    provider = choose(config, secrets)
    wanted = ((config or {}).get('search') or {}).get('provider', 'auto')
    if provider is None:
        if wanted == 'none':
            return {'ok': False, 'provider': 'none', 'detail': '联网搜索已关闭，只搜本地文件。'}
        return {'ok': False, 'provider': wanted, 'detail': f'选了 {PROVIDERS.get(wanted, {}).get("label", wanted)}，但还没有填它的钥匙。'}
    keyed = provider.name != 'engines'
    return {'ok': True, 'provider': provider.name, 'label': provider.label,
            'detail': (provider.label+'（已填钥匙）') if keyed else '没有填任何搜索钥匙，用无钥匙抓取兜底，时灵时不灵；建议在“模型”页填一个搜索钥匙。'}


async def _cli(argv):
    from . import backends
    home = backends._home()
    config, secrets = backends.load_config(home), backends.load_secrets(home)
    if argv and argv[0] in CLASSES:
        name = argv.pop(0)
        provider = CLASSES[name](secrets.get(PROVIDERS[name]['key'], ''))
    else:
        provider = choose(config, secrets) or SearchProvider()
    query = ' '.join(argv) or '今日新闻'
    print('提供方：', provider.name)
    try:
        report = await provider.search(query, count=6)
    except websearch.SearchError as exc:
        print('失败：', exc.reason, exc.detail)
        return 1
    if report.get('answer'):
        print('答案：', report['answer'][:500])
    for r in report['results']:
        print('-', r['title'][:60], r['url'])
        if r['snippet']:
            print('   ', r['snippet'][:120].replace('\n', ' '))
    return 0


if __name__ == '__main__':
    import asyncio
    raise SystemExit(asyncio.run(_cli(sys.argv[1:])))
