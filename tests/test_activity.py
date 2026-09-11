import unittest
from datetime import datetime
from lulu.activity import CareMonitor
class CareTests(unittest.TestCase):
 def feed(self,c,seconds,hour=12,idle=0,start=0):
  for i in range(seconds+1):r=c.update(idle,start+i,datetime(2026,9,7,hour))
  return r
 def test_candy_four_hours_after_start_and_ack(self):
  c=CareMonitor();r=self.feed(c,14399);self.assertIsNone(r['event']);r=self.feed(c,1,start=14399)
  self.assertEqual(r['event']['action'],'candy');ident=r['event']['id'];self.feed(c,10,start=14400);self.assertEqual(c.pending['id'],ident)
  c.dismiss(ident);self.assertIsNone(c.pending)
  self.assertIsNone(self.feed(c,100,start=14411)['event'])
  self.assertEqual(c.update(0,28800,datetime(2026,9,7,12))['event']['action'],'candy')   # and again every four hours of uptime
 def test_candy_does_not_need_the_user_present(self):
  noon=datetime(2026,9,7,12);c=CareMonitor();c.update(600,0,noon);self.assertEqual(c.update(600,14400,noon)['event']['action'],'candy')   # away at the 4 h mark: the offer waits
  self.assertEqual(c.update(600,15000,noon)['event']['action'],'candy')
  c=CareMonitor();c.update(None,0,noon);self.assertEqual(c.update(None,14400,noon)['event']['action'],'candy')   # idle detection unavailable
 def test_break_resets_active_seconds_only(self):
  c=CareMonitor();self.feed(c,200);c.update(300,201,datetime(2026,9,7,12));self.assertEqual(c.work,0)
  self.assertIsNone(self.feed(c,100,start=201)['event'])
 def test_no_activity_no_night(self):
  c=CareMonitor();self.assertIsNone(self.feed(c,3000,idle=600)['event'])
  self.assertFalse(c.update(None,3001)['available'])
  self.assertIsNone(self.feed(c,10,hour=23,idle=600)['event'])   # nobody at the desk: no night face
 def test_night_from_six_pm_hourly(self):
  c=CareMonitor();self.assertIsNone(self.feed(c,5,17)['event'])
  r=self.feed(c,0,18,start=6);self.assertEqual(r['event']['action'],'night');c.dismiss(r['event']['id'])
  self.assertIsNone(self.feed(c,3598,18,start=7)['event'])
  r=self.feed(c,1,19,start=3605);self.assertEqual(r['event']['action'],'night');c.dismiss(r['event']['id'])
  self.assertEqual(self.feed(c,3600,23,start=3607)['event']['action'],'night')
 def test_night_spans_past_midnight_until_six(self):
  c=CareMonitor();self.assertEqual(self.feed(c,0,5)['event']['action'],'night')
  c=CareMonitor();self.assertIsNone(self.feed(c,0,6)['event'])
 def test_stale_night_dropped_on_break_candy_kept(self):
  c=CareMonitor();self.assertEqual(c.update(0,0,datetime(2026,9,7,20))['event']['action'],'night')
  self.assertIsNone(c.update(400,10,datetime(2026,9,7,20))['event'])
  noon=datetime(2026,9,7,12);c=CareMonitor();c.update(0,0,noon);self.assertEqual(c.update(0,14400,noon)['event']['action'],'candy')
  self.assertEqual(c.update(400,14410,noon)['event']['action'],'candy')
 def test_night_before_candy(self):
  c=CareMonitor();c.update(0,0,datetime(2026,9,7,12));r=c.update(0,14400,datetime(2026,9,7,20))
  self.assertEqual(r['event']['action'],'night');c.dismiss(r['event']['id'])
  self.assertEqual(c.update(0,14401,datetime(2026,9,7,20))['event']['action'],'candy')
 def test_suspend_not_counted(self):
  noon=datetime(2026,9,7,12);c=CareMonitor();c.update(0,0,noon);c.update(0,10000,noon);self.assertEqual(c.work,5)
class CityClockTests(unittest.TestCase):
 def test_city_offset_drives_local_time(self):
  from datetime import timezone,timedelta
  from lulu.companion import Companion
  c=Companion.__new__(Companion);c.weather={'condition':'unknown'}
  self.assertLess(abs((c.local_time()-datetime.now()).total_seconds()),5)
  c.weather={'condition':'sunny','utc_offset_seconds':28800}
  expected=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(hours=8)
  self.assertLess(abs((c.local_time()-expected).total_seconds()),5)
if __name__=='__main__':unittest.main()
