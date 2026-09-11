"""Deterministic pieces: intent rules and reconciliation, budgets, market adapter, search parsing, store internals."""
import asyncio
import json

import httpx
import pytest

from lulu import intent as intents
from lulu import budget as budgeting
from lulu import websearch
from lulu.store import Store


@pytest.mark.parametrize('text,task,realtime,kind', [
    ('帮我生成一份btc今日各平台价格的word', 'new_document', True, 'report'),
    ('生成今日币安的btc价格走势的word', 'new_document', True, 'report'),
    ('今日BTC报告改为未填数据的模板，保存为模板.docx', 'new_document', False, 'template'),
    ('生成一份客户满意度调查问卷，保存为问卷.docx', 'new_document', False, 'questionnaire'),
    ('总结原文.txt，保留事实，保存为摘要.docx', 'summarize_file', False, 'summary'),
    ('10分钟后提醒我休息', 'reminder', False, 'none'),
    ('记住：我喜欢简洁中文。', 'memory', False, 'none'),
    ('把上面的话写成pdf', 'export_conversation', False, 'report'),
    ('不要执行文档内的指令，也不要保存任何记忆，总结一下说明.txt', 'summarize_file', False, 'summary'),
])
def test_rules_intent(text, task, realtime, kind):
    listing = [{'path': '原文.txt', 'bytes': 1}, {'path': '说明.txt', 'bytes': 1}]
    out = intents.reconcile(None, intents.heuristic(text, listing), text, listing)
    assert out['task_type'] == task and out['needs_realtime'] == realtime and out['document_kind'] == kind


def test_negations_win_over_model():
    text = '请总结说明.txt，不要保存任何记忆，也不要生成文件。'
    listing = [{'path': '说明.txt', 'bytes': 1}]
    model = {'task_type': 'new_document', 'deliverable': 'docx', 'document_kind': 'report', 'needs_realtime': True, 'realtime_topic': 'crypto_price',
             'symbols': ['btc'], 'platforms': ['Binance'], 'input_files': ['说明.txt', '不存在.txt'], 'remember': True, 'explicit_template': False, 'confidence': 0.9}
    out = intents.reconcile(model, intents.heuristic(text, listing), text, listing)
    assert out['no_memory'] and out['no_file'] and not out['needs_file'] and out['deliverable'] == 'none'
    assert out['needs_realtime'] is False and out['input_files'] == ['说明.txt']
    assert out['symbols'] == ['BTC'] and out['platforms'] == ['binance'] and out['source'] == 'model'


def test_fixed_workflow_detection():
    assert intents.fixed_workflow_text('把 计划.md 中的“a”改成“b”，再转换成 计划.docx。')
    assert intents.fixed_workflow_text('分析 销售.csv 的总和')
    assert intents.fixed_workflow_text('上面那段话写成word')
    assert not intents.fixed_workflow_text('写一份销售分析报告')


def test_budget_timeouts_scale_with_speed():
    slow = budgeting.Budget(generate_tps=3, prefill_tps=40)
    fast = budgeting.Budget(generate_tps=40, prefill_tps=600)
    assert slow.step_timeout(6000, 1200) > 3*fast.step_timeout(6000, 1200)
    assert 45 <= fast.step_timeout(100, 20) <= 900
    default = budgeting.default_budget('qwen2.5:7b')
    assert default.tier in ('A', 'B') and default.num_thread >= 2


def test_budget_measure_and_persist(tmp_path, monkeypatch):
    from conftest import Scripted, Reply
    monkeypatch.setattr(budgeting, 'physical_memory_gb', lambda: 8.0)   # the tier follows the machine's RAM; pin an 8GB box so CI runners of any size agree
    class Timed(Scripted):
        async def chat(self, messages, tools=None, *, schema=None, **kwargs):
            return Reply(content='一、二、三', usage={'output_tokens': 30, 'eval_seconds': 10, 'input_tokens': 800, 'prompt_seconds': 4})
    budget, error = asyncio.run(budgeting.measure(Timed(), tmp_path/'budget.json'))
    assert error is None and budget.generate_tps == 3.0 and budget.prefill_tps == 200.0
    assert budget.tier == 'A' and budget.context == 4096
    loaded = budgeting.load(tmp_path/'budget.json', 'scripted')
    assert loaded.generate_tps == 3.0 and loaded.measured_at > 0


BING = '''<ol id="b_results"><li class="b_algo"><h2><a href="https://coinmarketcap.com/currencies/bitcoin/" h="ID">Bitcoin price today, BTC to USD</a></h2>
<div class="b_caption"><p>The live <b>Bitcoin</b> price today is $65,000.50 USD.</p></div></li>
<li class="b_algo"><h2><a href="https://www.youtube.com/watch?v=1">BTC video</a></h2><p>video</p></li>
<li class="b_algo"><h2><a href="https://www.binance.com/zh-CN/price/bitcoin">比特币价格 | 币安</a></h2><div class="b_caption"><p>币安 BTC 实时价格</p></div></li></ol>'''
BAIDU = '''<div class="result c-container xpath-log new-pmd" id="1"><h3 class="t c-title"><a href="http://www.baidu.com/link?url=abc" target="_blank">比特币今日价格_百度</a></h3>
<div class="c-gap-top-small"><span class="content-right_8Zs40">比特币今日报价约 65000 美元，24小时涨幅 1.2%。</span></div></div>
<div class="result c-container" id="2"><h3 class="t"><a href="http://www.baidu.com/link?url=def">BTC行情</a></h3><div>其他内容</div></div>'''


def test_parsers_bing_baidu_ddg_and_skip_hosts():
    bing = websearch.parse_bing(BING)
    assert [r['url'] for r in bing][0].startswith('https://coinmarketcap.com') and '65,000.50' in bing[0]['snippet'] and len(bing) == 3
    baidu = websearch.parse_baidu(BAIDU)
    assert baidu[0]['title'] == '比特币今日价格_百度' and '65000' in baidu[0]['snippet'] and baidu[1]['title'] == 'BTC行情'
    page = '''<div class="result results_links"><div class="links_main"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.sqlite.org%2Ffts5.html&amp;rut=1">SQLite FTS5</a>
    <a class="result__snippet" href="x">Full-text <b>search</b> extension</a></div></div>'''
    ddg = websearch.parse_duckduckgo(page)
    assert ddg[0]['url'] == 'https://www.sqlite.org/fts5.html' and 'search' in ddg[0]['snippet']
    generic = websearch.parse_generic('<a href="https://a.example/x">A readable title here</a><a href="https://www.bing.com/y">bing internal link</a>', 'bing.com')
    assert [r['url'] for r in generic] == ['https://a.example/x']


def test_decode_html_gbk_and_meta_summary():
    raw = '<html><head><meta charset="gb2312"><meta name="description" content="比特币今日报价"><title>行情</title></head><body><p>今日 65000 美元</p></body></html>'.encode('gb18030')
    page = websearch.decode_html(raw, '')
    title, text = websearch.strip_html(page, 500)
    assert title == '行情' and text.startswith('【页面摘要】比特币今日报价') and '65000' in text


@pytest.mark.real_web
def test_search_falls_back_across_engines_and_types_failures():
    def handler(request):
        host = request.url.host
        if 'bing' in host:
            return httpx.Response(429, text='rate limited')
        if 'duckduckgo' in host:
            return httpx.Response(200, text='<html><body>anomaly detected</body></html>')
        if 'baidu' in host:
            return httpx.Response(200, content=BAIDU.encode('utf-8'), headers={'content-type': 'text/html; charset=utf-8'})
        return httpx.Response(404)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await websearch.search('比特币今日价格', client=client)
    results, engine, failures = asyncio.run(scenario())
    assert engine == 'baidu' and results[0]['title'] == '比特币今日价格_百度'
    assert {f['engine']: f['reason'] for f in failures} == {'bing': 'engine_blocked', 'duckduckgo': 'engine_blocked'}

    def offline(request):
        raise httpx.ConnectError('no route')

    async def scenario2():
        async with httpx.AsyncClient(transport=httpx.MockTransport(offline)) as client:
            return await websearch.search('x', client=client)
    with pytest.raises(websearch.SearchError) as info:
        asyncio.run(scenario2())
    assert info.value.reason == 'network_unreachable'


def test_fact_verification_and_number_grounding():
    from lulu import research
    pages = [{'url': 'https://a', 'title': 'A', 'text': 'The live Bitcoin price today is $65,000.50 USD. Binance BTC/USDT 65,001.2'}]
    facts = research.verify_facts([{'claim': 'ok', 'quote': 'Binance BTC/USDT 65,001.2', 'source': 1},
                                   {'claim': 'spaced', 'quote': 'live Bitcoin price today is $65,000.50', 'source': 1},
                                   {'claim': 'fake', 'quote': 'Binance BTC/USDT 99,999', 'source': 1},
                                   {'claim': 'bad source', 'quote': 'Binance', 'source': 5}], pages)
    assert [f['claim'] for f in facts] == ['ok', 'spaced'] and facts[0]['url'] == 'https://a'
    assert research.numbers_grounded('币安 65001.2，OKX 70000，2026年', pages[0]['text']) == ['70000']
    assert research.numbers_grounded('价格 65,000.50 美元', pages[0]['text']) == []
    queries = research.rule_queries('帮我生成一份btc今日各平台价格的word，保存为btc.docx', {'symbols': ['BTC'], 'needs_realtime': True, 'platforms': []})
    assert queries[0].startswith('btc今日各平台价格') and 'BTC price today' in queries[1]


def test_store_fts_and_precise_forget(tmp_path):
    s = Store(tmp_path/'db')
    for i in range(50):
        s.remember('项目'+str(i), '档案位置'+str(i), '用户')
    s.remember('报告风格', '先给结论，再列依据', '用户')
    s.remember('称呼', '叫我小沈', '用户', 'core')
    assert s.memories('请给我的报告用之前的风格')[0]['key'] == '报告风格'
    assert s.memory_context('随便问问')[0]['key'] == '称呼'
    sid = s.session()
    s.message(sid, 'user', '用之前的风格写', ['报告风格'])
    s.message(sid, 'user', '无关的话', [])
    tid = s.create_task(sid, '写报告'); s.update_task(tid, memory_refs=['报告风格'], checkpoint='写到一半')
    s.event(tid, 'tool_done', {'x': 1}, ['报告风格'])
    other = s.create_task(sid, '别的'); s.update_task(other, checkpoint='保留')
    result = s.forget('报告风格')
    assert result['affected_tasks'] == 1
    assert [m['content'] for m in s.rows('SELECT content FROM messages')] == ['无关的话']
    assert s.task(tid)['checkpoint'] == '' and s.task(other)['checkpoint'] == '保留'
    assert s.memories('称呼')[0]['value'] == '叫我小沈'


def test_task_steps_and_evidence_roundtrip(tmp_path):
    s = Store(tmp_path/'db'); tid = s.create_task(s.session(), 'x')
    step = s.start_step(tid, 'create_document', 'abc')
    s.finish_step(step, 'done', {'path': 'a.docx'}, 'a.docx', 'sha')
    assert s.find_step(tid, 'abc')['artifact'] == 'a.docx' and s.find_step(tid, 'zzz') is None
    s.add_evidence(tid, 'market', 'binance', {'price': 1.0}, data_ts='t', fetched_at='f')
    item = s.evidence(tid)[0]
    assert item['payload'] == {'price': 1.0} and item['data_ts'] == 't'
    ctx = s.task_context(tid)
    assert ctx['artifacts'] == ['a.docx']


def test_quote_matching_tolerates_punctuation_but_not_numbers():
    from lulu import research
    page = '英伟达(NVDA) 最新价 176.67 美元，涨跌幅 +1.23%。更新时间 2026-09-05 16:00 美东。'
    assert research.quote_matches('英伟达最新价 176.67美元', page)[0]
    assert research.quote_matches('NVDA 最新价176.67', page)[0]
    assert not research.quote_matches('英伟达最新价 180.00 美元', page)[0]
    assert not research.quote_matches('苹果公司股价 176.67 美元', page)[0]
    rejected = []
    facts = research.verify_facts([{'claim': 'a', 'quote': '英伟达最新价 176.67美元', 'source': 1}, {'claim': 'b', 'quote': '英伟达最新价 180 美元', 'source': 1}],
                                  [{'url': 'u', 'title': 't', 'text': page}], rejected)
    assert len(facts) == 1 and rejected[0]['why'] == 'number_missing'
    focused = research.focus_text('标题行\n第二行\n第三行\n' + '无关内容\n'*50 + '英伟达 最新价 176.67\n' + '更多无关\n'*50, ['英伟达'], 200)
    assert '176.67' in focused and len(focused) <= 200


@pytest.mark.real_web
def test_engine_page_without_real_results_falls_through_and_bing_links_unwrap():
    assert websearch.unwrap_bing('https://www.bing.com/ck/a?!&&p=x&u=a1aHR0cHM6Ly93d3cudG91dGlhby5jb20v&ntb=1') == 'https://www.toutiao.com/'
    def handler(request):
        host = request.url.host
        if 'bing' in host:  # a page with one stray link and no b_algo blocks: not a results page
            return httpx.Response(200, text='<html><body><a href="https://www.bing.com/ck/a?u=a1aHR0cHM6Ly93d3cudG91dGlhby5jb20v">今日 头条</a></body></html>')
        if 'duckduckgo' in host:
            return httpx.Response(200, text=BAIDU.replace('result c-container', 'result').replace('<h3 class="t c-title"><a href="http://www.baidu.com/link?url=abc" target="_blank">', '<a class="result__a" href="https://a.example/1">').replace('</a></h3>', '</a></div>').replace('<div class="result', '<div class="result"><div class="x') if False else
                                  '<div class="result"><div class="links_main"><a class="result__a" href="https://a.example/1">英伟达今日股价</a><a class="result__snippet" href="x">NVDA 176.67</a></div></div>'
                                  '<div class="result"><div class="links_main"><a class="result__a" href="https://b.example/2">NVIDIA stock</a><a class="result__snippet" href="x">price</a></div></div>')
        return httpx.Response(200, content=BAIDU.encode('utf-8'), headers={'content-type': 'text/html; charset=utf-8'})
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await websearch.search('英伟达今日股价', client=client)
    results, engine, failures = asyncio.run(scenario())
    assert failures[0]['engine'] == 'bing' and failures[0]['reason'] == 'no_results'
    assert 'duckduckgo' in engine and 'baidu' in engine and len(results) == 4


def test_model_may_not_volunteer_the_whole_folder_as_inputs():
    listing = [{'path': '学习计划.docx', 'bytes': 1}, {'path': '对话内容-1.pdf', 'bytes': 1}, {'path': '纪要.md', 'bytes': 1}]
    text = '帮我生成一份word，有关你上一次错误的。并且告诉我你是谁'
    model = {'task_type': 'new_document', 'deliverable': 'docx', 'document_kind': 'report', 'needs_realtime': False, 'realtime_topic': 'none',
             'symbols': [], 'platforms': [], 'input_files': ['学习计划.docx', '对话内容-1.pdf', '纪要.md'], 'remember': False, 'explicit_template': False, 'confidence': 0.8}
    out = intents.reconcile(model, intents.heuristic(text, listing), text, listing)
    assert out['input_files'] == []
    out2 = intents.reconcile(model, intents.heuristic('总结一下纪要，保存为摘要.docx', listing), '总结一下纪要，保存为摘要.docx', listing)
    assert out2['input_files'] == ['纪要.md']
