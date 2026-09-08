import sys,unittest,tempfile,time
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge.companion import parse_reminder,classify
from bridge.server import Bridge
class Tests(unittest.TestCase):
 def test_times(self):
  now=datetime(2026,9,6,10,0).timestamp()
  self.assertEqual(parse_reminder('10分钟后提醒我喝水',now)['due_at'],now+600)
  self.assertEqual(parse_reminder('半小时后提醒我休息',now)['due_at'],now+1800)
  self.assertEqual(parse_reminder('明天下午三点半提醒我交作业',now)['due_at'],datetime(2026,9,7,15,30).timestamp())
  self.assertEqual(parse_reminder('今天15:00提醒我开会',now)['due_at'],datetime(2026,9,6,15).timestamp())
  for text in ['提醒我喝水','三点提醒我','今天09:00提醒我','0分钟后提醒我','每天下午三点提醒我喝水','取消提醒我喝水']:
   with self.assertRaises(ValueError,msg=text):parse_reminder(text,now)
  self.assertIsNone(parse_reminder('帮我总结这段话',now))
 def test_persistence(self):
  with tempfile.TemporaryDirectory() as d:
   app=Bridge(Path(d),probe=False)
   self.assertEqual(app.settings()['provider'],'ollama');self.assertEqual(app.settings()['model'],'qwen2.5:7b')
   item=app.companion.create({'due_at':time.time()-1,'title':'喝水','request':'1秒后提醒我喝水'})
   self.assertEqual(len(app.companion.snapshot()['due']),1)
   app.close();app=Bridge(Path(d),probe=False)
   self.assertEqual(app.companion.snapshot()['due'][0]['id'],item['id'])
   app.companion.dismiss(item['id']);self.assertEqual(app.companion.snapshot()['due'],[]);app.close()
 def test_weather(self):
  self.assertEqual(classify(0),'sunny');self.assertEqual(classify(3),'cloudy');self.assertEqual(classify(63),'rainy')
  self.assertEqual(classify(71),'unknown')
if __name__=='__main__':unittest.main()
