"""Local idle duration only; never capture keys, text, screenshots or app content."""
import ctypes,sys,time
from datetime import datetime,timedelta

def system_idle_seconds():
    try:
        if sys.platform=='win32':
            class LastInput(ctypes.Structure):
                _fields_=[('cbSize',ctypes.c_uint),('dwTime',ctypes.c_uint32)]
            info=LastInput();info.cbSize=ctypes.sizeof(info)
            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):return None
            ctypes.windll.kernel32.GetTickCount.restype=ctypes.c_uint32
            return ((ctypes.windll.kernel32.GetTickCount()-info.dwTime)&0xffffffff)/1000.0
        if sys.platform=='darwin':
            lib=ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
            fn=lib.CGEventSourceSecondsSinceLastEventType;fn.argtypes=[ctypes.c_int,ctypes.c_uint32];fn.restype=ctypes.c_double
            result=fn(0,0xffffffff)
            return result if 0<=result<1e8 else None
    except (OSError,AttributeError):pass
    return None

class CareMonitor:
    def __init__(self):
        self.last=None;self.work=0.;self.night_work=0.;self.night_key='';self.night_sent=False
        self.pending=None;self.serial=0
    def update(self,idle,stamp=None,local=None):
        stamp=time.monotonic() if stamp is None else stamp
        local=datetime.now() if local is None else local
        delta=0 if self.last is None else max(0,min(5,stamp-self.last));self.last=stamp
        key=(local-timedelta(days=1) if local.hour<6 else local).strftime('%Y-%m-%d')
        if key!=self.night_key:self.night_key=key;self.night_sent=False;self.night_work=0
        if idle is None:return self.snapshot(False)
        if idle>=300:self.work=0.;self.night_work=0.;self.pending=None
        if idle<60:
            self.work+=delta
            if local.hour>=22 or local.hour<6:self.night_work+=delta
            if self.pending is None:
                if self.night_work>=600 and not self.night_sent:
                    self._emit('night');self.night_sent=True
                elif self.work>=2700:self._emit('candy');self.work=0.
        return self.snapshot(True)
    def _emit(self,kind):
        self.serial+=1;self.pending={'id':self.serial,'action':kind}
    def dismiss(self,ident):
        if self.pending and self.pending['id']==ident:self.pending=None
    def snapshot(self,available):
        return {'available':available,'active_seconds':round(self.work),'event':self.pending}
