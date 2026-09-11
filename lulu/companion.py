"""Optional city weather and local activity care, independent of model tasks."""
import asyncio,json,os,time,urllib.request,urllib.parse
from datetime import datetime,timedelta,timezone
from .activity import CareMonitor,system_idle_seconds
def fetch_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'LuluCompanion/0.2'})
    with urllib.request.urlopen(req,timeout=8) as response:
        raw=response.read(200001)
    if len(raw)>200000:raise ValueError('天气响应过长')
    return json.loads(raw)

def classify(code):
    if code in (0,1):return 'sunny'
    if code in (2,3,45,48):return 'cloudy'
    if code in (51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99):return 'rainy'
    return 'unknown' # Snow is not silently represented as rain.


class Companion:
    def __init__(self,store):
        self.store=store; self.care=CareMonitor(); self.next_weather=0; self.job=None; self.locate_job=None; self.located=False
        with store.db: store.db.execute('CREATE TABLE IF NOT EXISTS companion_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        self.weather={'condition':'unknown','city':'','detail':'正在按网络位置找你所在的城市…'}

    async def locate(self):
        """No city chosen yet: place the user by IP (city-level, enough for weather). A chosen city always wins."""
        self.located=True
        for url,pick in (('https://ipapi.co/json/',lambda d:(d.get('city'),d.get('latitude'),d.get('longitude'))),
                         ('http://ip-api.com/json/?fields=status,city,lat,lon&lang=zh-CN',lambda d:(d.get('city'),d.get('lat'),d.get('lon')))):
            try:
                data=await asyncio.to_thread(fetch_json,url)
                name,lat,lon=pick(data)
                if name and lat is not None and lon is not None:
                    if self.store.rows("SELECT value FROM companion_settings WHERE key='city'"): return
                    self.set_city({'name':str(name),'latitude':float(lat),'longitude':float(lon)},auto=True)
                    return
            except Exception: continue
        self.weather={'condition':'unknown','city':'','detail':'没能自动定位，在设置里选一个城市就行。'}
    async def cities(self,query):
        if not isinstance(query,str) or not 1<=len(query)<=80: raise ValueError('请输入城市名称')
        data=await asyncio.to_thread(fetch_json,'https://geocoding-api.open-meteo.com/v1/search?'+urllib.parse.urlencode({'name':query,'count':8,'language':'zh','format':'json'}))
        return [{'name':x['name'],'country':x.get('country',''),'admin1':x.get('admin1',''),'latitude':x['latitude'],'longitude':x['longitude']} for x in data.get('results',[])]
    def set_city(self,city,auto=False):
        lat,lon=float(city['latitude']),float(city['longitude'])
        if not -90<=lat<=90 or not -180<=lon<=180: raise ValueError('坐标无效')
        item={'name':str(city['name'])[:80],'latitude':lat,'longitude':lon,'auto':bool(auto)}
        with self.store.db:self.store.db.execute('INSERT OR REPLACE INTO companion_settings VALUES (?,?)',('city',json.dumps(item)))
        self.next_weather=0
        self.weather={'condition':'unknown','city':item['name'],'detail':'正在更新天气…'}
    async def update_weather(self,raw):
        city=json.loads(raw)
        try:
            q={**{k:city[k] for k in ('latitude','longitude')},'current':'weather_code,temperature_2m','timezone':'auto'}
            data=await asyncio.to_thread(fetch_json,'https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode(q))
            cur=data['current'];result={'condition':classify(int(cur['weather_code'])),'city':city['name'],'detail':str(cur['temperature_2m'])+' °C'+('（按网络位置自动找到的）' if city.get('auto') else ''),'source':'Open-Meteo','auto':bool(city.get('auto'))}
            if isinstance(data.get('utc_offset_seconds'),(int,float)):result['utc_offset_seconds']=int(data['utc_offset_seconds'])   # the city's clock drives the night care
        except Exception:result={'condition':'unknown','city':city['name'],'detail':'天气暂不可用，使用普通待机'}
        latest=self.store.rows("SELECT value FROM companion_settings WHERE key='city'")
        if latest and latest[0]['value']==raw:self.weather=result
    def local_time(self):
        """Wall-clock time where the user is: the weather city's timezone once Open-Meteo has told us, else this computer's clock."""
        offset=self.weather.get('utc_offset_seconds')
        if offset is None:return datetime.now()
        return datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(seconds=int(offset))
    def snapshot(self):
        rows=self.store.rows("SELECT value FROM companion_settings WHERE key='city'")
        if not rows and not self.located and not os.environ.get('LULU_NO_LOCATE') and (self.locate_job is None or self.locate_job.done()):
            self.locate_job=asyncio.create_task(self.locate())
        if time.monotonic()>=self.next_weather and (self.job is None or self.job.done()):
            self.next_weather=time.monotonic()+1800
            if rows:self.job=asyncio.create_task(self.update_weather(rows[0]['value']))
        return {'weather':self.weather,'care':self.care.update(system_idle_seconds(),local=self.local_time()),'due':self.store.rows("SELECT * FROM reminders WHERE status='pending' AND due<=? ORDER BY due",(time.time(),))}
    async def close(self):
        for job in (self.job,self.locate_job):
            if job:
                job.cancel();await asyncio.gather(job,return_exceptions=True)
