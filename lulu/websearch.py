"""General web search and page fetch. No API keys, no agent packages.

Engines are tried in order until one returns results; every failure is typed so the user gets a plain reason.
Run `python -m lulu.websearch 查询词` to see what each engine returns on this machine.
"""
import asyncio
import html
import ipaddress
import json
import os
import re
import socket
import sys
import time
from pathlib import Path
import base64
from urllib.parse import urlparse, parse_qs, unquote, quote_plus

import httpx

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
           'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.7', 'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8'}
DEFAULT_ENGINES = ['bing', 'duckduckgo', 'baidu']
ENGINE_HOSTS = {'bing.com', 'duckduckgo.com', 'baidu.com', 'microsoft.com', 'baidu.com/link'}
SKIP_HOSTS = ('youtube.com', 'youtu.be', 'bilibili.com', 'facebook.com', 'instagram.com', 'tiktok.com', 'douyin.com', 'twitter.com', 'x.com', 'weibo.com')


class SearchError(ValueError):
    def __init__(self, reason, detail=''):
        super().__init__(detail or reason)
        self.reason, self.detail = reason, detail


# ------------------------------------------------------------------ URL guard
def _addresses_private(infos):
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
            return True
    return False


def _is_private(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValueError('无法解析该网址的域名')
    return _addresses_private(infos)


async def _is_private_async(host, timeout=6):
    """DNS in the loop's resolver thread with a cap. A synchronous getaddrinfo here once froze the whole service:
    a slow lookup blocked the event loop, the launcher's health checks failed, and the agent was restarted mid-task."""
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(loop.getaddrinfo(host, None), timeout)
    except socket.gaierror:
        raise ValueError('无法解析该网址的域名')
    except asyncio.TimeoutError:
        raise ValueError('域名解析超时')
    return _addresses_private(infos)


def _check_shape(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('只支持 http/https 网址')
    if parsed.hostname == 'localhost':
        raise ValueError('不允许读取本机或内网地址')
    return parsed.hostname


def check_url(url):
    host = _check_shape(url)
    if _is_private(host):
        raise ValueError('不允许读取本机或内网地址')
    return url


async def check_url_async(url):
    host = _check_shape(url)
    if await _is_private_async(host):
        raise ValueError('不允许读取本机或内网地址')
    return url


def host_of(url):
    try:
        return (urlparse(url).hostname or '').lower()
    except ValueError:
        return ''


# ------------------------------------------------------------ HTML handling
def decode_html(content, header_charset=''):
    """Chinese sites often omit the charset header; look at the meta tag before falling back to UTF-8."""
    head = content[:4096].decode('ascii', 'ignore')
    match = re.search(r'charset=["\']?\s*([A-Za-z0-9_-]+)', head, re.I)
    for enc in (header_charset, match.group(1) if match else '', 'utf-8', 'gb18030'):
        if not enc:
            continue
        try:
            return content.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode('utf-8', 'replace')


def strip_html(page, max_chars):
    title = re.search(r'(?is)<title[^>]*>(.*?)</title>', page)
    metas = []
    for m in re.finditer(r'(?is)<meta\s+[^>]*?(?:name|property)=["\'](?:description|og:description|twitter:description)["\'][^>]*?content=["\'](.*?)["\']', page):
        metas.append(html.unescape(m.group(1)).strip())
    for m in re.finditer(r'(?is)<meta\s+[^>]*?content=["\'](.*?)["\'][^>]*?(?:name|property)=["\'](?:description|og:description|twitter:description)["\']', page):
        metas.append(html.unescape(m.group(1)).strip())
    page = re.sub(r'(?is)<(script|style|noscript|svg|nav|footer|header|aside|iframe)[^>]*>.*?</\1>', ' ', page)
    page = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>|</tr>|</td>|</th>', '\n', page)
    text = re.sub(r'(?s)<[^>]+>', ' ', page)
    text = html.unescape(text)
    text = re.sub(r'[ \t\r\f\v\xa0]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text).strip()
    summary = '\n'.join(dict.fromkeys(m for m in metas if m))
    if summary:
        text = '【页面摘要】'+summary+'\n'+text
    return (html.unescape(title.group(1)).strip() if title else ''), text[:max_chars]


def _text(fragment):
    return html.unescape(re.sub(r'(?s)<[^>]+>', ' ', fragment)).replace('\xa0', ' ').strip()


def _squash(text):
    return re.sub(r'\s+', ' ', text).strip()


# ---------------------------------------------------------------- parsers
def parse_duckduckgo(page):
    results = []
    for block in re.findall(r'(?s)<div class="result[^"]*">(.*?)</div>\s*</div>', page):
        link = re.search(r'(?s)<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block)
        if not link:
            continue
        href = html.unescape(link.group(1))
        if 'duckduckgo.com/l/?' in href or href.startswith('//duckduckgo.com/l/'):
            target = parse_qs(urlparse(href).query).get('uddg', [''])[0]
            href = unquote(target) if target else href
        snippet = re.search(r'(?s)<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', block)
        results.append({'title': _squash(_text(link.group(2))), 'url': href, 'snippet': _squash(_text(snippet.group(1))) if snippet else ''})
    return results


def unwrap_bing(url):
    """Bing wraps result links as /ck/a?...&u=a1<base64url>; recover the real address."""
    if 'bing.com/ck/a' not in url:
        return url
    target = parse_qs(urlparse(url).query).get('u', [''])[0]
    if target.startswith('a1'):
        payload = target[2:]
        try:
            return base64.urlsafe_b64decode(payload+'='*(-len(payload) % 4)).decode('utf-8', 'replace')
        except (ValueError, UnicodeDecodeError):
            return url
    return url


def parse_bing(page):
    results = []
    for block in re.findall(r'(?s)<li class="b_algo"[^>]*>(.*?)</li>', page):
        link = re.search(r'(?s)<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block)
        if not link:
            continue
        snippet = re.search(r'(?s)<p[^>]*>(.*?)</p>', block)
        results.append({'title': _squash(_text(link.group(2))), 'url': unwrap_bing(html.unescape(link.group(1))),
                        'snippet': _squash(_text(snippet.group(1))) if snippet else ''})
    return results


def parse_baidu(page):
    results = []
    for block in re.findall(r'(?s)<div[^>]+class="result(?: c-container)?[^"]*"[^>]*>(.*?)(?=<div[^>]+class="result(?: c-container)?[^"]*"|$)', page):
        link = re.search(r'(?s)<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block)
        if not link:
            continue
        rest = block[link.end():]
        snippet = re.search(r'(?s)<(?:span|div)[^>]+class="[^"]*(?:content-right|c-abstract|c-span-last)[^"]*"[^>]*>(.*?)</(?:span|div)>', rest)
        results.append({'title': _squash(_text(link.group(2))), 'url': html.unescape(link.group(1)),
                        'snippet': _squash(_text(snippet.group(1)))[:300] if snippet else _squash(_text(rest))[:300]})
    return results


def parse_generic(page, engine_host):
    """Last resort when an engine changes its markup: every external link with a readable title."""
    results, seen = [], set()
    for href, inner in re.findall(r'(?s)<a[^>]+href="(https?://[^"#]+)"[^>]*>(.*?)</a>', page):
        href = unwrap_bing(html.unescape(href))
        host = host_of(href)
        title = _squash(_text(inner))
        if not host or engine_host in host or 'microsoft.com' in host or len(title) < 8 or href in seen:
            continue
        seen.add(href)
        results.append({'title': title, 'url': href, 'snippet': ''})
    return results


ENGINES = {
    'duckduckgo': {'url': 'https://html.duckduckgo.com/html/', 'method': 'POST', 'params': lambda q: {'q': q, 'kl': 'cn-zh'}, 'parse': parse_duckduckgo, 'host': 'duckduckgo.com',
                   'blocked': r'anomaly|captcha|bots'},
    'bing': {'url': 'https://www.bing.com/search', 'method': 'GET', 'params': lambda q: {'q': q, 'setlang': 'zh-cn', 'ensearch': '0'}, 'parse': parse_bing, 'host': 'bing.com',
             'blocked': r'b_captcha|challenge|验证'},
    'baidu': {'url': 'https://www.baidu.com/s', 'method': 'GET', 'params': lambda q: {'wd': q, 'ie': 'utf-8', 'rn': 10}, 'parse': parse_baidu, 'host': 'baidu.com',
              'blocked': r'wappass|验证码|安全验证'},
}


def debug_dir():
    value = os.environ.get('LULU_SEARCH_DEBUG_DIR')
    return Path(value) if value else None


async def search_engine(engine, query, count=8, timeout=15, client=None):
    spec = ENGINES[engine]

    async def run(client):
        try:
            if spec['method'] == 'POST':
                response = await client.post(spec['url'], data=spec['params'](query))
            else:
                response = await client.get(spec['url'], params=spec['params'](query))
        except httpx.ConnectError:
            raise SearchError('network_unreachable', '无法连接搜索服务')
        except httpx.TimeoutException:
            raise SearchError('timeout', '搜索服务响应超时')
        except httpx.HTTPError as exc:
            raise SearchError('engine_error', str(exc)[:120])
        if response.status_code in (403, 429, 503):
            raise SearchError('engine_blocked', f'搜索引擎拒绝访问（HTTP {response.status_code}）')
        if response.status_code >= 400:
            raise SearchError('engine_error', f'HTTP {response.status_code}')
        page = decode_html(response.content, response.charset_encoding or '')
        results = [r for r in spec['parse'](page) if r['url'].startswith('http')]
        if len(results) < 2:
            # The engine's markup did not match: keep the page for diagnosis, then fall back to bare links.
            folder = debug_dir()
            if folder:
                try:
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder/f'{engine}-{int(time.time())}.html').write_text(page, encoding='utf-8', errors='replace')
                except OSError:
                    pass
            if re.search(spec['blocked'], page[:20000], re.I):
                raise SearchError('engine_blocked', '搜索引擎要求人工验证')
            generic = parse_generic(page, spec['host'])
            results = results or generic
            if len(results) < 3:
                raise SearchError('no_results', f'搜索引擎页面没有解析出结果（{len(results)} 条）')
        cleaned = []
        for r in results:
            if any(s in host_of(r['url']) for s in SKIP_HOSTS):
                continue
            cleaned.append(r)
            if len(cleaned) >= count:
                break
        return cleaned

    if client is not None:
        return await run(client)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=HEADERS, trust_env=False) as client:
        return await run(client)


async def search(query, count=8, engines=None, timeout=15, client=None):
    """Try engines in order until enough results are in hand. Returns (results, engine_used, failures);
    raises SearchError only when every engine failed."""
    failures, collected, used = [], [], []
    for engine in engines or DEFAULT_ENGINES:
        if engine not in ENGINES:
            continue
        try:
            results = await search_engine(engine, query, count, timeout, client)
            seen = {r['url'] for r in collected}
            collected.extend(r for r in results if r['url'] not in seen)
            used.append(engine)
            if len(collected) >= min(count, 4):
                return collected[:count], '+'.join(used), failures
        except SearchError as exc:
            failures.append({'engine': engine, 'reason': exc.reason, 'detail': exc.detail})
    if collected:
        return collected[:count], '+'.join(used), failures
    reasons = {f['reason'] for f in failures}
    detail = '；'.join(f"{f['engine']}：{f['detail']}" for f in failures)
    if reasons and reasons <= {'network_unreachable', 'timeout'}:
        raise SearchError('network_unreachable', '无法连接任何搜索服务，请检查网络。'+detail)
    if reasons == {'no_results'}:
        raise SearchError('no_results', '所有搜索引擎都没有返回结果。')
    raise SearchError('engine_blocked' if 'engine_blocked' in reasons else 'engine_error', '搜索服务不可用：'+detail)


# ------------------------------------------------------------------ fetch
async def fetch(url, max_chars=6000, timeout=15, client=None):
    await check_url_async(url)

    async def run(client):
        response = await client.get(url)
        response.raise_for_status()
        final = str(response.url)
        if final != url:
            await check_url_async(final)
        content_type = response.headers.get('content-type', '')
        if not any(k in content_type for k in ('html', 'text', 'json', 'xml')) and content_type:
            raise ValueError('该网址不是网页或文本内容')
        raw = response.content[:2_000_000]
        charset = response.charset_encoding or ''

        def parse():
            page = decode_html(raw, charset)
            if 'html' in content_type or page.lstrip()[:15].lower().startswith(('<!doctype', '<html')):
                return strip_html(page, max_chars)
            return '', page[:max_chars]
        # Decoding and stripping a 2MB page is CPU work; keep it off the event loop so the health check keeps answering.
        title, text = await asyncio.to_thread(parse)
        return {'url': final, 'title': title, 'text': text, 'status': response.status_code, 'fetched_at': time.strftime('%Y-%m-%dT%H:%M:%S')}

    if client is not None:
        return await run(client)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=HEADERS, trust_env=False, max_redirects=5) as client:
        return await run(client)


async def fetch_many(urls, max_chars=6000, timeout=15, concurrency=4, client=None):
    """Fetch several pages concurrently. Returns (pages, failures) preserving input order."""
    semaphore = asyncio.Semaphore(concurrency)
    pages, failures = [], []

    async def one(client, url):
        async with semaphore:
            try:
                pages.append(await fetch(url, max_chars, timeout, client))
            except Exception as exc:
                failures.append({'url': url, 'error': str(exc)[:160]})

    async def run(client):
        await asyncio.gather(*(one(client, u) for u in urls))
    if client is not None:
        await run(client)
    else:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=HEADERS, trust_env=False, max_redirects=5) as client:
            await run(client)
    order = {u: i for i, u in enumerate(urls)}
    pages.sort(key=lambda p: order.get(p['url'], 999))
    return pages, failures


# -------------------------------------------------------------------- CLI
async def _cli(query, engines):
    print('查询：', query)
    for engine in engines:
        try:
            results = await search_engine(engine, query, count=5)
            print(f'\n== {engine}: {len(results)} 条')
            for r in results:
                print(' -', r['title'][:60], '|', r['url'][:90], '|', r['snippet'][:80])
        except SearchError as exc:
            print(f'\n== {engine}: 失败 [{exc.reason}] {exc.detail}')
    try:
        results, used, failures = await search(query, engines=engines)
        print(f'\n综合：使用 {used}，跳过 {failures}')
        pages, bad = await fetch_many([r['url'] for r in results[:3]], max_chars=800)
        for p in pages:
            print('\n--', p['url'], '|', p['title'][:60], '\n', p['text'][:300].replace('\n', ' '))
        for b in bad:
            print('\n-- 抓取失败', b)
    except SearchError as exc:
        print('\n综合失败：', exc.reason, exc.detail)


if __name__ == '__main__':
    os.environ.setdefault('LULU_SEARCH_DEBUG_DIR', str(Path.cwd()/'search-debug'))
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    engines = next((a.split('=', 1)[1].split(',') for a in sys.argv[1:] if a.startswith('--engines=')), DEFAULT_ENGINES)
    asyncio.run(_cli(' '.join(args) or '今日BTC价格', engines))
