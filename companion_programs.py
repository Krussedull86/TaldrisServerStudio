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
                    if status['status']=='running':log('Tilleggsprogram kjører allerede: '+status['name']+' • PID '+', '.join(map(str,status['pids'])));continue
                    if status['status']=='unknown':raise ValueError('En tilsvarende prosess kan ikke kontrolleres. Kontroller tilgang/rettigheter før ny start.')
                    path=Path(p['path']).resolve();cwd=Path(p.get('cwd') or path.parent).resolve()
                    if not path.is_file():raise ValueError('EXE-filen finnes ikke: '+str(path))
                    if not cwd.is_dir():raise ValueError('Arbeidsmappen finnes ikke: '+str(cwd))
                    if getattr(sys,'frozen',False) and path==Path(sys.executable).resolve():raise ValueError('Kontrollpanelet kan ikke startes som sitt eget tilleggsprogram.')
                    log('Starter tilleggsprogram: '+str(path)+' • Arbeidsmappe: '+str(cwd))
                    proc=subprocess.Popen([str(path),*arguments(p.get('args',''))],cwd=str(cwd),close_fds=True,creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'CREATE_NEW_CONSOLE',0),env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
                    self.launched[(key(path),tuple(arguments(p.get('args',''))))]=proc
                if stop_event.wait(p.get('wait_seconds',2)):raise ValueError('Agenten avsluttes; serverstart avbrytes.')
                if proc.poll() is not None:raise ValueError('Programprosessen avsluttet under oppstart, kode '+str(proc.returncode)+'.')
                log('Tilleggsprogram startet: '+status['name']+' • PID '+str(proc.pid)+'. Dette bekrefter bare at prosessen kjører.')
            except Exception as error:
                log('Tilleggsprogram '+str(p.get('name') or p.get('path'))+': '+str(error))
                if p.get('required',True):raise ValueError('Påkrevd tilleggsprogram ble ikke klart: '+str(error)) from error

    def control(self,program,action,log,stop_event):
        if action not in ('start','stop','restart'):raise ValueError('Ukjent programhandling.')
        with self.lock:
            status=self.inspect(program)
            if status['status']=='unknown':raise ValueError('Prosessen kan ikke kontrolleres. Sjekk tilgang/rettigheter.')
            if action in ('stop','restart'):
                for pid in status['pids']:
                    try:
                        proc=psutil.Process(pid)
                        # Revalidate identity immediately before signalling; never stop by filename alone.
                        if key(proc.exe())!=key(program['path']):raise ValueError('Prosessidentiteten er endret.')
                        args=arguments(program.get('args',''))
                        if args and proc.cmdline()[1:]!=args:raise ValueError('Prosessargumentene er endret.')
                        proc.terminate()
                        proc.wait(timeout=15)
                        log('Tilleggsprogram stoppet: '+status['name']+' • PID '+str(pid))
                    except psutil.NoSuchProcess:pass
                    except psutil.TimeoutExpired:raise ValueError('Programmet avsluttet ikke innen 15 sekunder. Ny prosess startes ikke.')
            if action in ('start','restart'):
                self.ensure([dict(program,enabled=True,on_start=True,required=True)],'start',log,stop_event)
            return self.inspect(program)
