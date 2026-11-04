"""SteamCMD console startup and streaming evidence, shared by agent and desktop."""
import os,re,sys,threading
from pathlib import Path
from steam_status import plain_terminal

_spawn_lock=threading.RLock()

def spawn_steam(exe,args,cwd=None):
    from winpty import PtyProcess
    exe=Path(exe).resolve()
    env=os.environ.copy()
    bundle=getattr(sys,'_MEIPASS',None)
    if bundle:
        root=os.path.normcase(os.path.abspath(bundle))
        def bundled(value):
            value=os.path.normcase(os.path.abspath(value.strip('"')))
            return value==root or value.startswith(root+os.sep)
        env['PATH']=os.pathsep.join(p for p in env.get('PATH','').split(os.pathsep) if p and not bundled(p))
    # Windows children inherit PyInstaller's DLL directory. Steam must load its
    # own runtime, rather than incompatible DLLs bundled with Qt/Python.
    with _spawn_lock:
        kernel=None;previous=None
        if sys.platform=='win32' and bundle:
            import ctypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.GetDllDirectoryW.argtypes=[ctypes.c_uint32,ctypes.c_wchar_p]
            kernel.SetDllDirectoryW.argtypes=[ctypes.c_wchar_p]
            buf=ctypes.create_unicode_buffer(32768)
            kernel.GetDllDirectoryW(len(buf),buf);previous=buf.value or None
            if not kernel.SetDllDirectoryW(None):raise ctypes.WinError(ctypes.get_last_error())
        try:return PtyProcess.spawn([str(exe),*args],cwd=str(cwd or exe.parent),env=env,dimensions=(40,240))
        finally:
            if kernel is not None:kernel.SetDllDirectoryW(previous)

class ConsoleReplies:
    """Answer terminal capability/cursor queries; these are not login input."""
    def __init__(self):self.tail=''
    def feed(self,text,write):
        data=self.tail+text
        for match in re.finditer(r'\x1b\[(?:6n|0?c|>0?c)',data):
            query=match.group()
            write('\x1b[1;1R' if query.endswith('6n') else '\x1b[>0;0;0c' if '>' in query else '\x1b[?1;0c')
        # Only retain an incomplete escape, never repeat a completed query.
        pos=data.rfind('\x1b')
        tail=data[pos:] if pos>=0 else ''
        self.tail=tail if re.fullmatch(r'\x1b(?:\[(?:>|0|>0|6)?)?',tail) else ''

class SteamEvidence:
    """Keep result lines even after a long download scrolls out of the UI."""
    def __init__(self):self.pending='';self.lines=[]
    def feed(self,text):
        self.pending+=text
        parts=re.split(r'[\r\n]',self.pending)
        self.pending=parts.pop()[-8192:]
        for line in parts:
            line=plain_terminal(line)
            if re.search(r'Success[!.]|ERROR!|FAILED\b|No subscription|Access Denied|Invalid (?:Password|Login)|Rate Limit|Logged in|Logging in|Waiting for user info|Restarting SteamCMD',line,re.I):
                self.lines.append(line)
    def text(self):return '\n'.join(self.lines+[plain_terminal(self.pending)])
