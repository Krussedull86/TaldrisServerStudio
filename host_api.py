"""Authenticated loopback-only API. One engine owns the installation."""
import hmac,json,secrets,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request,urlopen,ProxyHandler,build_opener
from urllib.error import HTTPError
from host_security import AgentLock,atomic_private,load_secrets,store_secrets
from config_documents import Document,catalog


class AgentAPI:
    def __init__(self,engine):
        self.engine=engine;engine.api=self;self.token=secrets.token_urlsafe(48);outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                try:
                    if self.client_address[0]!='127.0.0.1' or self.headers.get('Origin') or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+outer.token):self.reply(403,{'error':'Ingen tilgang.'});return
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=12*1024**2:self.reply(413,{'error':'Ugyldig forespørselsstørrelse.'});return
                    data=json.loads(self.rfile.read(size));result=outer.call(data['method'],data.get('params',{}));self.reply(200,{'result':result})
                except Exception as error:self.reply(400,{'error':outer.engine.redact(error)})
            def reply(self,code,data):
                raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True
    def start(self):
        import os,psutil
        try:created=psutil.Process().create_time()
        except psutil.NoSuchProcess:created=time.time()
        atomic_private(self.engine.home/'agent.json',dict(port=self.server.server_port,token=self.token,pid=os.getpid(),created=created))
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
    def stop(self):self.server.shutdown();self.server.server_close()
    def call(self,method,params):
        e=self.engine
        if method=='snapshot':return e.snapshot(int(params.get('since',0)))
        if method=='enqueue':return e.enqueue(params['action'],params.get('server',''),params.get('data'),params.get('actor','Windows-panel'))
        if method=='patch':return e.patch_state(params['changes'])
        if method=='add':
            with e.manager.lock:return e.manager.add()
        if method=='mission_save':
            from mission_settings import save_mission
            result=save_mission(e.manager,e.profile(params['server']),params['mission'],params['base']);e.log('Windows-panel: kartvalg lagret • '+params['mission']);return result
        if method=='import_batch':
            from batch_import import apply_profile
            result=apply_profile(e.manager,params['profile'],params.get('target'),params.get('expected'));e.log('Windows-panel: BAT-profil importert • '+result['name']);return result
        if method=='updates':
            with e.manager.lock:
                settings=e.manager.state.setdefault('updates',{})
                for key in ('repository','channel','auto_check'):
                    if key in params:settings[key]=params[key]
                from program_updates import repository
                if settings.get('repository'):settings['repository']=repository(settings['repository'])
                if settings.get('channel','dev') not in ('dev','stable'):raise ValueError('Ukjent kanal.')
                e.manager.save();return settings
        if method=='input':e.steam_input(str(params['value']));return True
        if method=='cancel_steam':
            if e.pty:e.pty.terminate(force=True)
            return True
        if method=='upgrade':
            import os,subprocess,sys,psutil
            if e.manager.busy or any(j['status']=='running' for j in e.jobs.values()):raise ValueError('Agentoppdatering venter til jobbene er ferdig.')
            if getattr(e,'upgrade_pending',False):return True
            source=Path(params['exe']).resolve()
            if source.suffix.casefold()!='.exe' or not source.is_file() or source.open('rb').read(2)!=b'MZ':raise ValueError('Ugyldig agentprogram.')
            me=psutil.Process();args=[str(source),'--home',str(e.home)]
            if e.service:args+=['--upgrade-service']
            else:args+=['--agent','--wait-agent',str(me.pid),str(me.create_time())]
            subprocess.Popen(args,cwd=str(source.parent),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0),close_fds=True,env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
            e.upgrade_pending=True
            if not e.service:threading.Timer(.5,e.stop_event.set).start()
            return True
        if method=='document_save':
            with e.manager.lock:
                result=e.execute('document_save',params['server'],params);e.log('Windows-panel: konfigurasjon lagret • '+params['file']);return result
        if method=='catalog':return catalog(e.profile(params['server']))
        if method=='document':
            doc=Document(e.profile(params['server']),params['file'],e.home);return {'text':doc.text,'relative':doc.relative}
        if method=='discord_settings':
            settings=e.manager.state.setdefault('discord',{})
            if params:
                candidate=dict(settings,**{k:v for k,v in params.items() if k!='token'})
                if candidate.get('enabled'):
                    for key in ('guild_id','channel_id'):
                        if not str(candidate.get(key,'')).isdigit():raise ValueError('Discord '+key+' må være en numerisk ID.')
                    if not isinstance(candidate.get('owners'),list) or not candidate['owners'] or any(not str(x).isdigit() for x in candidate['owners']):raise ValueError('Legg inn minst én gyldig eier-ID.')
                    permissions=[candidate.get('roles',{}),*candidate.get('server_roles',{}).values()]
                    for roles in permissions:
                        if not isinstance(roles,dict):raise ValueError('Roller må være et JSON-objekt.')
                        for scope,ids in roles.items():
                            if scope not in ('read','control','moderate','maintenance','config') or not isinstance(ids,list) or any(not str(x).isdigit() for x in ids):raise ValueError('Ugyldig rettighet eller rolle-ID-liste.')
                for key in ('enabled','guild_id','channel_id','owners','roles','server_roles'):
                    if key in params:settings[key]=params[key]
                if settings.get('enabled') and (not str(settings.get('guild_id','')).isdigit() or not settings.get('owners')):raise ValueError('Discord krever server-ID og minst én eier-ID.')
                if params.get('token'):
                    secrets_data=load_secrets(e.home);secrets_data['discord_token']=params['token'];store_secrets(e.home,secrets_data)
                e.manager.save()
                if e.discord:e.discord.stop()
                from discord_host import DiscordHost
                e.discord=DiscordHost(e);e.discord.start()
            return dict(settings,has_token=bool(load_secrets(e.home).get('discord_token')))
        if method=='shutdown':
            if e.manager.busy or any(j['status']=='running' for j in e.jobs.values()):raise ValueError('Vent til jobben er ferdig før agenten byttes.')
            e.stop_event.set();return True
        raise ValueError('Ukjent API-metode.')


class AgentClient:
    def __init__(self,home):self.home=Path(home);self.opener=build_opener(ProxyHandler({}))
    def call(self,method,params=None,timeout=15):
        info=json.loads((self.home/'agent.json').read_text('utf-8'))
        port=int(info['port'])
        if not 1<=port<=65535:raise ValueError('Ugyldig agentport.')
        raw=json.dumps({'method':method,'params':params or {}}).encode()
        request=Request('http://127.0.0.1:'+str(port)+'/',data=raw,headers={'Authorization':'Bearer '+info['token'],'Content-Type':'application/json'})
        try:
            with self.opener.open(request,timeout=timeout) as response:data=json.load(response)
        except HTTPError as error:
            try:data=json.load(error)
            except ValueError:raise ValueError('Bakgrunnsagenten avviste forespørselen.')
        if 'error' in data:raise ValueError(data['error'])
        return data['result']


def serve(home,service=False,external_stop=None):
    lock=AgentLock(home);lock.acquire()
    from host_engine import HostEngine
    engine=HostEngine(home,service);api=AgentAPI(engine);api.start();engine.start()
    try:
        from discord_host import DiscordHost
        engine.discord=DiscordHost(engine);engine.discord.start()
        while not engine.stop_event.wait(.5):
            if external_stop and external_stop.is_set():break
    finally:engine.stop();api.stop();lock.close()
