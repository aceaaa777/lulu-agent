"""General web research: queries → search → fetch → quote-grounded fact extraction.

The model never sees the open web directly. The program searches, fetches, and hands it page text; the model
may only state facts as verbatim quotes from that text, which the program verifies before anything is written.
"""
import difflib
import json
import re

from . import websearch
from .evidence import NEGATED

QUERY_SCHEMA = {'title': 'queries', 'type': 'object', 'additionalProperties': False,
                'properties': {'queries': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 3}}, 'required': ['queries']}
FACT_SCHEMA = {'title': 'facts', 'type': 'object', 'additionalProperties': False,
               'properties': {'facts': {'type': 'array', 'maxItems': 12, 'items': {'type': 'object', 'additionalProperties': False,
                              'properties': {'claim': {'type': 'string'}, 'quote': {'type': 'string'}, 'source': {'type': 'integer'}},
                              'required': ['claim', 'quote', 'source']}}}, 'required': ['facts']}

QUERY_SYSTEM = ('你是搜索助手。把用户的要求改写成1到3条适合搜索引擎的短查询词，只输出JSON。去掉“帮我/生成/一份/word/保存为”等与检索无关的词；'
                '涉及实时数据时加上“今日”或具体对象；有英文专名可再给一条英文查询。')
FACT_SYSTEM = ('你是资料核对员，只输出JSON。下面是编号的网页文本。请把与用户要求直接相关的事实逐条列出：claim 用中文一句话概括，'
               'quote 必须是对应网页文本中一字不差的连续原文（含数字与单位，20到200字），source 是网页编号。没有原文支持的内容不要写。'
               '价格、日期、数量类信息优先。找不到相关内容就返回空数组。')

FILLER = re.compile(r'帮我|请|生成|一份|写成|制作|做一份|保存为|保存成|导出|文档|文件|报告|的word|word|docx|pdf|excel|表格|并且|然后|一下|给我|我要|我想|需要|查一下|搜索|搜一下|查询|看看|是多少|多少钱', re.I)


def rule_queries(request, intent):
    positive = NEGATED.sub('', request)
    positive = re.split(r'\n用户答复', positive)[0]
    base = re.sub(r'[，。！？、“”"（）()：:；;]', ' ', FILLER.sub(' ', positive))
    base = re.sub(r'\s+', ' ', base).strip()
    queries = []
    if base:
        queries.append(base[:60])
    symbols = intent.get('symbols') or []
    if symbols and intent.get('needs_realtime'):
        queries.append(' '.join(symbols)+' price today'+(' '+' '.join(intent.get('platforms') or []) if intent.get('platforms') else ''))
    return [q for q in dict.fromkeys(queries) if q][:3]


async def make_queries(provider, request, intent, budget):
    rules = rule_queries(request, intent)
    if not provider.profile.get('supports_schema', True):
        return rules
    reply = await provider.chat([{'role': 'system', 'content': QUERY_SYSTEM}, {'role': 'user', 'content': request[:800]}],
                                schema=QUERY_SCHEMA, max_tokens=120, temperature=0, timeout=budget.step_timeout(1000, 120))
    try:
        model = [q.strip() for q in json.loads(reply.content).get('queries', []) if isinstance(q, str) and 2 <= len(q.strip()) <= 80] if not reply.failed else []
    except (ValueError, AttributeError):
        model = []
    merged = [q for q in dict.fromkeys(model+rules) if q]
    return merged[:3] or rules


def normalize(text):
    return re.sub(r'\s+', '', text.replace('，', ',').replace('：', ':')).lower()


NUMBER = re.compile(r'\d[\d,]*(?:\.\d+)?')


def _tokens(text):
    words = re.findall(r'[a-z0-9][a-z0-9.%+\-]*', text.lower())
    grams = set()
    for run in re.findall(r'[\u4e00-\u9fff]+', text):
        grams.update(run[i:i+2] for i in range(len(run)-1))
        if len(run) == 1:
            grams.add(run)
    return set(words) | grams


def quote_matches(quote, page_text):
    """Exact (whitespace/punctuation-insensitive) match, or an anchored near match: every number in the quote appears
    verbatim in the page and most of the surrounding words appear near one of those numbers. Small models drift on
    punctuation, spacing and bracketed asides; they must not drift on numbers."""
    q, t = normalize(quote), normalize(page_text)
    if not q or not t:
        return False, 'empty'
    if q in t:
        return True, 'exact'
    numbers = [n.replace(',', '') for n in NUMBER.findall(quote)]
    plain = t.replace(',', '')
    if numbers:
        if any(n not in plain for n in numbers):
            return False, 'number_missing'
        anchor = plain.find(numbers[0])
        window = plain[max(0, anchor-200):anchor+200]
        want = {tok for tok in _tokens(quote) if not re.fullmatch(r'[\d.,%+\-]+', tok)}
        if not want:
            return True, 'numbers_only'
        hit = sum(1 for tok in want if tok in window)
        ratio = hit/len(want)
        return (ratio >= 0.75, f'window_ratio={ratio:.2f}')
    matcher = difflib.SequenceMatcher(None, t, q, autojunk=False)
    block = matcher.find_longest_match(0, len(t), 0, len(q))
    if block.size < max(6, len(q)//3):
        return False, 'no_anchor'
    start = max(0, block.a-(block.b+4))
    ratio = difflib.SequenceMatcher(None, t[start:start+len(q)+8], q, autojunk=False).ratio()
    return (ratio >= 0.85, f'ratio={ratio:.2f}')


def verify_facts(candidates, pages, rejected=None):
    """Keep only facts whose quote really appears in the cited page. `rejected` collects (quote, reason) for the record."""
    verified = []
    for item in candidates:
        try:
            idx = int(item.get('source', 0))-1
            quote = str(item.get('quote', '')).strip()
            claim = str(item.get('claim', '')).strip()
        except (TypeError, ValueError):
            continue
        if not (0 <= idx < len(pages)) or len(quote) < 6 or not claim:
            if rejected is not None:
                rejected.append({'quote': quote[:120], 'source': item.get('source'), 'why': 'bad_source_or_short'})
            continue
        ok, why = quote_matches(quote, pages[idx]['text'])
        if ok:
            verified.append({'claim': claim[:200], 'quote': quote[:400], 'source': idx+1, 'url': pages[idx]['url'], 'title': pages[idx]['title'][:120]})
        elif rejected is not None:
            rejected.append({'quote': quote[:120], 'source': idx+1, 'why': why})
    return verified


def focus_text(text, terms, per_page):
    """Keep the parts of a page that mention the query terms or numbers, so the slice the model sees is the useful one."""
    if len(text) <= per_page:
        return text
    lines = [l for l in text.split('\n') if l.strip()]
    keep, size = [], 0
    def good(line):
        low = line.lower()
        return any(t.lower() in low for t in terms) or bool(re.search(r'\d', line))
    head = lines[:3]
    for line in head:
        keep.append(line); size += len(line)+1
    for line in lines[3:]:
        if size >= per_page:
            break
        if good(line):
            keep.append(line[:400]); size += min(len(line), 400)+1
    return '\n'.join(keep)[:per_page]


async def extract_facts(provider, request, pages, budget, terms=(), record=None):
    if not pages or not provider.profile.get('supports_schema', True):
        return []
    per_page = max(900, (budget.prompt_chars-len(request)-500)//max(1, len(pages)))
    numbered = [{'编号': i+1, '标题': p['title'][:100], '网址': p['url'][:120], '文本': focus_text(p['text'], terms, per_page)} for i, p in enumerate(pages)]
    prompt = json.dumps({'用户要求': request[:600], '网页': numbered}, ensure_ascii=False)
    reply = await provider.chat([{'role': 'system', 'content': FACT_SYSTEM}, {'role': 'user', 'content': prompt}],
                                schema=FACT_SCHEMA, max_tokens=700, temperature=0, timeout=budget.step_timeout(len(prompt), 700))
    if reply.failed:
        if record is not None:
            record['model_error'] = reply.content[:200]
        return []
    try:
        candidates = json.loads(reply.content).get('facts', [])
    except (ValueError, AttributeError):
        if record is not None:
            record['unparsed'] = (reply.content or '')[:300]
        return []
    rejected = []
    # The model may only quote from the focused slices it actually saw plus the full page; check against both.
    facts = verify_facts(candidates if isinstance(candidates, list) else [], pages, rejected)
    if record is not None:
        record['candidates'] = len(candidates) if isinstance(candidates, list) else 0
        record['rejected'] = rejected[:8]
    return facts


def rank_results(results, terms, limit):
    """Prefer results whose title/snippet mention the request's key terms; keep engine order otherwise."""
    def score(r):
        text = (r['title']+' '+r['snippet']).lower()
        return sum(1 for t in terms if t and t.lower() in text)
    ordered = sorted(enumerate(results), key=lambda pair: (-score(pair[1]), pair[0]))
    seen, out = set(), []
    for _, r in ordered:
        key = websearch.host_of(r['url'])+re.sub(r'[#?].*$', '', r['url'])
        if key in seen or r['url'].lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip')):
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= limit:
            break
    return out


async def research(provider, request, intent, budget, *, engines=None, max_pages=4, page_chars=6000, event=None, searcher=None):
    """Returns {'queries','results','pages','facts','failures','reason'}. reason is set when nothing usable came back.
    `searcher` is a searchapi provider (keyed API or the keyless scraper); None means the scraper."""
    from . import searchapi
    searcher = searcher or searchapi.SearchProvider()
    report = {'queries': [], 'results': [], 'pages': [], 'facts': [], 'failures': [], 'reason': '', 'provider': searcher.name}
    report['queries'] = await make_queries(provider, request, intent, budget)
    if event:
        event('search_started', {'queries': report['queries'], 'provider': searcher.name})
    results, engine_used, answers = [], None, []
    for query in report['queries']:
        try:
            found = await searcher.search(query, count=8, engines=engines)
            engine_used = found.get('provider') or searcher.name
            report['failures'].extend({'query': query, **f} for f in found.get('failures') or [])
            for r in found['results']:
                r['query'] = query
            results.extend(found['results'])
            if found.get('answer'):
                answers.append(found['answer'])
        except websearch.SearchError as exc:
            report['failures'].append({'query': query, 'engine': searcher.name, 'reason': exc.reason, 'detail': exc.detail})
        if len(results) >= max_pages*2:
            break
    if not results and not answers:
        reasons = {f['reason'] for f in report['failures']}
        report['reason'] = ('network_unreachable' if reasons <= {'network_unreachable', 'timeout'} and reasons else
                            'engine_blocked' if 'engine_blocked' in reasons else 'no_results')
        return report
    terms = [t for t in re.findall(r'[A-Za-z]{2,}|\d{2,}|[\u4e00-\u9fff]{2,4}', ' '.join(report['queries']))][:12]
    report['results'] = rank_results(results, terms, max_pages*2)
    if event:
        event('search_results', {'engine': engine_used, 'count': len(report['results']), 'top': [{'title': r['title'][:80], 'url': r['url']} for r in report['results'][:6]]})
    pages, bad = (await websearch.fetch_many([r['url'] for r in report['results'][:max_pages]], max_chars=page_chars)) if report['results'] else ([], [])
    if len(pages) < max_pages and len(report['results']) > max_pages:
        extra, bad2 = await websearch.fetch_many([r['url'] for r in report['results'][max_pages:max_pages*2]][:max_pages-len(pages)], max_chars=page_chars)
        pages.extend(extra); bad.extend(bad2)
    report['failures'].extend({'engine': 'fetch', 'reason': 'fetch_failed', **b} for b in bad)
    report['pages'] = [p for p in pages if len(p['text']) > 40]
    # Search snippets are real text from the engine and often carry the number a JS-rendered page hides; keep them as one more source.
    snippets = '\n'.join(f"{r['title']}：{r['snippet']}" for r in report['results'] if r.get('snippet'))
    if snippets:
        report['pages'].append({'url': 'search://'+(engine_used or 'web'), 'title': '搜索结果摘要', 'text': snippets[:page_chars], 'fetched_at': ''})
    # A keyed provider's own answer is real text it produced from the web; it is quotable like a page and cited as such.
    for answer in answers:
        report['pages'].append({'url': 'answer://'+(engine_used or searcher.name), 'title': searcher.label+' 的答案', 'text': answer[:page_chars], 'fetched_at': ''})
    if event:
        event('pages_fetched', {'count': len(report['pages']), 'urls': [p['url'] for p in report['pages']], 'failed': [b['url'] for b in bad]})
    if not report['pages']:
        report['reason'] = 'fetch_failed'
        return report
    record = {}
    report['facts'] = await extract_facts(provider, request, report['pages'], budget, terms, record)
    report['extraction'] = record
    if event:
        event('facts_verified', {'count': len(report['facts']), 'facts': [{'claim': f['claim'], 'source': f['url']} for f in report['facts'][:8]], **record})
    if not report['facts']:
        report['reason'] = 'no_grounded_facts'
    return report


REASON_TEXT = {'network_unreachable': '本机没有可用的网络连接', 'engine_blocked': '搜索引擎拒绝了自动访问（可能需要人工验证或稍后再试）',
               'engine_error': '搜索服务暂时不可用', 'no_results': '搜索没有返回结果', 'fetch_failed': '搜到了网页但都没能读取成功',
               'no_grounded_facts': '读到了网页，但没有找到能逐字核对的相关内容'}


def explain(report):
    reason = REASON_TEXT.get(report.get('reason', ''), report.get('reason', ''))
    details = []
    for f in report.get('failures', [])[:4]:
        if f.get('detail') or f.get('error'):
            details.append(f"{f.get('engine', '')}：{(f.get('detail') or f.get('error'))[:80]}")
    return reason+('（'+'；'.join(details)+'）' if details else '')


def numbers_grounded(body, sources_text, request=''):
    """Every multi-digit number in the body must appear in the evidence (or the request). Years and dates are ignored."""
    haystack = normalize(sources_text+' '+request).replace(',', '')
    missing = []
    for number in re.findall(r'\d[\d,]*(?:\.\d+)?', body):
        plain = number.replace(',', '')
        if len(plain.replace('.', '')) < 3 or re.fullmatch(r'(?:19|20)\d{2}', plain):
            continue
        if plain not in haystack:
            missing.append(number)
    return sorted(set(missing))
