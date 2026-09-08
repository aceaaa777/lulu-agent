"""Real local 7B acceptance run. Uses an isolated data directory, no mock answers."""
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lulu.loop import Agent
from lulu.models import OllamaProvider
from lulu.store import Store
from lulu.files import Files


async def main():
    root=Path(tempfile.mkdtemp(prefix='lulu-live-'))
    s=Store(root/'memory.db');f=Files(root/'workspace');provider=OllamaProvider()
    results=[]
    async def turn(text,resume=None):
        nonlocal s
        sid=s.session();tid=s.create_task(sid,text);start=time.monotonic()
        await Agent(s,f,provider).run(tid,resume)
        row=s.task(tid)
        result={'prompt':text,'answer':row['answer'],'status':row['status'],'seconds':round(time.monotonic()-start,2),
                'events':s.rows('SELECT kind,detail FROM events WHERE task=?',(tid,))}
        results.append(result)
        Path('live-test-report.json').write_text(json.dumps({'root':str(root),'model':provider.model,'results':results,'calls':provider.calls},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False),flush=True)
        return tid
    await turn('请记住：我的报告必须使用中文，先给结论，再列依据。请保存为长期记忆。')
    assert s.memories(),'模型未保存长期记忆'
    s.db.close();s=Store(root/'memory.db')
    await turn('我以前对报告的语言和结构有什么要求？')
    assert '中文' in results[-1]['answer'] and '结论' in results[-1]['answer'],'跨会话回忆失败'
    tid=await turn('创建 学习计划.md，内容是一个三天阅读计划，并在文件中明确写出“每天阅读30分钟”。实际保存文件。')
    assert (f.root/'学习计划.md').exists(),'没有生成文件'
    assert '每天阅读30分钟' in f.read('学习计划.md'),'未遵守用户要求的原句'
    await turn('把 学习计划.md 中的“每天阅读30分钟”改成“每天阅读45分钟”，再转换成 学习计划.docx。')
    assert '45分钟' in f.read('学习计划.md') and (f.root/'学习计划.docx').exists(),'修改或转换失败'
    f.write('销售.csv',rows=[['月份','金额'],['一月',12],['二月',18]])
    await turn('分析 销售.csv 的金额总和与平均值。请使用工具计算。')
    assert '30' in results[-1]['answer'] and '15' in results[-1]['answer'],'数值分析失败'
    assert any(e['kind']=='tool_done' and json.loads(e['detail']).get('action')=='analyze' for e in results[-1]['events']),'没有实际调用统计工具'
    await turn('读取 学习计划.md，简要总结文件中的阅读安排。')
    assert any(e['kind']=='tool_done' and json.loads(e['detail']).get('action')=='read' for e in results[-1]['events']),'总结没有读取原文件'
    assert '第四天' not in results[-1]['answer'],'总结增加了不存在的日期'
    await turn('10分钟后提醒我休息')
    assert s.rows("SELECT * FROM reminders WHERE status='pending'"),'提醒未保存'
    report={'root':str(root),'model':provider.model,'results':results,'calls':provider.calls}
    Path('live-test-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LIVE PASS',root,flush=True)


if __name__=='__main__': asyncio.run(main())
