import json
import pytest
from lulu.writer import NeedsInput, document_content, expected_plaintext, usable_current_source
from lulu.intent import realtime_request as needs_current_evidence
from lulu.files import Files
from lulu.store import Store

@pytest.mark.parametrize('text',[
 '为了生成一份报告，我需要获取实时数据。请提供平台信息。',
 '由于无法直接访问互联网获取最新数据，请您提供以下信息。',
 '{"status":"needs_input","question":"请选择交易平台","reason":"平台不明确"}',
 '待确认：平台、实时价格与时间范围。'])
def test_questions_not_saved_as_body(text):
 with pytest.raises(NeedsInput):document_content(text,'生成今日BTC价格报告')

def test_legitimate_questionnaire_and_ready():
 assert '请提供' in document_content('请提供您的年龄信息。','生成调查问卷')
 assert document_content('{"status":"ready","content":"学习计划正文"}','写学习计划')=='学习计划正文'
 assert needs_current_evidence('今日BTC价格。用户答复：不要模板，要真实数据')
 assert not needs_current_evidence('今日BTC价格。用户答复：先给我一个模板')

def test_docx_heading_receipt(tmp_path):
 f=Files(tmp_path);text='# 报告标题\n\n正文\n';f.write('报告.docx',text)
 assert f.read('报告.docx').strip()==expected_plaintext(text,'.docx')

def test_question_survives_restart_and_reply_once(tmp_path):
 s=Store(tmp_path/'db');tid=s.create_task(s.session(),'生成今日BTC价格文档')
 q=s.ask(tid,'提供真实资料，或改为模板','缺少数据',options=['模板','数据'],phase='gathering');s.update_task(tid,status='awaiting_input',phase='gathering');s.db.close()
 s=Store(tmp_path/'db');pending=s.rows("SELECT * FROM questions WHERE status='pending'");assert pending and json.loads(pending[0]['options'])==['模板','数据']
 follow,new=s.answer_question(q['id'],'不要模板，要真实数据')
 assert new and follow==tid
 assert s.answer_question(q['id'],'重复点击')==(tid,False)
 assert len(s.rows('SELECT * FROM tasks'))==1
 assert s.task(tid)['status']=='queued' and s.task(tid)['phase']=='gathering'
 assert json.loads(s.task(tid)['answers'])[0]['answer']=='不要模板，要真实数据'

def test_template_does_not_allow_model_refusal():
 with pytest.raises(NeedsInput):document_content('由于无法访问互联网，我不能获取真实数据，请提供资料。','生成报告模板')

def test_search_snippet_is_not_current_data():
 assert not usable_current_source({'action':'web','content':'2026-09-07 price:12345'},'2026-09-07')
 assert not usable_current_source({'action':'url','content':'Binance历史数据下载，登录后查看'},'2026-09-07')
 assert usable_current_source({'action':'url','content':'2026-09-07 收盘: 12345'},'2026-09-07')
