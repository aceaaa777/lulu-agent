"""Authenticated loopback API shared by the desktop window and transparent pet."""
import asyncio
import json
import secrets
import time
from pathlib import Path

from aiohttp import web

from . import budget as budgeting
from . import backends
from . import searchapi
from .agent import Agent
from .files import Files
from .store import Store
from .companion import Companion

VERSION='0.6-preview'


def create_app(home, port=8766, provider=None, assets=None):
    home=Path(home).resolve()
    assets=Path(assets or home)
    store=Store(home/'data'/'lulu.sqlite3')
    files=Files(home/'workspace')
    config=backends.load_config(home)
    keys=backends.load_secrets(home)
    if not (home/'config.json').exists():
        backends.save_config(home,config)   # first start: write the defaults so the user can see and edit them
    provider=provider or backends.build_provider(config,keys,workdir=str(home/'data'))
    budget_path=home/'data'/'budget.json'
    budget=budgeting.load(budget_path,provider.model)
    provider.num_thread=budget.num_thread
    provider.context=budget.context
    agent=Agent(store,files,provider,budget,engines=config.get('search_engines'),searcher=searchapi.choose(config,keys),think=bool(config.get('think')))
    import os
    os.environ.setdefault('LULU_SEARCH_DEBUG_DIR',str(home/'data'/'search-debug'))
    token=secrets.token_urlsafe(32)
    jobs={}
    companion=Companion(store)
    runtime={'config':config,'keys':keys,'installed':None,'probe':None}

    @web.middleware
    async def guard(request,handler):
        if request.host not in (f'127.0.0.1:{port}',f'localhost:{port}'):
            raise web.HTTPForbidden(text='Invalid host')
        if request.path.startswith('/api/') and request.headers.get('X-Lulu-Token')!=token:
            raise web.HTTPForbidden(text='Invalid local token')
        if request.method not in ('GET','HEAD'):
            origin=request.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
                raise web.HTTPForbidden(text='Invalid origin')
        try:
            response=await handler(request)
        except (ValueError,KeyError,TypeError,FileNotFoundError) as exc:
            response=web.json_response({'error':str(exc)},status=400)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Cache-Control']='no-store'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        return response

    app=web.Application(middlewares=[guard],client_max_size=29*1024*1024)
    app['store'],app['agent'],app['files'],app['token']=store,agent,files,token

    async def index(request):
        # The browser panel was retired in 0.7; the Godot work window is the only UI.
        return web.Response(text='Lulu 后端在运行。请使用桌面版的工作窗口。',content_type='text/plain',charset='utf-8')

    async def model_state():
        provider=agent.provider
        state={'connected':False,'model':provider.get_default_model(),'provider':provider.kind,'backend':provider.kind if provider.kind=='fake' else runtime['config'].get('backend','ollama'),
               'label':provider.label,'think':agent.think,'leaves_device':provider.leaves_device}
        names=await provider.models()
        if names is not None:
            wanted=[provider.model]+([provider.thinking_model] if provider.thinking_model and provider.thinking_model!=provider.model else [])
            installed=(all(m in names or m+':latest' in names for m in wanted) if provider.kind=='ollama' else True)
            state.update(connected=True,installed=installed,models=names[:40])
            runtime['installed']=installed
        return state

    async def state(request):
        from . import skills as skill_table
        return web.json_response({'engine':'lulu-loop','version':VERSION,'model':await model_state(),'budget':agent.budget.to_json(),'workspace':str(files.root),
            'skills':[{'key':k,'label':skill_table.LABELS[k]} for k in skill_table.SKILLS],'skill_options':skill_table.OPTIONS,
            'sessions':store.rows('SELECT * FROM sessions ORDER BY created DESC LIMIT 100'),
            'tasks':store.rows('SELECT id,session,goal,status,updated FROM tasks ORDER BY updated DESC LIMIT 60'),
            'memories':store.memories(limit=500),'memory_candidates':store.memory_candidates(),
            'reminders':store.rows("SELECT * FROM reminders WHERE status='pending' ORDER BY due"),
            'files':files.listing(),'now':time.time()})

    async def health(request):
        return web.json_response({'ok':True,'version':VERSION,'engine':'lulu-loop','pid':__import__('os').getpid()})

    async def budget_view(request):
        return web.json_response(agent.budget.to_json())

    async def budget_measure(request):
        require_idle()
        measured,error=await budgeting.measure(agent.provider,budget_path)
        if error: return web.json_response({'error':error},status=400)
        agent.budget=measured;agent.writer.budget=measured;agent.provider.num_thread=measured.num_thread
        return web.json_response(measured.to_json())

    # ------------------------------------------------------------ model backend
    def backend_view():
        info=backends.describe(runtime['config'],agent.provider,agent.budget,runtime['keys'],runtime['installed'])
        info['search']=searchapi.status(runtime['config'],runtime['keys'])
        info['options']={'backends':backends.BACKENDS,'tiers':backends.TIERS,'api_presets':backends.API_PRESETS,'search_providers':searchapi.PROVIDERS}
        info['busy']=any(not job.done() for job in jobs.values())
        return info

    async def backend_get(request):
        state=await model_state()
        info=backend_view();info['connected']=state['connected'];info['installed']=state.get('installed')
        return web.json_response(info)

    def rebuild(config):
        """Apply a config between tasks: new provider, budget for that model, search provider, think switch."""
        provider=backends.build_provider(config,runtime['keys'],workdir=str(home/'data'))
        budget=budgeting.load(budget_path,provider.model)
        provider.num_thread=budget.num_thread;provider.context=budget.context
        agent.set_provider(provider,budget)
        agent.searcher=searchapi.choose(config,runtime['keys'])
        agent.set_think(bool(config.get('think')))
        runtime['config']=config;runtime['installed']=None

    async def backend_set(request):
        data=await request.json()
        only_think=set(data)=={'think'}
        if not only_think: require_idle()
        config=backends.apply_update(runtime['config'],data)
        backends.save_config(home,config)
        if only_think:
            runtime['config']=config;agent.set_think(bool(config.get('think')))
        else:
            rebuild(config)
        state=await model_state()
        info=backend_view();info['connected']=state['connected'];info['installed']=state.get('installed')
        return web.json_response(info)

    async def backend_secret(request):
        data=await request.json()
        result=backends.set_secret(home,str(data.get('name','')),str(data.get('value','')))
        runtime['keys']=backends.load_secrets(home)
        if not any(not job.done() for job in jobs.values()):
            rebuild(runtime['config'])
        return web.json_response({**result,'keys':backends.masked(runtime['keys'])})

    async def backend_probe(request):
        report=await backends.probe(runtime['config'],runtime['keys'],workdir=str(home/'data'))
        report['summary']=backends.summarize_probe(report)
        runtime['probe']=report
        return web.json_response(report)

    async def backend_test(request):
        """One tiny real call through the current backend so the user sees it answer (and how fast)."""
        require_idle()
        data=await request.json() if request.can_read_body else {}
        think=bool(data.get('think',False))
        start=time.time()
        reply=await agent.provider.chat([{'role':'user','content':'请用一句话介绍你自己，中文。'}],max_tokens=80,temperature=0,timeout=240,think=think)
        return web.json_response({'ok':not reply.failed,'content':reply.content[:400],'thinking_chars':len(reply.thinking or ''),'seconds':round(time.time()-start,1),
                                  'model':(reply.usage or {}).get('model',agent.provider.model_for(think)),'usage':reply.usage})

    async def desktop(request):
        tasks=store.rows('SELECT id,session,goal,status,answer,updated FROM tasks ORDER BY updated DESC LIMIT 60')
        for task in tasks:
            if task['status'] in ('queued','running'):
                events=store.rows("SELECT kind FROM events WHERE task=? AND kind IN ('tool_started','tool_done','tool_failed','thinking','drafting','draft_result') ORDER BY id DESC LIMIT 1",(task['id'],))
                task['animation']='working' if events and events[0]['kind']=='tool_started' else 'thinking'
        provider=agent.provider
        backend={'backend':runtime['config'].get('backend','ollama'),'label':provider.label,'model':provider.model_for(agent.think) if agent.think else provider.model,
                 'think':agent.think,'leaves_device':provider.leaves_device,'last_error':provider.last_error,'installed':runtime['installed']}
        newest=store.rows("SELECT artifact FROM task_steps WHERE artifact IS NOT NULL AND status='done' ORDER BY id DESC LIMIT 1")
        last_artifact=newest[0]['artifact'] if newest and files.path(newest[0]['artifact']).exists() else ''
        return web.json_response({'tasks':tasks,'questions':store.rows("SELECT q.* FROM questions q JOIN tasks t ON t.id=q.task WHERE q.status='pending' AND t.status NOT IN ('queued','running') ORDER BY q.created"),'reminders':store.rows("SELECT * FROM reminders WHERE status='pending' ORDER BY due"),'now':time.time(),'backend':backend,'last_artifact':last_artifact})

    async def companion_state(request): return web.json_response(companion.snapshot())
    async def care_dismiss(request):
        data=await request.json();companion.care.dismiss(int(data['id']));return web.json_response({'ok':True})
    async def weather_search(request):
        data=await request.json()
        try:return web.json_response({'cities':await companion.cities(data.get('query'))})
        except (OSError,ValueError):return web.json_response({'error':'天气服务暂不可用，请稍后再试。'},status=400)
    async def weather_city(request):
        companion.set_city(await request.json());return web.json_response({'ok':True})

    async def import_file(request):
        import base64
        require_idle()
        data=await request.json()
        name=data['name']
        if '/' in name or '\\' in name or name.startswith('.'): raise ValueError('无效文件名')
        path=files.path(name)
        if path.exists(): raise ValueError('同名文件已存在，请重命名后上传')
        if path.suffix.lower() not in {'.txt','.md','.csv','.tsv','.json','.docx','.xlsx','.pdf','.html','.log'}: raise ValueError('暂不支持此文件格式')
        try: content=base64.b64decode(data['content'],validate=True)
        except ValueError: raise ValueError('文件传输内容无效')
        if len(content)>20*1024*1024: raise ValueError('单文件上限20MB')
        return web.json_response(await asyncio.to_thread(files.commit,path,lambda temp:temp.write_bytes(content)))

    async def new_session(request):
        return web.json_response({'id':store.session()})

    async def chat(request):
        data=await request.json()
        text=data.get('text','').strip()
        if not text or len(text)>6000: raise ValueError('请输入1–6000字；长文件请上传')
        sid=data.get('session')
        if not store.rows('SELECT id FROM sessions WHERE id=?',(sid,)): raise ValueError('会话不存在')
        if any(not job.done() for job in jobs.values()):
            return web.json_response({'error':'正在处理一个任务；请等待完成或先停止。'},status=409)
        resume=data.get('resume')
        if resume: store.task(resume)
        tid=store.create_task(sid,text)
        skill=data.get('skill')
        if skill:
            from . import skills as skill_table
            if skill not in skill_table.RUNNERS: raise ValueError('未知的标签：'+str(skill))
            names={i['path'] for i in files.listing()}
            chosen=[f for f in (data.get('files') or []) if isinstance(f,str) and f in names]
            options={k:v for k,v in (data.get('options') or {}).items() if k in skill_table.OPTIONS and v not in (None,'')}
            store.update_task(tid,intent={'forced':{'skill':skill,'files':chosen,'options':options}})
        jobs[tid]=asyncio.create_task(agent.run(tid,resume=resume))
        jobs[tid].add_done_callback(lambda done: jobs.pop(tid,None))
        return web.json_response({'task':tid})

    async def task_detail(request):
        tid=request.match_info['tid']
        evidence=[]
        for item in store.evidence(tid):
            payload=item.get('payload') if isinstance(item.get('payload'),dict) else {}
            summary={k:payload.get(k) for k in ('price','pair','url','close','open') if k in payload}
            if 'text' in payload: summary['characters']=len(payload['text'])
            evidence.append({'id':item['id'],'kind':item['kind'],'source':item['source'],'data_ts':item['data_ts'],'fetched_at':item['fetched_at'],'summary':summary})
        return web.json_response({'task':store.task(tid),
            'events':store.rows('SELECT id,task,kind,detail,created FROM events WHERE task=? ORDER BY id',(tid,)),
            'steps':store.rows('SELECT seq,kind,status,artifact,sha256,started,finished FROM task_steps WHERE task=? ORDER BY seq',(tid,)),
            'evidence':evidence,
            'questions':store.rows('SELECT * FROM questions WHERE task=? ORDER BY created',(tid,))})

    async def question_answer(request):
        data=await request.json();ident=request.match_info['qid']
        rows=store.rows('SELECT * FROM questions WHERE id=?',(ident,))
        if not rows:raise ValueError('问题不存在')
        q=rows[0]
        if data.get('action')=='cancel':
            if q['status']!='pending':raise ValueError('问题已经处理')
            pending_job=jobs.get(q['task'])
            if pending_job and not pending_job.done():
                pending_job.cancel();await asyncio.gather(pending_job,return_exceptions=True)
            with store.db:
                store.db.execute("UPDATE questions SET status='cancelled' WHERE id=?",(ident,))
                store.db.execute("UPDATE tasks SET status='cancelled',answer=?,updated=? WHERE id=?",('用户取消了待补充任务。',time.time(),q['task']))
            store.event(q['task'],'user_input_cancelled',{})
            return web.json_response({'cancelled':True})
        if q['status']=='answered':return web.json_response({'task':q['continuation'],'session':store.task(q['continuation'])['session'],'already_answered':True})
        if any(not job.done() for job in jobs.values()):return web.json_response({'error':'正在处理任务，请等待结束后再继续。'},status=409)
        tid,created=store.answer_question(ident,data.get('answer'))
        if created:
            jobs[tid]=asyncio.create_task(agent.run(tid,resume=q['task']))
            jobs[tid].add_done_callback(lambda done:jobs.pop(tid,None))
        return web.json_response({'task':tid,'session':store.task(tid)['session']})

    async def messages(request):
        return web.json_response(store.rows('SELECT role,content,created FROM messages WHERE session=? ORDER BY id',
                                           (request.match_info['sid'],)))

    async def cancel(request):
        tid=request.match_info['tid']
        job=jobs.get(tid)
        if job:
            job.cancel()
            return web.json_response({'stopping':True},status=202)
        return web.json_response({'stopped':True})

    def require_idle():
        if any(not job.done() for job in jobs.values()):
            raise ValueError('请先停止或等待当前任务，避免在执行途中改动记忆或文件。')

    async def memory(request):
        require_idle()
        data=await request.json()
        if request.method=='DELETE':
            result=store.forget(data['key'])
        else:
            result=store.remember(data['key'],data['value'],'用户在记忆面板明确设置',data.get('category','preference'))
        return web.json_response(result)

    async def memory_candidates(request):
        return web.json_response({'candidates':store.memory_candidates()})

    async def memory_candidate(request):
        data=await request.json()
        return web.json_response(store.resolve_candidate(request.match_info['cid'],data.get('action')=='accept'))

    async def memory_export(request):
        return web.json_response({'version':1,'memories':store.memories(limit=100000)})

    async def upload(request):
        require_idle()
        reader=await request.multipart()
        part=await reader.next()
        if not part or not part.filename: raise ValueError('请选择文件')
        name=part.filename
        if '/' in name or '\\' in name or name.startswith('.'): raise ValueError('无效文件名')
        path=files.path(name)
        if path.exists(): raise ValueError('同名文件已存在，请先重命名再上传')
        allowed={'.txt','.md','.csv','.tsv','.json','.docx','.xlsx','.pdf','.html','.log'}
        if path.suffix.lower() not in allowed: raise ValueError('暂不支持此文件格式')
        content=bytearray()
        while chunk:=await part.read_chunk():
            content.extend(chunk)
            if len(content)>20*1024*1024: raise ValueError('单文件上限20MB')
        result=await asyncio.to_thread(files.commit,path,lambda temp:temp.write_bytes(content))
        return web.json_response(result)

    async def download(request):
        path=files.path(request.query['path'])
        response=web.FileResponse(path)
        from urllib.parse import quote
        response.headers['Content-Disposition']="attachment; filename*=UTF-8''"+quote(path.name)
        return response

    async def restore(request):
        require_idle()
        data=await request.json()
        return web.json_response(await asyncio.to_thread(files.restore,data['backup_id']))

    async def reminder(request):
        data=await request.json()
        action=data.get('action')
        if action=='parse':
            from . import timeparse
            parsed=timeparse.parse(str(data.get('text','')))
            if not parsed: raise ValueError('没听懂时间，试试“明天早上8点提醒我开会”或“30分钟后提醒我”。')
            if 'error' in parsed: raise ValueError(parsed['error'])
            result=store.add_reminder(parsed['text'],parsed['due'],parsed['interval']);result['when']=parsed['when']
        elif action=='add':
            result=store.add_reminder(data['text'],float(data['due']),int(data.get('interval',0)))
        elif action=='ack':
            store.acknowledge(data['id'])
            result={'ok':True}
        elif action=='cancel':
            with store.db:
                store.db.execute("UPDATE reminders SET status='cancelled' WHERE id=?",(data['id'],))
            result={'ok':True}
        else: raise ValueError('无效提醒操作')
        return web.json_response(result)

    async def watchdog(app):
        """If the event loop stops turning for >3s, dump the main thread's stack to the log (desktop.log) so a
        freeze is attributed to a line of code, not guessed at. The launcher only restarts the agent after ~45s."""
        import sys,threading,traceback
        beat={'t':time.monotonic()}
        main_id=threading.get_ident()
        heartbeat=home/'data'/'heartbeat'
        async def pulse():
            n=0
            while True:
                beat['t']=time.monotonic();n+=1
                if n%2==0:
                    # The launcher judges liveness by this file's age, not by an HTTP probe that a system proxy can hijack.
                    try: heartbeat.write_text(str(time.time()))
                    except OSError: pass
                await asyncio.sleep(0.5)
        def watch():
            reported=0.0
            while not app.get('closing'):
                time.sleep(1)
                lag=time.monotonic()-beat['t']
                if lag>3 and time.monotonic()-reported>10:
                    reported=time.monotonic()
                    frame=sys._current_frames().get(main_id)
                    stack=''.join(traceback.format_stack(frame)[-12:]) if frame else '(no frame)'
                    print(f'[lulu-watchdog] event loop blocked for {lag:.1f}s; main thread at:\n{stack}',file=sys.stderr,flush=True)
        app['pulse']=asyncio.create_task(pulse())
        threading.Thread(target=watch,daemon=True,name='lulu-watchdog').start()

    async def warmup(app):
        """Measure speed once per model so timeouts fit this machine; skipped when the model server is down."""
        provider=agent.provider
        if agent.budget.measured_at and agent.budget.model==provider.model: return
        async def job():
            try:
                names=await provider.models()
                if names is None or (provider.kind=='ollama' and provider.get_default_model() not in names and provider.get_default_model()+':latest' not in names): return
                measured,error=await budgeting.measure(provider,budget_path)
                if not error and agent.provider is provider: agent.budget=measured;agent.writer.budget=measured;provider.num_thread=measured.num_thread
            except Exception: pass
        app['warmup']=asyncio.create_task(job())

    async def cleanup(app):
        app['closing']=True
        pulse=app.get('pulse')
        if pulse and not pulse.done(): pulse.cancel()
        warm=app.get('warmup')
        if warm and not warm.done(): warm.cancel()
        active=list(jobs.values())
        for job in active: job.cancel()
        await asyncio.gather(*active,return_exceptions=True)
        await companion.close()
        store.db.close()

    app.router.add_get('/',index)
    app.router.add_get('/api/state',state)
    app.router.add_get('/api/health',health)
    app.router.add_get('/api/budget',budget_view)
    app.router.add_post('/api/budget/measure',budget_measure)
    app.router.add_get('/api/backend',backend_get)
    app.router.add_post('/api/backend',backend_set)
    app.router.add_post('/api/backend/secret',backend_secret)
    app.router.add_post('/api/backend/probe',backend_probe)
    app.router.add_post('/api/backend/test',backend_test)
    app.router.add_get('/api/desktop',desktop)
    app.router.add_get('/api/companion',companion_state)
    app.router.add_post('/api/care/dismiss',care_dismiss)
    app.router.add_post('/api/weather/search',weather_search)
    app.router.add_post('/api/weather/city',weather_city)
    app.router.add_post('/api/import',import_file)
    app.router.add_post('/api/sessions',new_session)
    app.router.add_get('/api/sessions/{sid}',messages)
    app.router.add_post('/api/chat',chat)
    app.router.add_post('/api/questions/{qid}/answer',question_answer)
    app.router.add_get('/api/tasks/{tid}',task_detail)
    app.router.add_post('/api/tasks/{tid}/cancel',cancel)
    app.router.add_post('/api/memory',memory)
    app.router.add_delete('/api/memory',memory)
    app.router.add_get('/api/memory/export',memory_export)
    app.router.add_get('/api/memory/candidates',memory_candidates)
    app.router.add_post('/api/memory/candidates/{cid}',memory_candidate)
    app.router.add_post('/api/upload',upload)
    app.router.add_get('/api/download',download)
    app.router.add_post('/api/restore',restore)
    app.router.add_post('/api/reminders',reminder)
    app.on_startup.append(watchdog)
    app.on_startup.append(warmup)
    app.on_cleanup.append(cleanup)
    return app
