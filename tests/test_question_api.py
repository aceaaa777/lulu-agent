import asyncio
from aiohttp.test_utils import TestClient,TestServer
from lulu.server import create_app


def test_answer_resume_records_and_double_click(tmp_path):
 async def run():
  (tmp_path/'static').mkdir();app=create_app(tmp_path,port=18785);s=app['store'];old=s.create_task(s.session(),'生成报告');q=s.ask(old,'请提供项目资料','需要原文');s.update_task(old,status='awaiting_input');calls=[]
  async def agent_run(tid,resume=None):
   calls.append((tid,resume));s.update_task(tid,status='completed',answer='测试完成')
  app['agent'].run=agent_run
  async with TestClient(TestServer(app,host='127.0.0.1',port=18785)) as c:
   h={'X-Lulu-Token':app['token']};url='/api/questions/'+q['id']+'/answer'
   assert (await c.post(url,json={'answer':'资料'})).status==403
   assert (await c.post(url,headers=h,json={'answer':''})).status==400
   state=await(await c.get('/api/desktop',headers=h)).json();assert state['questions'][0]['id']==q['id']
   first=await(await c.post(url,headers=h,json={'answer':'资料如下：完成3项工作。'})).json();await asyncio.sleep(.05)
   second=await(await c.post(url,headers=h,json={'answer':'重复点击'})).json()
   assert first['task']==second['task']==old and len(calls)==1 and calls[0][1]==old
   record=await(await c.get('/api/tasks/'+first['task'],headers=h)).json()
   assert any(e['kind']=='user_input_answered' for e in record['events'])
   assert not (await(await c.get('/api/desktop',headers=h)).json())['questions']
 asyncio.run(run())
