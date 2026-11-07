"""DZSA's public website query, bounded and asynchronous per process launch."""
import copy,ipaddress,json,re,threading,time,urllib.error,urllib.request
from pathlib import Path
from windows_firewall import mask_config

API='https://dayzsalauncher.com/api/v1/query/'

def validate_settings(profile):
    if type(profile.get('dzsa_auto_check',True)) is not bool:raise ValueError('DZSA automatic check must be on/off.')
    value=profile.get('dzsa_public_ip','')
    if not isinstance(value,str):raise ValueError('DZSA public address must be an IPv4 address.')
    if value:
        try:address=ipaddress.IPv4Address(value)
        except ipaddress.AddressValueError:raise ValueError('Enter a public IPv4 address without a port.')
        if not address.is_global or address.is_multicast:raise ValueError('DZSA needs a public IPv4 address, not a local or private address.')

def endpoint(profile):
    validate_settings(profile)
    if not profile.get('dzsa_public_ip'):raise ValueError('Configure the public IPv4 address under Automation → DZSA Launcher.')
    text=(Path(profile['root'])/profile['config']).read_text('utf-8-sig')
    ports=re.findall(r'\bsteamQueryPort\s*=\s*(\d+)\s*;',mask_config(text),re.I)
    if len(ports)!=1 or not 1<=int(ports[0])<=65535:raise ValueError('Set one valid steamQueryPort in the server configuration.')
    return profile['dzsa_public_ip']+':'+str(int(ports[0]))

def submit(target):
    # Same GET and status/result envelope as the official servercheck page.
    request=urllib.request.Request(API+target,headers={'Accept':'application/json','User-Agent':'DZSA-Tools/0.12 (servercheck)'})
    try:
        with urllib.request.urlopen(request,timeout=20) as response:
            data=response.read(1024*1024+1)
    except urllib.error.HTTPError as error:raise ValueError('DZSA returned HTTP '+str(error.code)+'. Use the official page if verification is required.') from error
    if len(data)>1024*1024:raise ValueError('DZSA response exceeded 1 MB.')
    try:result=json.loads(data)
    except (ValueError,UnicodeError):raise ValueError('DZSA returned an unexpected response; no check was confirmed.')
    if not isinstance(result,dict) or type(result.get('status')) is not int:raise ValueError('DZSA returned an unexpected response; no check was confirmed.')
    if result['status']!=0:raise ValueError(str(result.get('error') or 'DZSA rejected the check.')[:400])
    if not isinstance(result.get('result'),dict) or not isinstance(result['result'].get('endpoint'),dict):raise ValueError('DZSA did not confirm a server result.')
    found=result['result']['endpoint']
    if found.get('ip')!=target.split(':')[0] or type(found.get('port')) is not int or not 1<=found['port']<=65535:raise ValueError('DZSA returned an unexpected server endpoint; no check was confirmed.')
    return 'Server found by DZSA. The launcher list can take about 5 minutes to update.'

class LauncherChecks:
    def __init__(self,engine):
        self.engine=engine;self.lock=threading.RLock();self.rows={};self.serial=0
    def status(self,key):
        with self.lock:
            row=self.rows.get(key,{})
            return {k:copy.deepcopy(v) for k,v in row.items() if k in ('state','message','endpoint','attempts','checked')}
    def update(self,p,running,record,health,manual=False):
        key=p['id'];identity=(record.get('pid'),record.get('started_wall'),p.get('dzsa_public_ip',''),p.get('dzsa_auto_check',True),p.get('query_enabled',True));now=time.monotonic()
        with self.lock:
            row=self.rows.get(key)
            if manual and row and row.get('inflight'):raise ValueError('A DZSA check is already in progress.')
            if not row or row['identity']!=identity or manual:
                self.serial+=1;row=dict(identity=identity,token=self.serial,state='waiting',message='Waiting for Steam query readiness.',attempts=0,due=now+(0 if manual else 30),deadline=now+600,inflight=False,manual=manual);self.rows[key]=row
            if not running:
                row.update(state='stopped',message='Server stopped; no DZSA request sent.');return
            if not p.get('query_enabled',True):
                row.update(state='disabled',message='Steam query monitoring is disabled. Enable it for DZSA checks.');return
            if not p.get('dzsa_auto_check',True) and not row['manual']:
                row.update(state='disabled',message='Automatic DZSA check is disabled.');return
            if not p.get('dzsa_public_ip'):
                row.update(state='configure',message='Set the public IPv4 address under Automation → DZSA Launcher.');return
            if row['state'] in ('success','failed','stopped','disabled','configure'):return
            if row['inflight']:return
            if now>row['deadline']:
                row.update(state='failed',message='DZSA check timed out waiting for the server. Check Steam query and try Check now.');return
            if now<row['due'] or not health.get('responding') or health.get('checked',0)<record.get('started_wall',0):return
            try:target=endpoint(p)
            except (ValueError,OSError) as error:row.update(state='failed',message=str(error));return
            row.update(state='checking',message='Asking DZSA to check '+target+'…',endpoint=target,inflight=True,attempts=row['attempts']+1)
            thread=threading.Thread(target=self._send,args=(key,row,target),daemon=True,name='dzsa-servercheck');thread.start()
    def _send(self,key,row,target):
        try:message=submit(target);success=True
        except (ValueError,OSError) as error:message=str(error)[:500];success=False
        # Never attach an old network result to a new/stopped server process.
        with self.engine.manager.lock:
            try:
                p=self.engine.profile(key);record=self.engine.manager.launches.get(key,{})
                current=(record.get('pid'),record.get('started_wall'),p.get('dzsa_public_ip',''),p.get('dzsa_auto_check',True),p.get('query_enabled',True))
                valid=self.engine.manager.running(p) and current==row['identity'] and not self.engine.stop_event.is_set()
            except ValueError:valid=False
            with self.lock:
                if self.rows.get(key) is not row:return
                row['inflight']=False
                if not valid:row.update(state='stopped',message='Check cancelled because the server or settings changed.');return
                row.update(checked=time.time(),message=message,state='success' if success else ('retry' if row['attempts']<3 else 'failed'),due=time.monotonic()+60*row['attempts'])
                if row['state']=='retry':row['message']+=' Retrying after '+str(60*row['attempts'])+' seconds.'
        self.engine.log(p['name']+': DZSA • '+row['message'])
