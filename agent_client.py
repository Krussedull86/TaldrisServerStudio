"""Desktop facade: one remote engine, stable profile objects and optimistic saves."""
import copy,json,os,subprocess,sys,threading,time
from pathlib import Path
from host_api import AgentClient
from config_documents import digest


def version_key(version,build):
    try:return tuple(map(int,str(version).split('.')))+(int(build),)
    except (ValueError,TypeError):return (0,0,0,0)


def ensure_agent(home):
    from host_security import remember_owner
    home=Path(home);remember_owner(home);client=AgentClient(home)
    try:
        snapshot=client.call('snapshot',timeout=2)
        from release_info import VERSION,BUILD
        if getattr(sys,'frozen',False) and version_key(VERSION,BUILD)>version_key(snapshot.get('version'),snapshot.get('build')):
            try:
                client.call('upgrade',{'exe':sys.executable});time.sleep(1)
                until=time.monotonic()+45
                while time.monotonic()<until:
                    try:
                        fresh=client.call('snapshot',timeout=1)
                        if (fresh.get('version'),fresh.get('build'))==(VERSION,BUILD):return client
                    except (OSError,ValueError):pass
                    time.sleep(.3)
            except ValueError:pass  # An active job can finish on the old agent first.
        return client
    except (OSError,ValueError,KeyError):pass
    args=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).with_name('app.py'))]
    args+=['--agent','--home',str(home)]
    subprocess.Popen(args,cwd=str(home),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0),close_fds=True,env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
    end=time.monotonic()+30
    while time.monotonic()<end:
        try:client.call('snapshot',timeout=1);return client
        except (OSError,ValueError,KeyError):time.sleep(.15)
    raise RuntimeError('Bakgrunnsagenten startet ikke. Se host.log i programdatamappen.')


class RemoteProcess:
    def __init__(self,manager,key):self.manager=manager;self.key=key
    def poll(self):
        entry=self.manager.runtime.get(self.key,{})
        return None if entry.get('running') else entry.get('launch',{}).get('exit_code',-1)
    @property
    def pid(self):return self.manager.runtime.get(self.key,{}).get('pid')


class RemoteManager:
    remote=True
    def __init__(self,home,log=lambda value:None,client=None):
        self.home=Path(home);self.file=self.home/'settings.json';self.log=log;self.client=client or ensure_agent(home);self.state={};self.baseline={};self.runtime={};self.busy=set();self.procs={};self.launches={};self.lock=threading.RLock();self.cursor=0;self.last_poll=0;self.raw={};self.refresh()
    def refresh(self):
        snap=self.client.call('snapshot',{'since':self.cursor});self.raw=snap;self.runtime=snap['runtime'];self.busy={key for key,value in self.runtime.items() if value.get('busy')};self.procs={key:RemoteProcess(self,key) for key in self.runtime};self.launches={key:value['launch'] for key,value in self.runtime.items() if 'launch' in value}
        for key,record in self.launches.items():record['proc']=self.procs[key];record['started']=time.monotonic()-max(0,time.time()-record['started_wall'])
        incoming=snap['state'];existing={p['id']:p for p in self.state.get('servers',[])};baseline={p['id']:p for p in self.baseline.get('servers',[])};profiles=[]
        for new in incoming['servers']:
            current=existing.get(new['id'],{})
            for key,value in new.items():
                if key not in current or current.get(key)==baseline.get(new['id'],{}).get(key):current[key]=copy.deepcopy(value)
            profiles.append(current)
        for key,value in incoming.items():
            if key!='servers' and (key not in self.state or self.state[key]==self.baseline.get(key)):self.state[key]=copy.deepcopy(value)
        self.state['servers']=profiles;self.baseline=copy.deepcopy(incoming)
        for event in snap['events']:self.log(event['text'])
        self.cursor=snap['event_id'];self.last_poll=time.monotonic();return snap
    def save(self):
        from host_engine import EDITABLE
        old={p['id']:p for p in self.baseline.get('servers',[])};changes=[]
        for p in self.state['servers']:
            fields={key:{'before':old.get(p['id'],{}).get(key),'after':value} for key,value in p.items() if key in EDITABLE and value!=old.get(p['id'],{}).get(key)}
            if fields:changes.append({'id':p['id'],'fields':fields})
        if changes:self.client.call('patch',{'changes':changes})
        updates=self.state.get('updates',{})
        if updates!=self.baseline.get('updates',{}):self.client.call('updates',{key:updates[key] for key in ('repository','channel','auto_check') if key in updates})
        self.refresh()
    def add(self):
        result=self.client.call('add');self.refresh();return next(p for p in self.state['servers'] if p['id']==result['id'])
    def import_batch(self,profile,target=None,expected=None):
        result=self.client.call('import_batch',{'profile':profile,'target':target,'expected':expected});self.refresh();return next(p for p in self.state['servers'] if p['id']==result['id'])
    def running(self,p):return self.runtime.get(p['id'],{}).get('running',False)
    def poll_processes(self):
        if time.monotonic()-self.last_poll>1:self.refresh()
        return []
    def enqueue(self,action,p=None,data=None):return self.client.call('enqueue',{'action':action,'server':p['id'] if p else '', 'data':data or {}})
    def start(self,p):return self.enqueue('start',p)
    def force_stop(self,p):return self.enqueue('force_stop',p)
    def job(self,p,fn):return self.enqueue('backup' if fn.__name__=='backup' else 'steam',p,{'kind':'all'})
    def backup(self,p):return self.enqueue('backup',p)
    def deploy(self,p):raise ValueError('Modinstallasjon utføres av bakgrunnsagenten etter SteamCMD.')
    def wait_job(self,job,timeout=30):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            snap=self.client.call('snapshot')
            value=next((j for j in snap['jobs'] if j['id']==job['id']),None)
            if value and value['status']=='completed':return value.get('result')
            if value and value['status']=='failed':raise ValueError(value['error'])
            time.sleep(.1)
        raise TimeoutError('Jobben kjører fortsatt. Kontroller jobbstatus i oversikten.')
    def save_document(self,doc):
        result=self.client.call('document_save',{'server':doc.profile['id'],'file':doc.relative,'base':digest(doc.original),'text':doc.text},timeout=30)
        doc.original=doc.text;return result



from PySide6.QtCore import QObject,Signal,QTimer
class RemoteSteamSession(QObject):
    output=Signal(str);completed=Signal(object);active=Signal(bool);progress=Signal(int);detail=Signal(str)
    def __init__(self,manager,parent=None):
        super().__init__(parent);self.manager=manager;self.job=None;self.profile=None;self.kind='';self.chained=False;self.ids=[];self.previous='';self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(1000)
    def running(self):return self.profile is not None or bool(self.manager.raw.get('steam_profile'))
    def start(self,profile,kind,ids=None,chained=False):
        if self.running():raise ValueError('En SteamCMD-jobb kjører allerede.')
        self.started=time.monotonic();self.job=self.manager.enqueue('steam',profile,dict(kind=kind,ids=ids,chained=chained));self.profile=profile;self.kind=kind;self.chained=chained;self.ids=ids or [];self.active.emit(True);self.progress.emit(-1)
    def send_secret(self,value):self.manager.client.call('input',{'value':value})
    def cancel(self):self.manager.client.call('cancel_steam')
    def poll(self):
        try:snap=self.manager.raw
        except Exception:return
        text=snap.get('console','')
        if text!=self.previous:self.output.emit(text);self.previous=text
        if not self.job:return
        job=next((j for j in snap.get('jobs',[]) if j['id']==self.job['id']),None)
        if not job:
            if time.monotonic()-self.started<10 or self.profile['id'] in self.manager.busy:return
            job={'status':'failed','error':'SteamCMD-jobben finnes ikke lenger i agenten. Kontroller logger etter agentbytte.'}
        self.detail.emit('Bakgrunnsagent: '+job['status'])
        if job['status'] in ('completed','failed'):
            data=dict(profile=self.profile,kind=self.kind,ids=self.ids,chained=self.chained,ok=job['status']=='completed',message=str(job.get('result') or job.get('error','')),output='',agent_managed=True)
            self.job=None;self.profile=None;self.active.emit(False);self.progress.emit(100 if data['ok'] else 0);self.completed.emit(data)
