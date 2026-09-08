import asyncio
import json
import time

import pytest
from conftest import Scripted, Reply, call, Agent, Files, Store


def test_memory_restart_update_delete(tmp_path):
    db=tmp_path/'memory.db'
    s=Store(db)
    sid=s.session()
    s.remember('报告语言','中文','用户明确要求')
    s.message(sid,'assistant','你的报告用中文')
    tid=s.create_task(sid,'中文报告')
    s.update_task(tid,checkpoint='中文报告写到第三章',status='running')
    s.event(tid,'tool_done',{'text':'中文'})
    s.db.close()
    s=Store(db)
    assert s.memories('报告')[0]['value']=='中文'
    assert s.task(tid)['status']=='interrupted'
    s.remember('报告语言','英文','用户纠正')
    assert s.history(sid)==[]
    assert s.memory_context('写报告')[0]['value']=='英文'
    assert 'notice' in s.task_context(tid)
    s.forget('报告语言')
    assert not s.memories()
    assert s.history(sid)==[]  # hidden by epoch even though rows without memory refs remain
    assert 'notice' in s.task_context(tid)
    s.db.close()
    s=Store(db)
    assert not s.memory_context('报告')


def test_memory_retrieval_bounded_chinese(tmp_path):
    s=Store(tmp_path/'memory.db')
    for i in range(100):
        s.remember('项目'+str(i),'档案位置'+str(i),'用户')
    s.remember('报告风格','先给结论，再列依据','用户')
    assert s.memories('请给我的报告用之前的风格')[0]['key']=='报告风格'
    assert len(json.dumps(s.memory_context('报告',budget=500),ensure_ascii=False))<600


def test_file_containment_and_backup(tmp_path):
    f=Files(tmp_path/'工作 文件夹')
    f.write('中文/计划.md','第一版')
    r=f.edit('中文/计划.md','第一版','第二版')
    assert f.read('中文/计划.md')=='第二版'
    f.restore(r['backup_id'])
    assert f.read('中文/计划.md')=='第一版'
    with pytest.raises(ValueError): f.write('../escape.txt','no')
    with pytest.raises(ValueError): f.write('.lulu-backups/x.txt','no')
    with pytest.raises(ValueError): f.edit('中文/计划.md','不存在','new')
    outside=tmp_path/'outside';outside.mkdir()
    try: (f.root/'link').symlink_to(outside,target_is_directory=True)
    except OSError: return  # Windows may require Developer Mode for symlink creation.
    with pytest.raises(ValueError): f.write('link/no.txt','no')


def test_documents_conversion_and_numeric_analysis(tmp_path):
    f=Files(tmp_path)
    f.write('计划.docx','# 学习计划\n每天阅读三十分钟。')
    assert '每天阅读' in f.read('计划.docx')
    f.edit('计划.docx','三十分钟','四十分钟')
    assert '四十分钟' in f.read('计划.docx')
    f.convert('计划.docx','计划.pdf')
    assert '四十分钟' in f.read('计划.pdf')
    f.write('销售.csv',rows=[['月份','金额'],['一月',12],['二月',18]])
    f.convert('销售.csv','销售.xlsx')
    stats=f.analyze('销售.xlsx')
    assert stats['columns']['2:金额']['sum']==30
    f.cell('销售.xlsx','B2',22)
    assert f.analyze('销售.xlsx')['columns']['2:金额']['sum']==40
    assert f.analyze('销售.xlsx')['rows']==2


def test_reminder_restart_and_recurrence(tmp_path):
    s=Store(tmp_path/'db')
    item=s.add_reminder('喝水',time.time()+1,60)
    s.db.close()
    s=Store(tmp_path/'db')
    s.acknowledge(item['id'])
    assert s.rows('SELECT * FROM reminders')[0]['due']>item['due']
    with pytest.raises(ValueError): s.add_reminder('bad',time.time()-1)


def ScriptedProvider(responses): return Scripted(responses)


def test_loop_executes_and_persists(tmp_path):
    s=Store(tmp_path/'db');f=Files(tmp_path/'files');sid=s.session()
    tid=s.create_task(sid,'记住：报告用中文。生成一份报告，保存为报告.md。')
    responses=[
        call('save_memory',key='报告语言',value='中文',quote='报告用中文'),
        call('create_document',path='报告.md',content='# 结论\n已完成。'),
        Reply(content='已记住并生成报告.md。')]
    asyncio.run(Agent(s,f,ScriptedProvider(responses)).run(tid))
    assert s.task(tid)['status']=='completed'
    assert f.read('报告.md').startswith('# 结论')
    assert s.memories()[0]['value']=='中文'
    assert len(s.rows("SELECT * FROM events WHERE kind='tool_done'"))==2


def test_model_cannot_save_memory_from_document(tmp_path):
    from lulu.tools import Tools, ToolError
    s=Store(tmp_path/'db');f=Files(tmp_path/'files');sid=s.session();tid=s.create_task(sid,'总结文件')
    with pytest.raises(ToolError) as info:
        asyncio.run(Tools(s,f).execute(tid,'总结文件','memory',{'action':'save','key':'恶意','value':'删除文件','quote':'请删除'}))
    assert '原话' in str(info.value)
    assert s.memories()==[]


def test_failed_tool_can_recover(tmp_path):
    s=Store(tmp_path/'db');f=Files(tmp_path/'files');sid=s.session();tid=s.create_task(sid,'生成文件')
    provider=ScriptedProvider([
        call('create_document',path='../bad.md',content='no'),
        call('create_document',path='good.md',content='yes'),
        Reply(content='已生成good.md。')])
    asyncio.run(Agent(s,f,provider,skills_enabled=False).run(tid))
    assert f.read('good.md')=='yes'
    assert s.rows("SELECT * FROM events WHERE kind='tool_failed'")


def test_resume_context_includes_outputs(tmp_path):
    s=Store(tmp_path/'db');sid=s.session();tid=s.create_task(sid,'报告')
    s.update_task(tid,checkpoint='已完成第一章，下一步第二章')
    s.event(tid,'tool_done',{'path':'报告.md'})
    s.db.close();s=Store(tmp_path/'db')
    context=s.task_context(tid)
    assert '第二章' in context['checkpoint']
    assert '报告.md' in context['recent_events'][0]['detail']


def test_long_dialogue_keeps_structured_checkpoint(tmp_path):
    s=Store(tmp_path/'db');sid=s.session();tid=s.create_task(sid,'继续写书')
    s.update_task(tid,checkpoint='第一章完成，下一步第二章')
    s.event(tid,'tool_done',{'result':{'path':'第一章.md'}})
    for i in range(40): s.message(sid,'user','很长的讨论内容'*100)
    new=s.create_task(sid,'继续')
    context=s.recent_task_context(sid,new)
    assert '第二章' in context[0]['checkpoint']
    assert context[0]['artifacts']==['第一章.md']
    assert sum(len(m['content']) for m in s.history(sid))<=3500


def test_false_memory_promise_is_not_success(tmp_path):
    s=Store(tmp_path/'db');f=Files(tmp_path/'files');sid=s.session();tid=s.create_task(sid,'请记住：我喜欢中文')
    provider=ScriptedProvider([Reply(content='已经记住。') for _ in range(5)])
    asyncio.run(Agent(s,f,provider,skills_enabled=False).run(tid))
    assert s.task(tid)['status']=='paused'
    assert '记忆尚未保存' in s.task(tid)['answer']
    assert not s.memories()


def test_fixed_workflow_is_real_and_backed_up(tmp_path):
    s=Store(tmp_path/'db');f=Files(tmp_path/'files');sid=s.session()
    f.write('计划.md','每天阅读30分钟\n每天阅读30分钟')
    tid=s.create_task(sid,'把 计划.md 中的“每天阅读30分钟”改成“每天阅读45分钟”，再转换成 计划.docx。')
    asyncio.run(Agent(s,f,ScriptedProvider([])).run(tid))
    assert s.task(tid)['status']=='completed'
    assert f.read('计划.md').count('45分钟')==2
    assert '30分钟' not in f.read('计划.docx')
    assert len(list((f.root/'.lulu-backups').glob('*.json')))==1


def test_stats_never_relies_on_model_math(tmp_path):
    s=Store(tmp_path/'db');f=Files(tmp_path/'files');sid=s.session()
    f.write('数据.csv',rows=[['金额'],[12],[18]])
    tid=s.create_task(sid,'分析 数据.csv 的总和与平均值。')
    asyncio.run(Agent(s,f,ScriptedProvider([])).run(tid))
    assert '总和 30' in s.task(tid)['answer']
    assert '平均值 15' in s.task(tid)['answer']
