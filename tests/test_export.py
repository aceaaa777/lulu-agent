import asyncio
import json

from lulu.loop import Agent
from lulu.export import split_export
from lulu.files import Files
from lulu.store import Store


def test_inline_and_followup_across_restart(tmp_path):
    s=Store(tmp_path/'db');f=Files(tmp_path/'files');sid=s.session()
    body='我们先讨论agent的实现形式。\n长期记忆一定要有，支持低配Windows。'
    tid=s.create_task(sid,body+'\n\n把上面的话写成pdf')
    asyncio.run(Agent(s,f).run(tid))
    assert s.task(tid)['status']=='completed'
    path=next(f.root.glob('*.pdf'))
    assert '长期记忆一定要有' in f.read(path.name)
    s.db.close();s=Store(tmp_path/'db')
    follow=s.create_task(sid,'上面那段话写成word')
    asyncio.run(Agent(s,f).run(follow))
    doc=next(f.root.glob('*.docx'))
    assert f.read(doc.name)==body
    assert '报错' not in f.read(doc.name)
    assert s.rows("SELECT * FROM events WHERE kind='thinking'")==[]


def test_previous_failed_export_still_resolves_original(tmp_path):
    s=Store(tmp_path/'db');sid=s.session()
    first=s.create_task(sid,'正文包含中文\n\n把上面的话写成pdf')
    s.update_task(first,status='paused',answer='本轮尚未完成：文件生成。')
    second=s.create_task(sid,'上面那段话写成word')
    f=Files(tmp_path/'files')
    asyncio.run(Agent(s,f).run(second))
    assert f.read(next(f.root.glob('*.docx')).name)=='正文包含中文'


def test_draft_and_empty_context_and_negation(tmp_path):
    s=Store(tmp_path/'db');sid=s.session();f=Files(tmp_path/'files')
    tid=s.create_task(sid,'把上面的内容导出为PDF')
    asyncio.run(Agent(s,f).run(tid))
    assert s.task(tid)['status']=='awaiting_input'
    assert '粘贴' in s.task(tid)['answer']
    prior=s.create_task(sid,'写一段介绍')
    s.update_task(prior,status='completed',answer='这是已经写好的介绍。')
    tid=s.create_task(sid,'把上面的回答写成Word')
    asyncio.run(Agent(s,f).run(tid))
    assert f.read(next(f.root.glob('*.docx')).name)=='这是已经写好的介绍。'
    assert split_export('不要把上面的话写成pdf') is None
