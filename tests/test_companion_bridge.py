import asyncio
from aiohttp.test_utils import TestClient, TestServer
from lulu.server import create_app


def test_animation_events_and_companion(tmp_path):
    async def run():
        (tmp_path/'static').mkdir()
        app=create_app(tmp_path,port=18781)
        async with TestClient(TestServer(app,host='127.0.0.1',port=18781)) as c:
            h={'X-Lulu-Token':app['token']};store=app['store']
            sid=store.session();tid=store.create_task(sid,'制作文档')
            async def snapshot():return await (await c.get('/api/desktop',headers=h)).json()
            assert (await snapshot())['lang']=='zh'
            assert (await snapshot())['tasks'][0]['animation']=='thinking'
            store.event(tid,'tool_started',{'name':'generate_document'})
            assert (await snapshot())['tasks'][0]['animation']=='working'
            store.event(tid,'drafting',{})   # 起草是动手，继续敲键盘
            assert (await snapshot())['tasks'][0]['animation']=='working'
            store.event(tid,'thinking',{'stage':'answer'})
            assert (await snapshot())['tasks'][0]['animation']=='thinking'
            store.event(tid,'skill_started',{'skill':'translate'})
            assert (await snapshot())['tasks'][0]['animation']=='working'
            store.event(tid,'skill_started',{'skill':'chat'})   # 聊天没有动手的部分
            assert (await snapshot())['tasks'][0]['animation']=='thinking'
            store.event(tid,'tool_done',{})
            assert (await snapshot())['tasks'][0]['status']!='completed'
            assert (await c.get('/api/companion')).status==403
            scene=await (await c.get('/api/companion',headers=h)).json()
            assert scene['weather']['condition']=='unknown' and scene['due']==[]
            assert (await c.post('/api/weather/city',headers=h,json={'name':'x','latitude':999,'longitude':0})).status==400
            assert (await c.post('/api/care/dismiss',headers=h,json={'id':0})).status==200
    asyncio.run(run())
