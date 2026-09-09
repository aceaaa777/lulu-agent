import json
import asyncio
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer
from lulu.server import create_app


def test_local_api_memory_and_boundary(tmp_path):
    async def scenario():
        (tmp_path/'static').mkdir()
        (tmp_path/'static'/'index.html').write_text('__TOKEN__')
        app=create_app(tmp_path,port=18769)
        async with TestClient(TestServer(app,host='127.0.0.1',port=18769)) as client:
            r=await client.get('/api/state')
            assert r.status==403
            headers={'X-Lulu-Token':app['token']}
            r=await client.post('/api/sessions',json={},headers=headers)
            assert r.status==200
            r=await client.post('/api/memory',json={'key':'语言','value':'中文'},headers=headers)
            assert (await r.json())['saved']
            r=await client.get('/api/memory/export',headers=headers)
            assert (await r.json())['memories'][0]['value']=='中文'
            r=await client.get('/api/download?path=../config.json',headers=headers)
            assert r.status==400
            r=await client.post('/api/memory',json={'key':'x','value':'y'},headers={**headers,'Origin':'https://evil.example'})
            assert r.status==403
            r=await client.get('/api/state',headers={**headers,'Host':'evil.example:18769'})
            assert r.status==403
            r=await client.delete('/api/memory',json={'key':'语言'},headers=headers)
            assert 'deleted' in (await r.json())
    asyncio.run(scenario())

def test_desktop_import_reminder_and_health(tmp_path):
    import base64,time
    async def scenario():
        (tmp_path/'static').mkdir();(tmp_path/'static/index.html').write_text('__TOKEN__')
        app=create_app(tmp_path,port=18771)
        async with TestClient(TestServer(app,host='127.0.0.1',port=18771)) as client:
            h={'X-Lulu-Token':app['token']}
            assert (await client.get('/api/health')).status==403
            assert (await (await client.get('/api/health',headers=h)).json())['ok']
            r=await client.post('/api/import',headers=h,json={'name':'中文文件.txt','content':base64.b64encode('正文'.encode()).decode()})
            assert r.status==200
            r=await client.post('/api/import',headers=h,json={'name':'../外部.txt','content':'YWJj'})
            assert r.status==400
            r=await client.post('/api/reminders',headers=h,json={'action':'add','text':'核对结果','due':time.time()+.05})
            assert r.status==200
            await asyncio.sleep(.1)
            data=await (await client.get('/api/desktop',headers=h)).json()
            assert len(data['reminders'])==1 and data['reminders'][0]['due']<data['now']
            rid=data['reminders'][0]['id']
            assert (await client.post('/api/reminders',headers=h,json={'action':'ack','id':rid})).status==200
            assert not (await (await client.get('/api/desktop',headers=h)).json())['reminders']
    asyncio.run(scenario())

def test_completed_task_accepts_next_submission_immediately(tmp_path):
    from conftest import Scripted, Reply
    class Fast(Scripted):
        async def chat(self,messages,tools=None,*,schema=None,**kwargs):
            if schema: return await super().chat(messages,tools,schema=schema,**kwargs)
            self.calls.append({'scripted':True})
            return Reply(content='你好，我是 Lulu。')
    async def scenario():
        (tmp_path/'static').mkdir();(tmp_path/'static/index.html').write_text('__TOKEN__')
        app=create_app(tmp_path,port=18772,provider=Fast())
        async with TestClient(TestServer(app,host='127.0.0.1',port=18772)) as client:
            h={'X-Lulu-Token':app['token']}
            sid=(await (await client.post('/api/sessions',headers=h,json={})).json())['id']
            for _ in range(3):
                r=await client.post('/api/chat',headers=h,json={'session':sid,'text':'你好'})
                assert r.status==200
                tid=(await r.json())['task']
                for attempt in range(150):
                    task=(await (await client.get('/api/tasks/'+tid,headers=h)).json())['task']
                    if task['status'] not in ('queued','running'): break
                    await asyncio.sleep(.02)
                assert task['status']=='completed'
    asyncio.run(scenario())


def test_backend_endpoints_switch_think_secret_and_probe(tmp_path,monkeypatch):
    monkeypatch.setenv('LULU_OLLAMA_BASE','http://127.0.0.1:1')
    async def scenario():
        (tmp_path/'static').mkdir();(tmp_path/'static/index.html').write_text('__TOKEN__')
        app=create_app(tmp_path,port=18773)
        async with TestClient(TestServer(app,host='127.0.0.1',port=18773)) as client:
            h={'X-Lulu-Token':app['token']}
            info=await (await client.get('/api/backend',headers=h)).json()
            assert info['backend']=='ollama' and info['think'] is False and not info['leaves_device'] and 'tiers' in info['options'] and info['connected'] is False
            assert (tmp_path/'config.json').exists()
            # think is a light switch: allowed any time, persisted, reflected on the desktop poll
            info=await (await client.post('/api/backend',headers=h,json={'think':True})).json()
            assert info['think'] is True and app['agent'].think is True and app['agent'].writer.think is True
            assert json.loads((tmp_path/'config.json').read_text(encoding='utf-8'))['think'] is True
            desk=await (await client.get('/api/desktop',headers=h)).json()
            assert desk['backend']['think'] is True and desk['backend']['label']=='本地模型'
            # a key never lands in config.json; switching to the API backend rebuilds the provider with it
            r=await (await client.post('/api/backend/secret',headers=h,json={'name':'api_key','value':'sk-secret-123456'})).json()
            assert r['saved'] and 'secret' not in json.dumps(r) and 'sk-secret' not in (tmp_path/'config.json').read_text(encoding='utf-8')
            info=await (await client.post('/api/backend',headers=h,json={'backend':'api','api':{'preset':'deepseek'}})).json()
            assert info['backend']=='api' and info['leaves_device'] and info['model']=='deepseek-chat' and app['agent'].provider.api_key=='sk-secret-123456'
            assert '发到' in info['note']
            r=await client.post('/api/backend',headers=h,json={'backend':'nope'})
            assert r.status==400
            report=await (await client.post('/api/backend/probe',headers=h)).json()
            assert set(report['backends'])=={'ollama','api','claude_cli','cli'} and '（当前）' in report['summary']
            # back to local, explicit 4b tier
            info=await (await client.post('/api/backend',headers=h,json={'backend':'ollama','tier':'4b'})).json()
            assert info['tier']=='4b' and info['thinking_model'].startswith('qwen3:4b-thinking') and not info['leaves_device']
            test=await (await client.post('/api/backend/test',headers=h,json={})).json()
            assert test['ok'] is False and '模型' in test['content']
    asyncio.run(scenario())
