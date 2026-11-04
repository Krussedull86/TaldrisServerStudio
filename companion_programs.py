"""Check full EXE identity and start missing companions with explicit manual lifecycle controls."""
import os,subprocess,sys,threading
from pathlib import Path
import psutil
from runtime_tools import arguments

def key(path):return os.path.normcase(str(Path(path).resolve()))

class CompanionPrograms:
    def __init__(self):self.lock=threading.RLock();self.launched={}
    def inspect(self,program):
        path=key(program['path']);args=arguments(program.get('args',''));pids=[];uncertain=False
        for identity,proc in list(self.launched.items()):
            if proc.poll() is not None:self.launched.pop(identity,None);continue
            if identity[0]==path and (not args or tuple(args)==identity[1]):pids.append(proc.pid)
        for proc in psutil.process_iter(['pid','name','exe','cmdline'],ad_value=None):
            try:
                info=proc.info
                if info.get('exe') and key(info['exe'])==path:
                    if args and info.get('cmdline') is None:uncertain=True;continue
                    if not args or (info.get('cmdline') or [])[1:]==args:pids.append(info['pid'])
                elif not info.get('exe') and str(info.get('name','')).casefold()==Path(program['path']).name.casefold():uncertain=True
            except (OSError,psutil.Error):continue
        return dict(id=program['id'],name=program.get('name') or Path(program['path']).stem,status='running' if pids else 'unknown' if uncertain else 'stopped',pids=sorted(set(pids)))
    def statuses(self,programs):
        with self.lock:return [self.inspect(p) for p in programs]
    def ensure(self,programs,event,log,stop_event):
        for p in programs:
            if not p.get('enabled',True) or not p.get('on_restart' if event=='restart' else 'on_start',True):continue
            try:
                with self.lock:
                    status=self.inspect(p)
                    if status['status']=='running':log('Companion program is already running: '+status['name']+' • PID '+', '.join(map(str,status['pids'])));continue
                    if status['status']=='unknown':raise ValueError('A matching process cannot be inspected. Check access permissions before launching another instance.')
                    path=Path(p['path']).resolve();cwd=Path(p.get('cwd') or path.parent).resolve()
                    if not path.is_file():raise ValueError('The EXE file does not exist: '+str(path))
                    if not cwd.is_dir():raise ValueError('The working directory does not exist: '+str(cwd))
                    if getattr(sys,'frozen',False) and path==Path(sys.executable).resolve():raise ValueError('The control panel cannot be launched as its own companion program.')
                    log('Starting companion program: '+str(path)+' • Working directory: '+str(cwd))
                    proc=subprocess.Popen([str(path),*arguments(p.get('args',''))],cwd=str(cwd),close_fds=True,creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'CREATE_NEW_CONSOLE',0),env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
                    self.launched[(key(path),tuple(arguments(p.get('args',''))))]=proc
                if stop_event.wait(p.get('wait_seconds',2)):raise ValueError('The agent is shutting down; server startup is cancelled.')
                if proc.poll() is not None:raise ValueError('The program process exited during startup, code '+str(proc.returncode)+'.')
                log('Companion program started: '+status['name']+' • PID '+str(proc.pid)+'. This only confirms that the process is running.')
            except Exception as error:
                log('Companion program '+str(p.get('name') or p.get('path'))+': '+str(error))
                if p.get('required',True):raise ValueError('A required companion program did not become ready: '+str(error)) from error

    def control(self,program,action,log,stop_event):
        if action not in ('start','stop','restart'):raise ValueError('Unknown program action.')
        with self.lock:
            status=self.inspect(program)
            if status['status']=='unknown':raise ValueError('The process cannot be inspected. Check access permissions.')
            if action in ('stop','restart'):
                for pid in status['pids']:
                    try:
                        proc=psutil.Process(pid)
                        # Revalidate identity immediately before signalling; never stop by filename alone.
                        if key(proc.exe())!=key(program['path']):raise ValueError('The process identity has changed.')
                        args=arguments(program.get('args',''))
                        if args and proc.cmdline()[1:]!=args:raise ValueError('The process arguments have changed.')
                        proc.terminate()
                        proc.wait(timeout=15)
                        log('Companion program stopped: '+status['name']+' • PID '+str(pid))
                    except psutil.NoSuchProcess:pass
                    except psutil.TimeoutExpired:raise ValueError('The program did not exit within 15 seconds. A new process will not be started.')
            if action in ('start','restart'):
                self.ensure([dict(program,enabled=True,on_start=True,required=True)],'start',log,stop_event)
            return self.inspect(program)
