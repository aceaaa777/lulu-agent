"""Generic fallback loop (skills disabled) with a scripted model: artifacts, acceptance, questions, resume, idempotency."""
import asyncio
import json

from conftest import Scripted, run, call, Reply, Agent, Files, Store, online_web


def generic(tmp_path, text, answers, store=None, judge='asking', session=None, facts=None):
    store = store or Store(tmp_path/'db')
    files = Files(tmp_path/'files')
    tid = store.create_task(session or store.session(), text)
    provider = Scripted(answers, judge, facts)
    asyncio.run(Agent(store, files, provider, skills_enabled=False).run(tid))
    return store, files, tid, provider


def test_loop_creates_real_document(tmp_path):
    s, f, tid, p = generic(tmp_path, '保存为学习计划.docx', [call('create_document', path='学习计划.docx', content='学习计划\n周一阅读'), Reply(content='已完成。')])
    assert s.task(tid)['status'] == 'completed'
    assert f.read('学习计划.docx') == '学习计划\n周一阅读'
    assert s.rows("SELECT * FROM events WHERE task=? AND kind='artifact_verified'", (tid,))
    assert s.task(tid)['phase'] == 'completed'
    assert [st['artifact'] for st in s.steps(tid) if st['artifact']] == ['学习计划.docx']


def test_no_artifact_cannot_claim_success(tmp_path):
    s, f, tid, p = generic(tmp_path, '生成文件，保存为结果.docx', [Reply(content='已生成结果.docx。')]*2)
    assert s.task(tid)['status'] == 'paused'
    assert not f.listing()
    assert len(p.calls) == 2


def test_missing_read_can_recover(tmp_path):
    s, f, tid, p = generic(tmp_path, '生成文档，保存为计划.docx', [call('read_document', path='计划.docx'), call('create_document', path='计划.docx', content='真实计划'), Reply(content='已生成。')])
    assert s.task(tid)['status'] == 'completed'
    assert f.read('计划.docx') == '真实计划'


def test_memory_restart_and_delete(tmp_path):
    s, f, tid, p = generic(tmp_path, '记住：我喜欢简洁中文。', [call('save_memory', key='回答风格', value='简洁中文', quote='我喜欢简洁中文'), Reply(content='记住了。')])
    assert s.task(tid)['status'] == 'completed'
    s.db.close(); s = Store(tmp_path/'db')
    s, f, tid, p = generic(tmp_path, '我的偏好是什么？', [Reply(content='简洁中文')], s)
    assert '简洁中文' in json.dumps(p.prompts, ensure_ascii=False)
    assert s.task(tid)['memory_refs'] == '["回答风格"]'
    s.forget('回答风格')
    s, f, tid, p = generic(tmp_path, '我的偏好是什么？', [Reply(content='尚无记忆。')], s)
    assert '简洁中文' not in json.dumps(p.prompts, ensure_ascii=False)


def test_duplicate_create_is_idempotent(tmp_path):
    args = {'path': '文档.docx', 'content': '重复调用只产生一份文档'}
    s, f, tid, p = generic(tmp_path, '保存为文档.docx', [call('create_document', **args), call('create_document', **args), Reply(content='已完成')])
    assert s.task(tid)['status'] == 'completed'
    assert len(s.rows("SELECT * FROM events WHERE task=? AND kind='artifact_verified'", (tid,))) == 1
    assert s.rows("SELECT * FROM events WHERE task=? AND kind='step_reused'", (tid,))


def test_cancellation_releases_lock(tmp_path):
    class Slow(Scripted):
        async def chat(self, messages, tools=None, *, schema=None, **kwargs):
            if schema and schema.get('title') == 'intent':
                return await super().chat(messages, tools, schema=schema, **kwargs)
            self.started.set()
            await asyncio.sleep(2)
            return Reply(content='未调用工具')

    async def scenario():
        s = Store(tmp_path/'db'); f = Files(tmp_path/'files'); p = Slow([]); p.started = asyncio.Event(); a = Agent(s, f, p)
        tid = s.create_task(s.session(), '写一份文件，要点：一、进度；二、风险；三、下周计划。保存为文件.docx')
        job = asyncio.create_task(a.run(tid)); await asyncio.wait_for(p.started.wait(), 10)
        job.cancel()
        try:
            await asyncio.wait_for(job, 10)
        except asyncio.CancelledError:
            pass
        assert not a.lock.locked()
        assert s.task(tid)['status'] == 'cancelled'
    asyncio.run(scenario())


def test_negated_save_does_not_require_artifact(tmp_path):
    s, f, tid, p = generic(tmp_path, '读取文档后口头回答，不要保存文件，也不要保存任何记忆。', [Reply(content='请提供要读取的文档。')])
    assert s.task(tid)['status'] == 'completed'
    assert not f.listing()


def test_all_named_artifacts_required(tmp_path):
    s, f, tid, p = generic(tmp_path, '生成文档保存为甲.docx，另保存为乙.pdf', [call('create_document', path='甲.docx', content='真实内容'), Reply(content='完成'), Reply(content='完成')])
    assert s.task(tid)['status'] == 'paused'
    assert '乙.pdf' in s.task(tid)['answer']


def test_failed_create_recovered_by_conversion(tmp_path):
    f = Files(tmp_path/'files'); f.write('原文.txt', '合同预算15000元')
    s, f, tid, p = generic(tmp_path, '将原文.txt转换文档，保存为合同.docx', [call('create_document', path='合同.docx', content=''), call('convert_document', path='原文.txt', destination='合同.docx'), Reply(content='完成')])
    assert s.task(tid)['status'] == 'completed'
    assert f.read('合同.docx') == '合同预算15000元'


def test_restart_resumes_from_phase_without_redoing_artifacts(tmp_path):
    f = Files(tmp_path/'files')
    s, f, tid, p = generic(tmp_path, '生成文档保存为甲.docx，另保存为乙.pdf', [call('create_document', path='甲.docx', content='甲的内容'), Reply(content='完成'), Reply(content='完成')])
    assert s.task(tid)['status'] == 'paused'
    s.db.close(); s = Store(tmp_path/'db')
    s.update_task(tid, status='queued')
    provider = Scripted([call('create_document', path='甲.docx', content='甲的内容'), call('create_document', path='乙.pdf', content='乙的内容'), Reply(content='完成')])
    asyncio.run(Agent(s, Files(tmp_path/'files'), provider, skills_enabled=False).run(tid))
    assert s.task(tid)['status'] == 'completed'
    assert len(s.rows("SELECT * FROM events WHERE task=? AND kind='artifact_verified'", (tid,))) == 2
    assert s.rows("SELECT * FROM events WHERE task=? AND kind='step_reused'", (tid,))
    assert '已完成步骤' in json.dumps(provider.prompts[0], ensure_ascii=False)


def test_explicit_question_tool(tmp_path):
    s, f, tid, p = generic(tmp_path, '生成项目总结Word', [call('ask_user', question='请提供项目资料', reason='缺少原文')])
    assert s.task(tid)['status'] == 'awaiting_input' and not f.listing()


def test_fixed_workflows_need_no_model(tmp_path):
    f = Files(tmp_path/'files'); f.write('计划.md', '每天阅读30分钟\n每天阅读30分钟'); f.write('数据.csv', rows=[['金额'], [12], [18]])
    s, f, tid, p = run(tmp_path, '把 计划.md 中的“每天阅读30分钟”改成“每天阅读45分钟”，再转换成 计划.docx。', [])
    assert s.task(tid)['status'] == 'completed' and f.read('计划.md').count('45分钟') == 2 and '30分钟' not in f.read('计划.docx')
    assert not p.calls
    s, f, tid, p = run(tmp_path, '分析 数据.csv 的总和与平均值。', [], s)
    assert '总和 30' in s.task(tid)['answer'] and '平均值 15' in s.task(tid)['answer'] and not p.calls


def test_export_conversation_uses_previous_answer(tmp_path):
    s, f, tid, p = run(tmp_path, '写一句关于秋天的话', [Reply(content='秋天的风带着桂花香。')])
    assert s.task(tid)['status'] == 'completed'
    s, f, tid2, p = run(tmp_path, '把上面的话写成pdf', [], s, session=s.task(tid)['session'])
    assert s.task(tid2)['status'] == 'completed'
    exported = [i['path'] for i in f.listing() if i['path'].endswith('.pdf')]
    assert exported and '桂花' in f.read(exported[0])


def test_model_error_is_reported_not_hidden(tmp_path):
    s, f, tid, p = generic(tmp_path, '写一份总结，保存为总结.docx', [Reply(content='本机模型调用失败：连接超时', finish_reason='error')])
    assert s.task(tid)['status'] == 'failed' and '模型' in s.task(tid)['answer']


def test_realtime_question_answer_is_regrounded_generic(tmp_path, monkeypatch):
    pages = [{'url': 'https://example.com/btc', 'title': 'Bitcoin price today', 'text': 'Binance BTC/USDT 65,001.2, OKX 65,010.0. Updated 2026-09-07 10:00.'}]
    facts = [{'claim': '币安 BTC/USDT 价格 65,001.2', 'quote': 'Binance BTC/USDT 65,001.2', 'source': 1}]
    online_web(monkeypatch, pages)
    s, f, tid, p = generic(tmp_path, '现在BTC在币安多少钱？', [Reply(content='币安现在是 71234 USDT。')], facts=facts)
    task = s.task(tid)
    assert task['status'] == 'completed' and '71234' not in task['answer'] and '65,001.2' in task['answer']
    assert any(e['kind'] == 'answer_regrounded' for e in s.rows('SELECT kind FROM events WHERE task=?', (tid,)))
