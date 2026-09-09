"""The eight skills with a scripted model: routing, slot questions, same-task resume, acceptance, memory hints."""
import asyncio
import json
from datetime import datetime, timedelta

from conftest import Scripted, run, call, Reply, Agent, Files, Store, online_web
from lulu import skills


def draft(body, status='deliverable', assumptions=(), questions=()):
    return Reply(content=json.dumps({'status': status, 'title': '', 'body_markdown': body, 'assumptions': list(assumptions), 'questions': list(questions), 'reason': ''}, ensure_ascii=False))


def summary(text, points=()):
    return Reply(content=json.dumps({'summary': text, 'points': list(points)}, ensure_ascii=False))


def resume(tmp_path, s, tid, answer, answers=(), facts=None):
    q = s.rows("SELECT * FROM questions WHERE task=? AND status='pending'", (tid,))[0]
    same, created = s.answer_question(q['id'], answer)
    assert same == tid and created
    p = Scripted(answers, facts=facts)
    asyncio.run(Agent(s, Files(tmp_path/'files'), p).run(tid, resume=tid))
    return p


def skill_of(s, tid):
    started = s.rows("SELECT detail FROM events WHERE task=? AND kind='skill_started'", (tid,))
    return json.loads(started[0]['detail'])['skill'] if started else None


# ---------------------------------------------------------------- routing
def test_router_picks_expected_skill(tmp_path):
    cases = {'把 报告.md 转成pdf': 'convert', '写一份周报，保存为周报.docx': 'generate', '总结一下 纪要.md': 'summarize', '记一下：明天要交房租': 'record',
             '记住：我的报告要先给结论': 'record', '明天早上8点提醒我开会': 'remind', '找一下本地有没有关于合同的文件': 'query', '现在BTC多少钱': 'query',
             '你还记得我的报告偏好吗': 'memory_qa', '忘掉我的报告偏好': 'memory_qa', '你是谁呀': 'chat', '今天心情不错': 'chat'}
    f = Files(tmp_path/'files'); f.write('报告.md', '正文'); f.write('纪要.md', '纪要正文')
    for text, expected in cases.items():
        s, f, tid, p = run(tmp_path, text, [Reply(content='好')])
        assert skill_of(s, tid) == expected, (text, skill_of(s, tid))


# ---------------------------------------------------------------- convert
def test_convert_named_file(tmp_path):
    f = Files(tmp_path/'files'); f.write('报告.md', '# 标题\n正文内容')
    s, f, tid, p = run(tmp_path, '把 报告.md 转成pdf', [])
    assert s.task(tid)['status'] == 'completed' and '报告.pdf' in s.task(tid)['answer'] and '正文内容' in f.read('报告.pdf')
    assert not p.calls


def test_convert_asks_for_file_then_format_and_resumes(tmp_path):
    f = Files(tmp_path/'files'); f.write('甲.md', '甲'); f.write('乙.md', '乙')
    s, f, tid, p = run(tmp_path, '帮我转换一下格式', [])
    assert s.task(tid)['status'] == 'awaiting_input'
    q = s.rows("SELECT * FROM questions WHERE task=?", (tid,))[0]
    assert '哪个文件' in q['question'] and set(json.loads(q['options'])) == {'甲.md', '乙.md'}
    resume(tmp_path, s, tid, '乙.md')
    assert s.task(tid)['status'] == 'awaiting_input'
    q2 = s.rows("SELECT * FROM questions WHERE task=? AND status='pending'", (tid,))[0]
    assert '什么格式' in q2['question'] and json.loads(q2['options']) == skills.FORMAT_OPTIONS
    resume(tmp_path, s, tid, '2')
    assert s.task(tid)['status'] == 'completed' and f.path('乙.docx').exists()
    assert len(s.rows('SELECT * FROM tasks')) == 1


# --------------------------------------------------------------- generate
def test_generate_without_materials_asks_then_writes(tmp_path):
    """A small model never drafts from nothing: no file, no points, no history → a materials question, zero model calls."""
    s, f, tid, p = run(tmp_path, '写一份下周学习计划，保存为学习计划.docx', [draft('# 学习计划\n周一阅读，周二复习。')])
    assert s.task(tid)['status'] == 'awaiting_input' and not f.listing() and not p.calls
    q = s.rows("SELECT * FROM questions WHERE task=?", (tid,))[0]
    assert '要点' in q['question'] and json.loads(q['options']) == skills.MATERIAL_OPTIONS
    p = resume(tmp_path, s, tid, '周一阅读英语，周二复习数学，每天一小时', [draft('# 学习计划\n周一阅读，周二复习。', assumptions=['按每天一小时安排'])])
    assert s.task(tid)['status'] == 'completed' and '学习计划.docx' in s.task(tid)['answer']
    body = f.read('学习计划.docx')
    assert body.startswith('学习计划') and '口径说明' in body and '每天一小时' in body
    assert len(p.calls) == 1 and '每天一小时' in json.dumps(p.prompts[-1], ensure_ascii=False)


def test_generate_with_inline_points_writes_directly(tmp_path):
    s, f, tid, p = run(tmp_path, '写一份下周学习计划，要点：周一英语、周二数学、周三复盘，保存为学习计划.docx', [draft('# 学习计划\n周一英语，周二数学，周三复盘。')])
    assert s.task(tid)['status'] == 'completed' and f.path('学习计划.docx').exists() and len(p.calls) == 1


def test_generate_template_option_needs_no_points(tmp_path):
    s, f, tid, p = run(tmp_path, '写一份周报，保存为周报.docx', [])
    assert s.task(tid)['status'] == 'awaiting_input'
    p = resume(tmp_path, s, tid, '先做空模板', [draft('# 周报模板\n本周工作：待填写\n下周计划：待填写')])
    assert s.task(tid)['status'] == 'completed' and '待填写' in f.read('周报.docx')
    assert '模板' in json.dumps(p.prompts[-1], ensure_ascii=False)


def test_generate_file_option_then_picks_source(tmp_path):
    f = Files(tmp_path/'files'); f.write('原文.txt', '负责人：陆遥\n预算：18650'); f.write('备忘.md', '备忘')
    s, f, tid, p = run(tmp_path, '写一份项目报告，保存为报告.docx', [])
    assert s.task(tid)['status'] == 'awaiting_input'
    resume(tmp_path, s, tid, '选参考文件', [])
    q = s.rows("SELECT * FROM questions WHERE task=? AND status='pending'", (tid,))[0]
    assert '哪个文件' in q['question'] and set(json.loads(q['options'])) == {'原文.txt', '备忘.md'}
    p = resume(tmp_path, s, tid, '原文.txt', [draft('# 项目报告\n负责人：陆遥\n预算：18650')])
    assert s.task(tid)['status'] == 'completed' and '陆遥' in f.read('报告.docx')
    assert '18650' in json.dumps(p.prompts[-1], ensure_ascii=False)


def test_generate_derives_filename(tmp_path):
    s, f, tid, p = run(tmp_path, '帮我生成一份关于团队周会的word，内容：本周完成了登录页，下周做支付。', [draft('# 团队周会\n内容')])
    assert s.task(tid)['status'] == 'completed'
    names = [i['path'] for i in f.listing()]
    assert names and names[0].endswith('.docx') and '团队周会' in names[0]


def test_generate_clarification_becomes_question_after_insist(tmp_path):
    f = Files(tmp_path/'files'); f.write('原文.txt', '负责人：陆遥\n预算：18650')
    asking = draft('', status='needs_input', questions=['项目名称是什么？'])
    s, f, tid, p = run(tmp_path, '根据原文.txt写一份项目计划，保存为计划.docx', [asking, asking])
    assert s.task(tid)['status'] == 'awaiting_input' and not f.path('计划.docx').exists()
    assert any(e['kind'] == 'draft_retry' for e in s.rows('SELECT kind FROM events WHERE task=?', (tid,)))
    p = resume(tmp_path, s, tid, '项目叫青松计划', [draft('# 青松计划\n负责人：陆遥\n预算：18650')])
    assert s.task(tid)['status'] == 'completed' and '青松' in f.read('计划.docx')


def test_generate_fabricated_facts_get_one_retry_then_pause(tmp_path):
    f = Files(tmp_path/'files'); f.write('原文.txt', '负责人：陆遥\n预算：18650')
    bad = draft('项目负责人是张三，预算为500元。')
    s, f, tid, p = run(tmp_path, '根据原文.txt写一份项目报告，保存为报告.docx', [bad, bad])
    assert s.task(tid)['status'] == 'paused' and '还没做好' in s.task(tid)['answer'] and not f.path('报告.docx').exists()
    assert any(e['kind'] == 'generate_retry' for e in s.rows('SELECT kind FROM events WHERE task=?', (tid,)))
    assert '上一稿的问题' in json.dumps(p.prompts[-1], ensure_ascii=False)


def test_generate_asking_body_is_blocked(tmp_path):
    s, f, tid, p = run(tmp_path, '写一份项目总结，要点：一、完成了登录页；二、支付延期一周，保存为总结.docx', [draft('请提供项目的背景信息、参与人员与成果，以便我生成完整文档。'), draft('请提供项目的背景信息。')])
    assert s.task(tid)['status'] == 'awaiting_input' and not f.listing() and 'judge' in p.schema_calls


def test_generate_realtime_offline_pauses(tmp_path):
    s, f, tid, p = run(tmp_path, '帮我生成一份btc今日各平台价格的word', [])
    assert s.task(tid)['status'] == 'awaiting_input' and not f.listing() and len(p.calls) == 0
    assert '网络' in s.rows("SELECT question FROM questions WHERE task=?", (tid,))[0]['question']


def test_generate_realtime_with_web_facts(tmp_path, monkeypatch):
    pages = [{'url': 'https://example.com/btc', 'title': 'Bitcoin price', 'text': 'Binance BTC/USDT 65,001.2, OKX 65,010.0. Updated 2026-09-07.'}]
    facts = [{'claim': '币安价格 65,001.2', 'quote': 'Binance BTC/USDT 65,001.2', 'source': 1}, {'claim': 'OKX 65,010.0', 'quote': 'OKX 65,010.0', 'source': 1}]
    online_web(monkeypatch, pages)
    s, f, tid, p = run(tmp_path, '帮我生成一份btc今日各平台价格的word，保存为btc.docx', [draft('# BTC 今日价格\n币安 65,001.2 USDT，OKX 65,010.0 USDT。')], facts=facts)
    assert s.task(tid)['status'] == 'completed' and '65,001.2' in f.read('btc.docx')


# -------------------------------------------------------------- summarize
def test_summarize_named_file_and_numbers_grounded(tmp_path):
    f = Files(tmp_path/'files'); f.write('纪要.md', '会议决定：预算 18650，负责人陆遥，9月20日交付。')
    s, f, tid, p = run(tmp_path, '总结一下 纪要.md', [summary('预算 99999，负责人陆遥。'), summary('预算 18650，负责人陆遥，9月20日交付。', ['预算 18650'])])
    assert s.task(tid)['status'] == 'completed' and '18650' in s.task(tid)['answer'] and '99999' not in s.task(tid)['answer']
    assert any(e['kind'] == 'summary_retry' for e in s.rows('SELECT kind FROM events WHERE task=?', (tid,)))


def test_summarize_extract_fields_verified(tmp_path):
    f = Files(tmp_path/'files'); f.write('原文.txt', '代号：青松731\n负责人：陆遥\n预算：18650')
    extracted = Reply(content=json.dumps({'fields': [{'name': '负责人', 'value': '陆遥', 'quote': '负责人：陆遥'}, {'name': '预算', 'value': '500', 'quote': '预算：500'}]}, ensure_ascii=False))
    s, f, tid, p = run(tmp_path, '读取原文.txt，提取负责人、预算、截止日期三项事实。', [extracted])
    a = s.task(tid)['answer']
    assert '负责人：陆遥' in a and '500' not in a and '没有找到' in a and '截止日期' in a


def test_summarize_table_needs_no_model_and_can_save(tmp_path):
    f = Files(tmp_path/'files'); f.write('销售.csv', rows=[['月份', '金额'], ['一月', 12], ['二月', 18]])
    s, f, tid, p = run(tmp_path, '统计一下 销售.csv，保存为统计.md', [])
    assert s.task(tid)['status'] == 'completed' and '总和 30' in s.task(tid)['answer'] and '总和 30' in f.read('统计.md') and not p.calls


def test_summarize_previous_answer(tmp_path):
    s, f, tid, p = run(tmp_path, '写一句关于秋天的话', [Reply(content='秋天的风带着桂花香，傍晚的天空很高。')])
    s, f, tid2, p = run(tmp_path, '总结一下上面这段', [summary('秋天傍晚天空高远，有桂花香。')], s, session=s.task(tid)['session'])
    assert s.task(tid2)['status'] == 'completed' and '桂花' in s.task(tid2)['answer']


def test_summarize_asks_which_file(tmp_path):
    f = Files(tmp_path/'files'); f.write('甲.md', '甲'); f.write('乙.md', '乙')
    s, f, tid, p = run(tmp_path, '帮我总结一下文件', [])
    assert s.task(tid)['status'] == 'awaiting_input'
    assert set(json.loads(s.rows('SELECT options FROM questions WHERE task=?', (tid,))[0]['options'])) == {'甲.md', '乙.md'}


# ----------------------------------------------------------------- record
def test_record_note_and_memory(tmp_path):
    s, f, tid, p = run(tmp_path, '记一下：明天要交房租', [])
    assert s.task(tid)['status'] == 'completed' and not p.calls
    notes = [i['path'] for i in f.listing() if i['path'].startswith('笔记/')]
    assert notes and '明天要交房租' in f.read(notes[0])
    s, f, tid2, p = run(tmp_path, '记住：我的报告要先给结论再列依据', [], s)
    assert s.task(tid2)['status'] == 'completed' and s.memories()[0]['value'].startswith('我的报告要先给结论')
    assert s.memories()[0]['source'] == '记住：我的报告要先给结论再列依据'


# ----------------------------------------------------------------- remind
def test_remind_parses_time_and_asks_when_missing(tmp_path):
    s, f, tid, p = run(tmp_path, '明天早上8点提醒我开会', [])
    assert s.task(tid)['status'] == 'completed' and not p.calls
    r = s.rows("SELECT * FROM reminders WHERE status='pending'")[0]
    due = datetime.fromtimestamp(r['due'])
    assert r['text'] == '开会' and due.hour == 8 and due.date() == (datetime.now()+timedelta(days=1)).date()
    s, f, tid2, p = run(tmp_path, '提醒我交周报', [], s)
    assert s.task(tid2)['status'] == 'awaiting_input'
    assert json.loads(s.rows('SELECT options FROM questions WHERE task=?', (tid2,))[0]['options']) == skills.TIME_OPTIONS
    resume(tmp_path, s, tid2, '30分钟后')
    assert s.task(tid2)['status'] == 'completed'
    texts = [r['text'] for r in s.rows("SELECT text FROM reminders WHERE status='pending'")]
    assert any('交周报' in t for t in texts)


def test_remind_list_and_cancel(tmp_path):
    s = Store(tmp_path/'db'); s.add_reminder('喝水', datetime.now().timestamp()+600)
    s, f, tid, p = run(tmp_path, '查看一下提醒', [], s)
    assert '喝水' in s.task(tid)['answer']
    s, f, tid, p = run(tmp_path, '取消喝水的提醒', [], s)
    assert s.task(tid)['status'] == 'completed' and not s.rows("SELECT * FROM reminders WHERE status='pending'")


# ------------------------------------------------------------------ query
def test_query_local_files(tmp_path):
    f = Files(tmp_path/'files'); f.write('合同草案.md', '本合同预算15000元'); f.write('其他.md', '无关')
    s, f, tid, p = run(tmp_path, '找一下本地有没有关于合同的文件', [])
    assert s.task(tid)['status'] == 'completed' and '合同草案.md' in s.task(tid)['answer'] and '其他.md' not in s.task(tid)['answer'] and not p.calls


def test_query_web_answer_with_sources(tmp_path, monkeypatch):
    pages = [{'url': 'https://example.com/nvda', 'title': 'NVDA', 'text': '英伟达(NVDA) 最新价 176.67 美元，涨跌幅 +1.23%。'}]
    facts = [{'claim': '英伟达最新价 176.67 美元', 'quote': '英伟达(NVDA) 最新价 176.67 美元', 'source': 1}]
    online_web(monkeypatch, pages)
    answer = Reply(content=json.dumps({'answer': '英伟达最新价 176.67 美元（来源：example.com）。'}, ensure_ascii=False))
    s, f, tid, p = run(tmp_path, '查一下今天美股英伟达的价格', [answer], facts=facts)
    assert s.task(tid)['status'] == 'completed' and '176.67' in s.task(tid)['answer'] and 'example.com' in s.task(tid)['answer']


def test_query_web_fabricated_number_is_regrounded(tmp_path, monkeypatch):
    pages = [{'url': 'https://example.com/nvda', 'title': 'NVDA', 'text': '英伟达(NVDA) 最新价 176.67 美元。'}]
    facts = [{'claim': '英伟达最新价 176.67 美元', 'quote': '英伟达(NVDA) 最新价 176.67 美元', 'source': 1}]
    online_web(monkeypatch, pages)
    s, f, tid, p = run(tmp_path, '查一下今天美股英伟达的价格', [Reply(content=json.dumps({'answer': '英伟达 199.99 美元'}))], facts=facts)
    assert '199.99' not in s.task(tid)['answer'] and '176.67' in s.task(tid)['answer']


def test_query_web_offline_asks(tmp_path):
    s, f, tid, p = run(tmp_path, '查一下今天美股英伟达的价格', [])
    assert s.task(tid)['status'] == 'awaiting_input' and len(p.calls) == 0


# ------------------------------------------------------------- memory_qa
def test_memory_qa_lists_and_forgets(tmp_path):
    s = Store(tmp_path/'db'); s.remember('报告风格', '先给结论再列依据', '用户'); s.remember('称呼', '叫我小沈', '用户')
    s, f, tid, p = run(tmp_path, '你还记得我的报告偏好吗', [], s)
    assert '先给结论' in s.task(tid)['answer'] and not p.calls
    s, f, tid, p = run(tmp_path, '忘掉我的报告风格', [], s)
    assert s.task(tid)['status'] == 'completed' and [m['key'] for m in s.memories()] == ['称呼']


def test_memory_qa_forget_asks_when_ambiguous(tmp_path):
    s = Store(tmp_path/'db'); s.remember('报告风格', '先给结论', '用户'); s.remember('报告语言', '中文', '用户')
    s, f, tid, p = run(tmp_path, '忘掉关于报告的记忆', [], s)
    assert s.task(tid)['status'] == 'awaiting_input'
    assert set(json.loads(s.rows('SELECT options FROM questions WHERE task=?', (tid,))[0]['options'])) == {'报告风格', '报告语言'}
    resume(tmp_path, s, tid, '报告语言')
    assert [m['key'] for m in s.memories()] == ['报告风格']


# ------------------------------------------------------------------- chat
def test_chat_answers_directly_and_proposes_memory(tmp_path):
    s = Store(tmp_path/'db'); f = Files(tmp_path/'files')
    tid = s.create_task(s.session(), '我平时喜欢简短的回答，你是谁呀')
    p = Scripted([Reply(content='我是 Lulu。')])
    p.candidates = [{'key': '回答风格', 'value': '喜欢简短的回答', 'quote': '喜欢简短的回答'}, {'key': '假的', 'value': 'x', 'quote': '这句话不存在'}]
    asyncio.run(Agent(s, f, p).run(tid))
    assert s.task(tid)['status'] == 'completed' and s.task(tid)['answer'] == '我是 Lulu。'
    cands = s.memory_candidates()
    assert [c['key'] for c in cands] == ['回答风格'] and not s.memories()
    s.resolve_candidate(cands[0]['id'], True)
    assert s.memories()[0]['key'] == '回答风格' and not s.memory_candidates()


# ------------------------------------------------------ 0.6: rules-first routing
def test_rules_route_without_any_model_call(tmp_path):
    """Decisive phrases settle the skill before the classifier runs: zero schema calls for these."""
    f = Files(tmp_path/'files'); f.write('合同.md', '甲方乙方')
    cases = {'明天早上8点提醒我开会': 'remind', '取消喝水的提醒': 'remind', '你还记得我的报告偏好吗': 'memory_qa', '忘掉关于报告的记忆': 'memory_qa',
             '记一下：明天交房租': 'record', '记住：报告先给结论': 'record', '把 合同.md 转成pdf': 'convert', '帮我转换一下格式': 'convert',
             '把这段翻译成英文：今天天气很好': 'translate', '“good morning”中文怎么说': 'translate', '总结一下 合同.md': 'summarize', '提取 合同.md 里的甲方、乙方': 'summarize',
             '写一份周报，保存为周报.docx': 'generate', '帮我生成一份关于团队周会的word': 'generate',
             '找一下本地有没有关于合同的文件': 'query', '查一下今天英伟达的股价': 'query', '听说苹果要出折叠屏了？': 'query', 'Qwen3 是开源的吗': 'query',
             '比特币减半是真的吗': 'query', '你是谁呀': 'chat', '今天心情不错': 'chat', '谢谢你': 'chat', '你能做什么': 'chat'}
    listing = [{'path': '合同.md'}]
    for text, expected in cases.items():
        assert skills.route_rules(text, listing) == expected, (text, skills.route_rules(text, listing))
    assert skills.route_rules('记住我的生日，然后写一份生日计划保存为计划.docx', listing) is None  # two jobs: classifier decides
    s, f, tid, p = run(tmp_path, '明天早上8点提醒我开会', [])
    assert skill_of(s, tid) == 'remind' and 'intent' not in p.schema_calls
    s, f, tid, p = run(tmp_path, '你是谁呀', [Reply(content='我是 Lulu。')])
    assert skill_of(s, tid) == 'chat' and 'intent' not in p.schema_calls and s.task(tid)['answer'] == '我是 Lulu。'
    intent = json.loads(s.rows("SELECT detail FROM events WHERE task=? AND kind='intent'", (tid,))[0]['detail'])
    assert intent['source'] == 'rules' and intent['skill_hint'] == 'chat'


def test_question_without_web_falls_back_to_model_knowledge(tmp_path):
    """‘xx是真的吗’ is a query; offline it answers from the model and says so, instead of pausing."""
    s, f, tid, p = run(tmp_path, '比特币每四年减半是真的吗', [Reply(content='是的，大约每四年一次。')])
    assert skill_of(s, tid) == 'query' and s.task(tid)['status'] == 'completed'
    assert '没能联网核实' in s.task(tid)['answer'] and '每四年' in s.task(tid)['answer']
    assert any(e['kind'] == 'answer_unverified' for e in s.rows('SELECT kind FROM events WHERE task=?', (tid,)))


def test_realtime_question_offline_still_pauses(tmp_path):
    s, f, tid, p = run(tmp_path, '查一下今天英伟达的股价', [Reply(content='大约 180 美元')])
    assert s.task(tid)['status'] == 'awaiting_input' and not p.calls
    assert '网络' in s.rows("SELECT question FROM questions WHERE task=?", (tid,))[0]['question']


# ----------------------------------------------------------------- translate
def translation(text):
    return Reply(content=json.dumps({'translation': text}, ensure_ascii=False))


def test_translate_inline_text_to_english(tmp_path):
    s, f, tid, p = run(tmp_path, '把这句翻译成英文：会议改到9月20日下午三点。', [translation('The meeting is moved to 3 p.m. on September 20.')])
    assert skill_of(s, tid) == 'translate' and s.task(tid)['status'] == 'completed'
    assert s.task(tid)['answer'].startswith('The meeting') and not f.listing() and len(p.calls) == 1
    prompt = json.loads(p.prompts[-1][-1]['content'])
    assert prompt['目标语言'] == '英文' and prompt['原文'] == '会议改到9月20日下午三点。'


def test_translate_detects_direction_and_checks_numbers(tmp_path):
    s, f, tid, p = run(tmp_path, '翻译一下：Please pay 18650 yuan before Friday.', [translation('请在周五前支付 99999 元。'), translation('请在周五前支付 18650 元。')])
    assert s.task(tid)['status'] == 'completed' and '18650' in s.task(tid)['answer'] and '99999' not in s.task(tid)['answer']
    assert json.loads(p.prompts[0][-1]['content'])['目标语言'] == '中文'
    assert any(e['kind'] == 'translate_retry' for e in s.rows('SELECT kind FROM events WHERE task=?', (tid,)))


def test_translate_file_writes_translation_file(tmp_path):
    f = Files(tmp_path/'files'); f.write('说明.md', '第一段。\n\n第二段，共 3 条。')
    s, f, tid, p = run(tmp_path, '把 说明.md 翻译成英文', [translation('Paragraph one.\n\nParagraph two, 3 items.')])
    assert s.task(tid)['status'] == 'completed' and f.path('译文-说明.md').exists() and '3 items' in f.read('译文-说明.md')
    assert '译文-说明.md' in s.task(tid)['answer']


def test_translate_without_text_asks_and_resumes(tmp_path):
    s, f, tid, p = run(tmp_path, '帮我翻译成日文', [])
    assert s.task(tid)['status'] == 'awaiting_input' and '要翻译的文字' in s.rows("SELECT question FROM questions WHERE task=?", (tid,))[0]['question']
    p = resume(tmp_path, s, tid, '早上好', [translation('おはようございます')])
    assert s.task(tid)['status'] == 'completed' and 'おはよう' in s.task(tid)['answer']
    assert json.loads(p.prompts[-1][-1]['content']) == {'目标语言': '日文', '原文': '早上好'}


# ----------------------------------------------------------------- thinking
def test_think_switch_reaches_generative_slots_only(tmp_path):
    class Recording(Scripted):
        def __init__(self, *a, **k):
            super().__init__(*a, **k); self.think_flags = []
        async def chat(self, messages, tools=None, *, schema=None, **kwargs):
            self.think_flags.append((schema.get('title') if schema else 'text', kwargs.get('think', False)))
            return await super().chat(messages, tools, schema=schema, **kwargs)
    s = Store(tmp_path/'db'); f = Files(tmp_path/'files'); f.write('纪要.md', '会议决定：预算 18650，负责人陆遥。')
    p = Recording([summary('预算 18650，负责人陆遥。')])
    agent = Agent(s, f, p, think=True)
    tid = s.create_task(s.session(), '总结一下 纪要.md')
    asyncio.run(agent.run(tid))
    assert ('summary', True) in p.think_flags
    assert all(flag is False for title, flag in p.think_flags if title in ('intent', 'candidates', 'memory'))
    thinking_event = [json.loads(e['detail']) for e in s.rows("SELECT detail FROM events WHERE task=? AND kind='thinking'", (tid,))]
    agent.set_think(False)
    assert agent.writer.think is False
    p2 = Recording([Reply(content='你好')])
    tid2 = s.create_task(s.session(), '你好呀')
    agent.set_provider(p2)
    asyncio.run(agent.run(tid2))
    assert ('text', False) in p2.think_flags and s.task(tid2)['answer'] == '你好'


# ------------------------------------------ 0.6.1: the three failures from the first real session
def test_translate_previous_file_reference_uses_the_last_artifact(tmp_path):
    """‘帮我把上一份文件翻译成英文’ must translate the file Lulu just produced, not the words ‘上一份文件’."""
    f = Files(tmp_path/'files'); f.write('对话内容.md', '第一段。\n\n第二段，共 3 条。')
    s, f, tid, p = run(tmp_path, '把 对话内容.md 转成pdf', [])
    assert s.task(tid)['status'] == 'completed'
    session = s.task(tid)['session']
    p = Scripted([translation('Paragraph one.\n\nParagraph two, 3 items.')])
    tid2 = s.create_task(session, '帮我把上一份文件翻译成英文')
    asyncio.run(Agent(s, Files(tmp_path/'files'), p).run(tid2))
    assert s.task(tid2)['status'] == 'completed' and f.path('译文-对话内容.md').exists()
    assert '第二段' in json.loads(p.prompts[-1][-1]['content'])['原文']


def test_follow_up_correction_reuses_previous_skill(tmp_path):
    """‘我是说上一份文件的内容’ after a translation is a correction of that translation — never a reminder."""
    f = Files(tmp_path/'files'); f.write('对话内容.md', '正文，共 3 条。')
    s, f, tid, p = run(tmp_path, '把 对话内容.md 转成pdf', [])
    session = s.task(tid)['session']
    tid2 = s.create_task(session, '帮我把上一份翻译成英文')
    asyncio.run(Agent(s, Files(tmp_path/'files'), Scripted([translation('Body, 3 items.')])).run(tid2))
    p = Scripted([translation('Body text, 3 items.')])
    tid3 = s.create_task(session, '我是说上一份文件的内容，')
    asyncio.run(Agent(s, Files(tmp_path/'files'), p).run(tid3))
    assert skill_of(s, tid3) == 'translate' and 'intent' not in p.schema_calls
    assert any(e['kind'] == 'follow_up' for e in s.rows('SELECT kind FROM events WHERE task=?', (tid3,)))
    assert s.task(tid3)['status'] == 'completed' and '提醒' not in s.task(tid3)['answer']


def test_model_cannot_invent_a_reminder_or_memory_job(tmp_path):
    """The classifier may say ‘reminder’; without the user's own reminder words the program overrides it."""
    class Misled(Scripted):
        async def chat(self, messages, tools=None, *, schema=None, **kwargs):
            if schema and schema.get('title') == 'intent':
                self.schema_calls.append('intent')
                from lulu import intent as intents
                text = json.loads(messages[-1]['content'])['用户请求']
                wrong = dict(intents.heuristic(text)); wrong['task_type'] = 'reminder'
                return Reply(content=json.dumps(wrong, ensure_ascii=False))
            return await super().chat(messages, tools, schema=schema, **kwargs)
    s = Store(tmp_path/'db'); f = Files(tmp_path/'files')
    tid = s.create_task(s.session(), '这个项目的负责人和预算分别是什么，帮我看看资料里有没有写')
    p = Misled([Reply(content='资料里没有写负责人和预算。')])
    asyncio.run(Agent(s, f, p).run(tid))
    assert skill_of(s, tid) != 'remind' and '什么时候提醒' not in (s.task(tid)['answer'] or '')
    assert not s.rows("SELECT * FROM reminders")


def test_question_about_news_offline_does_not_hang_or_pause(tmp_path):
    """‘我听说openai越狱了？’: a query; offline it answers from the model with the unverified note instead of freezing."""
    s, f, tid, p = run(tmp_path, '我听说openai越狱了？', [Reply(content='没有可靠消息表明这件事发生过。')])
    assert skill_of(s, tid) == 'query' and s.task(tid)['status'] == 'completed' and '没能联网核实' in s.task(tid)['answer']


def test_translate_that_file_and_filename_answer(tmp_path):
    """‘翻译一下该文件’ resolves the reference; answering the source question with ‘1.docx’ means that file, not the text ‘1.docx’."""
    f = Files(tmp_path/'files'); f.write('1.docx', '合同正文，共 3 条。')
    s, f, tid, p = run(tmp_path, '翻译一下该文件', [translation('Contract body, 3 items.')])
    assert skill_of(s, tid) == 'translate' and s.task(tid)['status'] == 'completed' and f.path('译文-1.docx').exists()
    f.write('2.docx', '第二份，共 5 条。')
    s2, f2, tid2, p2 = run(tmp_path, '帮我翻译成英文', [])
    assert s2.task(tid2)['status'] == 'awaiting_input'
    p3 = resume(tmp_path, s2, tid2, '2.docx', [translation('Second one, 5 items.')])
    assert s2.task(tid2)['status'] == 'completed' and '第二份' in json.loads(p3.prompts[-1][-1]['content'])['原文'] and f2.path('译文-2.docx').exists()


# ---------------------------------------------------- 0.7: tags force the skill; three new skills
def forced(tmp_path, text, skill, answers, files=(), options=None, store=None, session=None):
    """What the tag row sends: skill + chosen files + options; the classifier is never consulted."""
    s = store or Store(tmp_path/'db'); f = Files(tmp_path/'files')
    tid = s.create_task(session or s.session(), text)
    s.update_task(tid, intent={'forced': {'skill': skill, 'files': list(files), 'options': options or {}}})
    p = Scripted(answers)
    asyncio.run(Agent(s, f, p).run(tid))
    return s, f, tid, p


def test_tag_forces_skill_and_options_without_classifier(tmp_path):
    f = Files(tmp_path/'files'); f.write('纪要.md', '会议决定：预算 18650，负责人陆遥。')
    s, f, tid, p = forced(tmp_path, '明天早上8点提醒我开会', 'translate', [translation('Remind me of the meeting at 8 tomorrow morning.')], options={'lang': '英文'})
    assert skill_of(s, tid) == 'translate' and 'intent' not in p.schema_calls and s.task(tid)['answer'].startswith('Remind me')
    assert json.loads(p.prompts[-1][-1]['content'])['目标语言'] == '英文'
    s, f, tid, p = forced(tmp_path, '', 'summarize', [summary('预算 18650，负责人陆遥。')], files=['纪要.md'], options={'length': '一句话', 'out_format': 'Word'})
    assert s.task(tid)['status'] == 'completed' and '18650' in s.task(tid)['answer'] and [i for i in f.listing() if i['path'].startswith('摘要-')]
    assert '40 字以内' in p.prompts[-1][0]['content']
    s, f, tid, p = forced(tmp_path, '把这句翻译一下：会议改期', 'chat', [Reply(content='好的呀')])
    assert skill_of(s, tid) == 'chat' and s.task(tid)['answer'] == '好的呀'


def test_tag_chat_endpoint_seeds_forced_intent(tmp_path):
    from aiohttp.test_utils import TestClient, TestServer
    from lulu.server import create_app
    async def scenario():
        (tmp_path/'static').mkdir(); (tmp_path/'static/index.html').write_text('__TOKEN__')
        app = create_app(tmp_path, port=18777, provider=Scripted([translation('Hello')]))
        async with TestClient(TestServer(app, host='127.0.0.1', port=18777)) as client:
            h = {'X-Lulu-Token': app['token']}
            state = await (await client.get('/api/state', headers=h)).json()
            assert [x['key'] for x in state['skills']][:3] == ['translate', 'summarize', 'rewrite'] and 'tone' in state['skill_options']
            sid = (await (await client.post('/api/sessions', json={}, headers=h)).json())['id']
            r = await client.post('/api/chat', json={'text': '你好', 'session': sid, 'skill': 'translate', 'files': ['不存在.md'], 'options': {'lang': '英文', 'bogus': 1}}, headers=h)
            tid = (await r.json())['task']
            for _ in range(50):
                await asyncio.sleep(0.05)
                if app['store'].task(tid)['status'] not in ('queued', 'running'): break
            task = app['store'].task(tid)
            assert task['status'] == 'completed' and task['answer'] == 'Hello'
            intent = json.loads(task['intent'])
            assert intent['forced']['skill'] == 'translate' and intent['forced']['files'] == [] and intent['forced']['options'] == {'lang': '英文'}
            r = await client.post('/api/chat', json={'text': 'x', 'session': sid, 'skill': 'magic'}, headers=h)
            assert r.status == 400
    asyncio.run(scenario())


def rewritten(text):
    return Reply(content=json.dumps({'text': text}, ensure_ascii=False))


def test_rewrite_tone_and_number_check(tmp_path):
    s, f, tid, p = forced(tmp_path, '那个，我们这边呢，大概就是想说预算 18650 这个事情可能要再讨论讨论。', 'rewrite',
                          [rewritten('关于 18650 的预算，我们建议再讨论一次。')], options={'tone': '更正式'})
    assert skill_of(s, tid) == 'rewrite' and s.task(tid)['status'] == 'completed' and s.task(tid)['answer'].startswith('关于 18650')
    assert '正式' in p.prompts[-1][0]['content'] and json.loads(p.prompts[-1][-1]['content'])['原文'].startswith('那个')
    s, f, tid, p = run(tmp_path, '帮我把这段改得正式一点：我们那个预算 18650 得再聊聊。', [rewritten('预算 99999 需再议。'), rewritten('关于 18650 的预算需再议。')])
    assert skill_of(s, tid) == 'rewrite' and '18650' in s.task(tid)['answer'] and '99999' not in s.task(tid)['answer']
    assert any(e['kind'] == 'rewrite_retry' for e in s.rows('SELECT kind FROM events WHERE task=?', (tid,)))


def test_ask_file_answers_only_from_the_file(tmp_path):
    f = Files(tmp_path/'files'); f.write('合同.md', '甲方：青松公司。付款期限：签约后 30 天内付清。违约金：合同总额的 5%。')
    good = Reply(content=json.dumps({'answer': '签约后 30 天内付清。', 'quote': '付款期限：签约后 30 天内付清', 'found': True}, ensure_ascii=False))
    s, f, tid, p = forced(tmp_path, '付款期限是多久？', 'ask_file', [good], files=['合同.md'])
    assert skill_of(s, tid) == 'ask_file' and '30 天' in s.task(tid)['answer'] and '原文' in s.task(tid)['answer']
    made_up = Reply(content=json.dumps({'answer': '违约金是 15%。', 'quote': '违约金：合同总额的 15%', 'found': True}, ensure_ascii=False))
    s, f, tid, p = forced(tmp_path, '违约金多少？', 'ask_file', [made_up], files=['合同.md'], store=s)
    assert '对照原文' in s.task(tid)['answer']
    missing = Reply(content=json.dumps({'answer': '文件里没有提到', 'quote': '', 'found': False}, ensure_ascii=False))
    s, f, tid, p = forced(tmp_path, '乙方是谁？', 'ask_file', [missing], files=['合同.md'], store=s)
    assert '没有提到' in s.task(tid)['answer']
    s, f, tid, p = run(tmp_path, '合同.md 里付款期限是多少', [good])
    assert skill_of(s, tid) == 'ask_file'


def test_extract_to_table_keeps_only_values_in_the_text(tmp_path):
    f = Files(tmp_path/'files'); f.write('名单.md', '陆遥 13800000001 预算 18650\n周文 13900000002 预算 9200')
    rows = Reply(content=json.dumps({'rows': [{'姓名': '陆遥', '电话': '13800000001', '金额': '18650'}, {'姓名': '周文', '电话': '13900000002', '金额': '77777'}]}, ensure_ascii=False))
    s, f, tid, p = forced(tmp_path, '', 'extract', [rows], files=['名单.md'], options={'columns': ['姓名', '电话', '金额'], 'out_format': 'Excel'})
    assert skill_of(s, tid) == 'extract' and s.task(tid)['status'] == 'completed'
    made = [i['path'] for i in f.listing() if i['path'].startswith('提取-')]
    assert made and made[0].endswith('.xlsx') and '2 条' in s.task(tid)['answer'] and '1 个格子' in s.task(tid)['answer']
    table = f.read(made[0])
    assert '13800000001' in table and '77777' not in table
    s2, f2, tid2, p2 = run(tmp_path, '把 名单.md 里的姓名、电话提取成表', [Reply(content=json.dumps({'rows': [{'姓名': '陆遥', '电话': '13800000001'}]}, ensure_ascii=False))])
    assert skill_of(s2, tid2) == 'extract' and '陆遥 | 13800000001' in s2.task(tid2)['answer']


def test_translate_previous_answer_reference(tmp_path):
    s = Store(tmp_path/'db'); f = Files(tmp_path/'files'); sid = s.session()
    tid = s.create_task(sid, '你好'); asyncio.run(Agent(s, f, Scripted([Reply(content='会议改到周五，预算 18650。')])).run(tid))
    tid2 = s.create_task(sid, '翻译一下上面这段')
    p = Scripted([translation('The meeting moves to Friday; budget 18650.')])
    asyncio.run(Agent(s, f, p).run(tid2))
    assert s.task(tid2)['status'] == 'completed' and json.loads(p.prompts[-1][-1]['content'])['原文'] == '会议改到周五，预算 18650。'


# ------------------------------------------------ 2026-09-08 真机测试报告（GPT）P02 / P03 / P04
def test_generate_direct_display_writes_no_file(tmp_path):
    """按要点写 with 结果=直接显示 (the tag row sends no out_format): the text goes into the chat, no Word file."""
    points = '要点：收件人为测试团队；周五下午三点在虚拟会议室A开会；讨论桌宠测试结果；请提前确认能否参加。落款测试员甲。'
    body = '测试团队：\n\n本周五下午三点在虚拟会议室A开会，讨论桌宠测试结果，请提前确认能否参加。\n\n测试员甲'
    s, f, tid, p = forced(tmp_path, points, 'generate', [draft(body)], options={'doc_kind': '邮件'})
    assert s.task(tid)['status'] == 'completed' and s.task(tid)['answer'].startswith('测试团队') and '保存在' not in s.task(tid)['answer']
    assert not [i for i in f.listing() if i['path'].endswith('.docx')]
    s, f, tid, p = forced(tmp_path, points, 'generate', [draft(body)], options={'doc_kind': '邮件', 'out_format': 'Word'}, store=s)
    assert '保存在 邮件.docx' in s.task(tid)['answer'] and f.read('邮件.docx').startswith('测试团队')


PURCHASE = [['物品', '数量', '单价（元）', '金额（元）', '交付状态'], ['笔记本', 10, 12.5, 125, '已交付'], ['笔', 5, 3.2, 16, '已交付'],
            ['文件夹', 2, 8, 16, '尚未交付'], ['合计', 17, None, 157, None], ['人工测试数据', None, None, None, None]]


def test_table_analysis_skips_total_rows_and_keeps_the_cells(tmp_path):
    f = Files(tmp_path/'files'); f.write('采购记录.xlsx', rows=PURCHASE)
    stats = f.analyze('采购记录.xlsx')
    assert stats['columns']['2:数量']['sum'] == 17 and stats['columns']['4:金额（元）']['sum'] == 157   # 34 / 314 before: the 合计 line was counted again
    assert stats['excluded_rows'] and stats['excluded_rows'][0].startswith('合计')
    assert '尚未交付' in stats['text'] and stats['text'].startswith('物品\t数量')


def test_ask_file_on_excel_reads_the_rows_not_only_the_sums(tmp_path):
    f = Files(tmp_path/'files'); f.write('采购记录.xlsx', rows=PURCHASE)
    good = Reply(content=json.dumps({'answer': '合计 17 件、157 元；文件夹尚未交付。', 'quote': '文件夹\t2\t8\t16\t尚未交付', 'found': True}, ensure_ascii=False))
    s, f, tid, p = forced(tmp_path, '合计数量和金额是多少？哪种物品尚未交付？', 'ask_file', [good], files=['采购记录.xlsx'])
    assert s.task(tid)['status'] == 'completed' and '尚未交付' in s.task(tid)['answer']
    shown = json.loads(p.prompts[-1][-1]['content'])['文件内容']
    assert '文件夹\t2\t8\t16\t尚未交付' in shown and '总和 157' in shown and '不含合计行' in shown and 'numeric_count' not in shown


def test_extract_from_selected_excel_does_not_ask_for_a_file(tmp_path):
    f = Files(tmp_path/'files'); f.write('采购记录.xlsx', rows=PURCHASE)
    rows = Reply(content=json.dumps({'rows': [{'物品': '笔记本', '数量': '10', '交付状态': '已交付'}, {'物品': '文件夹', '数量': '2', '交付状态': '尚未交付'}]}, ensure_ascii=False))
    s, f, tid, p = forced(tmp_path, '提取三种物品，排除合计和说明行', 'extract', [rows], files=['采购记录.xlsx'], options={'columns': ['物品', '数量', '交付状态']})
    assert s.task(tid)['status'] == 'completed', s.task(tid)['answer']
    assert '尚未交付' in s.task(tid)['answer'] and '尚未交付' in json.loads(p.prompts[-1][-1]['content'])['原文']
