"""Local idle duration only; never capture keys, text, screenshots or app content."""
import ctypes,sys,time
from datetime import datetime

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
    """Two care events, both decided here and only played by the pet.
    candy: every CANDY_SECONDS (four hours) after Lulu started, whatever the user was doing; the offer waits until the
    pet is free to show it, so a user who was away sees it on return.
    night: between NIGHT_START and NIGHT_END on the *local* clock passed in (the weather city's time when one is set),
    once every NIGHT_REPEAT seconds while the user is present (input within PRESENT_SECONDS).
    `work` only reports active seconds for diagnostics; a BREAK_SECONDS pause resets it."""
    CANDY_SECONDS=14400;BREAK_SECONDS=300;PRESENT_SECONDS=60
    NIGHT_START=18;NIGHT_END=6;NIGHT_REPEAT=3600
    def __init__(self):
        self.last=None;self.started=None;self.work=0.;self.night_last=None;self.candies=0
        self.pending=None;self.serial=0
    @classmethod
    def is_night(cls,local):
        return local.hour>=cls.NIGHT_START or local.hour<cls.NIGHT_END
    def update(self,idle,stamp=None,local=None):
        stamp=time.monotonic() if stamp is None else stamp
        local=datetime.now() if local is None else local
        if self.started is None:self.started=stamp
        delta=0 if self.last is None else max(0,min(5,stamp-self.last));self.last=stamp
        if idle is not None:
            if idle>=self.BREAK_SECONDS:
                self.work=0.
                if self.pending and self.pending['action']=='night':self.pending=None
            elif idle<self.PRESENT_SECONDS:
                self.work+=delta
                if self.pending is None and self.is_night(local) and (self.night_last is None or stamp-self.night_last>=self.NIGHT_REPEAT):
                    self._emit('night');self.night_last=stamp
        if self.pending is None and stamp-self.started>=(self.candies+1)*self.CANDY_SECONDS:
            self.candies+=1;self._emit('candy')
        return self.snapshot(idle is not None)
    def _emit(self,kind):
        self.serial+=1;self.pending={'id':self.serial,'action':kind}
    def dismiss(self,ident):
        if self.pending and self.pending['id']==ident:self.pending=None
    def snapshot(self,available):
        return {'available':available,'active_seconds':round(self.work),'event':self.pending}
