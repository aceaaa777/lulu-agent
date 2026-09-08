import unittest
from datetime import datetime
from bridge.activity import CareMonitor
class CareTests(unittest.TestCase):
 def feed(self,c,seconds,hour=12,idle=0,start=0):
  for i in range(seconds+1):r=c.update(idle,start+i,datetime(2026,9,7,hour))
  return r
 def test_day_threshold_and_ack(self):
  c=CareMonitor();r=self.feed(c,2699);self.assertIsNone(r['event']);r=self.feed(c,1,start=2699)
  self.assertEqual(r['event']['action'],'candy');ident=r['event']['id'];self.feed(c,10,start=2700);self.assertEqual(c.pending['id'],ident)
  c.dismiss(ident);self.assertIsNone(c.pending)
 def test_break_resets(self):
  c=CareMonitor();self.feed(c,2600);c.update(300,2601,datetime(2026,9,7,12));self.assertEqual(c.work,0)
  self.assertIsNone(self.feed(c,200,start=2601)['event'])
 def test_no_activity_no_care(self):
  c=CareMonitor();self.assertIsNone(self.feed(c,3000,idle=600)['event'])
  self.assertFalse(c.update(None,3001)['available'])
 def test_night_once(self):
  c=CareMonitor();r=self.feed(c,600,23);self.assertEqual(r['event']['action'],'night');c.dismiss(r['event']['id'])
  self.assertIsNone(self.feed(c,600,23,start=600)['event'])
 def test_suspend_not_counted(self):
  c=CareMonitor();c.update(0,0);c.update(0,10000);self.assertEqual(c.work,5)
if __name__=='__main__':unittest.main()
