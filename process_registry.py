"""Persist identity, never adopt a process based on PID alone."""
import json
import os
from pathlib import Path
import time
import psutil


def identity(proc):
    return dict(pid=proc.pid,created=proc.create_time(),exe=proc.exe(),args=proc.cmdline())


def matches(saved,proc):
    return (abs(proc.create_time()-float(saved['created']))<0.01 and
            os.path.normcase(os.path.abspath(proc.exe()))==os.path.normcase(os.path.abspath(saved['exe'])) and
            proc.cmdline()==saved['args'])


class AttachedProcess:
    def __init__(self,proc):self.proc=proc; self.pid=proc.pid
    def poll(self):
        try:
            if self.proc.is_running() and self.proc.status()!=psutil.STATUS_ZOMBIE:return None
            code=self.proc.wait(timeout=0)
            return code if code is not None else -1
        except psutil.NoSuchProcess:return -1
        except psutil.AccessDenied:return None  # Never mistake inaccessible for stopped.
        except psutil.Error:return -1
    def terminate(self):self.proc.terminate()


def save_processes(manager):
    records={}
    for key,record in manager.launches.items():
        if record['state']=='exited':continue
        try:
            saved=identity(psutil.Process(record['pid']))
            if os.path.normcase(saved['exe'])!=os.path.normcase(record['exe']):continue
            saved.update(name=record['name'],profiles=record['profiles'],cwd=record['cwd'],started_wall=record['started_wall'],restart_due=record.get('restart_due'),expected_stop=record.get('expected_stop',False))
            records[key]=saved
        except (psutil.Error,OSError,TypeError,ValueError):continue
    path=manager.home/'processes.json'; tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(records,indent=2),encoding='utf-8'); tmp.replace(path)


def restore_processes(manager):
    path=manager.home/'processes.json'
    if not path.exists():return
    try:records=json.loads(path.read_text('utf-8'))
    except (ValueError,OSError):manager.log('Prosessregisteret kunne ikke leses. Ingen prosess tas over.'); return
    for profile in manager.state['servers']:
        saved=records.get(profile['id'])
        if not saved:continue
        try:
            proc=psutil.Process(int(saved['pid']))
            if not matches(saved,proc):raise ValueError('Prosessidentiteten stemmer ikke.')
            if Path(saved['exe']).resolve()!=(Path(profile['root'])/'DayZServer_x64.exe').resolve():raise ValueError('Servermappe er endret.')
            attached=AttachedProcess(proc)
            if attached.poll() is not None:continue
            from server_diagnostics import snapshot
            record=dict(saved,proc=attached,baseline=snapshot(saved['profiles']),started=time.monotonic()-max(0,time.time()-saved['started_wall']),state='running')
            manager.procs[profile['id']]=attached; manager.launches[profile['id']]=record
            manager.log(profile['name']+': koblet til eksisterende serverprosess, PID '+str(proc.pid)+'. Serveren er ikke restartet.')
        except (psutil.Error,OSError,ValueError,KeyError,TypeError):manager.log(profile['name']+': tidligere serverprosess kunne ikke bekreftes. Ingen prosess tas over.')


def discover_processes(manager):
    """Migration from older panels: require exact executable/config/profile/port."""
    for profile in manager.state['servers']:
        if profile['id'] in manager.procs or not profile['root']:continue
        root=Path(profile['root']).resolve(); exe=root/'DayZServer_x64.exe'
        expected=['-config='+str((root/profile['config']).resolve()),'-profiles='+str((root/profile['profiles']).resolve()),'-port='+str(profile['port'])]
        candidates=[]
        for proc in psutil.process_iter(['pid','name']):
            try:
                if (proc.info.get('name') or '').casefold()!='dayzserver_x64.exe':continue
                if Path(proc.exe()).resolve()!=exe:continue
                args=proc.cmdline()
                if not all(any(os.path.normcase(a)==os.path.normcase(e) for a in args[1:]) for e in expected):continue
                candidates.append((proc,args))
            except (psutil.Error,OSError):continue
        if len(candidates)!=1:
            if candidates:manager.log(profile['name']+': flere serverprosesser matcher. Automatisk overtakelse avbrytes.')
            continue
        proc,args=candidates[0]
        from server_diagnostics import snapshot
        started=proc.create_time(); profiles=str((root/profile['profiles']).resolve()); attached=AttachedProcess(proc)
        record=dict(name=profile['name'],exe=str(exe),args=args,cwd=str(root),profiles=profiles,pid=proc.pid,proc=attached,baseline=snapshot(profiles),started_wall=started,started=time.monotonic()-max(0,time.time()-started),state='running',expected_stop=False,restart_due=None)
        manager.procs[profile['id']]=attached; manager.launches[profile['id']]=record
        manager.log(profile['name']+': fant og overtok eksisterende DayZ-prosess med bekreftet EXE, konfigurasjon, profiles og port. PID '+str(proc.pid)+'.')
    save_processes(manager)
