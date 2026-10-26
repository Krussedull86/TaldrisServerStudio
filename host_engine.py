"""Single-owner headless server engine shared by desktop, service and Discord."""
import copy,json,os,queue,re,shutil,threading,time,uuid,zipfile
from collections import deque
from pathlib import Path
import psutil
from core import Manager,validate,local_path,validate_mod
from config_documents import Document,digest,catalog
from steam_services import steam_arguments,result_summary,details,provision
from steam_status import plain_terminal
from process_registry import save_processes
from rcon_client import server_command

EDITABLE={'name','root','steamcmd','steam_user','login_mode','workshop','config','profiles','port','mods','markers','map_size','map_image','extra_args','auto_firewall','query_enabled','auto_update','update_minutes','mission','max_players','start_after_install','update_game','scheduled_restart','restart_mode','restart_times','restart_interval','maintenance_backup','backup_keep','crash_recovery','rcon_config','local_scan_root','autostart'}


def offline_job(fn):
    def wrapped(self,p,*args,**kwargs):
        if not hasattr(self,'offline_owner'):self.offline_owner=threading.local()
        owned=getattr(self.offline_owner,'keys',set());outer=p['id'] not in owned
        with self.manager.lock:
            if outer:self.editable(p);self.manager.busy.add(p['id']);owned.add(p['id']);self.offline_owner.keys=owned
        try:return fn(self,p,*args,**kwargs)
        finally:
            if outer:
                with self.manager.lock:self.manager.busy.discard(p['id']);owned.discard(p['id'])
    return wrapped


class HostEngine:
    def __init__(self,home,service=False):
        self.home=Path(home);self.home.mkdir(parents=True,exist_ok=True);self.service=service;self.events=deque(maxlen=1000);self.event_id=0;self.event_lock=threading.RLock();self.secrets=[];self.manager=Manager(self.home,self.log)
        self.jobs={};self.queue=queue.Queue();self.stop_event=threading.Event();self.worker=None;self.schedule_thread=None;self.console='';self.pty=None;self.secrets=[];self.steam_profile=None;self.check_due={};self.retries={};self.crashes={};self.health={};self.health_due={};self.metric_procs={};self.rcon_locks={};self.pending_upgrade_exe=None;self.fast_threads=[];self.pending_keys=set();self.pending_lock=threading.Lock();self.discord=None
        for p in self.manager.state['servers']:
            if p['root'] and (Path(p['root'])/'.taldris-restore.json').exists():
                try:
                    if self.manager.running(p):raise ValueError('Serveren kjører. Stopp den før avbrutt gjenoppretting kan repareres.')
                    from restore_transaction import recover
                    recover(p['root']);p.update(maintenance_state='failed',maintenance_error='Avbrutt gjenoppretting er reparert. Kontroller filer før ny oppstart.',desired_running=False);self.log(p['name']+': gjenopprettingsjournal behandlet.')
                except Exception as error:p.update(maintenance_state='failed',maintenance_error=str(error),desired_running=False);self.log(p['name']+': gjenoppretting krever kontroll: '+str(error))
            if self.manager.running(p):p['desired_running']=True
            if p.get('maintenance_state') in ('backup','steam','deploy'):p.update(maintenance_state='failed',maintenance_error='Forrige vedlikehold ble avbrutt. Prøv på nytt.')
        self.manager.save()
    def redact(self,text):
        text=str(text)
        for value in self.secrets:
            if value:text=text.replace(value,'[skjult]')
        text=re.sub(r'(?i)(RConPassword|passwordAdmin|password|token)(\s*[=:]\s*)([^\s;,]+)',r'\1\2[skjult]',text)
        return text
    def log(self,message):
        message=self.redact(message)
        with self.event_lock:
            self.event_id+=1;event=dict(id=self.event_id,time=time.time(),text=message);self.events.append(event)
            with (self.home/'host.log').open('a',encoding='utf-8') as file:file.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+message+'\n')
            if (self.home/'host.log').stat().st_size>5*1024**2:
                old=self.home/'host.previous.log';old.unlink(missing_ok=True);(self.home/'host.log').replace(old)
    def profile(self,key):
        matches=[p for p in self.manager.state['servers'] if p['id']==key or p['name']==key]
        if len(matches)!=1:raise ValueError('Velg en entydig server-ID fra oversikten.')
        return matches[0]
    def editable(self,p):
        if not p.get('root','').strip():raise ValueError('Velg servermappe først.')
        if self.manager.running(p) or (p['id'] in self.manager.busy and p['id'] not in getattr(getattr(self,'offline_owner',None),'keys',set())):raise ValueError('Stopp serveren og vent til jobbene er ferdig.')
        for other in self.manager.state['servers']:
            if other['id']!=p['id'] and (self.manager.running(other) or other['id'] in self.manager.busy) and Path(other['root']).resolve()==Path(p['root']).resolve():raise ValueError('En annen aktiv profil bruker samme mappe.')
    def snapshot(self,since=0):
        with self.manager.lock:
            runtime={}
            for p in self.manager.state['servers']:
                record=self.manager.launches.get(p['id']);running=self.manager.running(p);entry=dict(running=running,busy=p['id'] in self.manager.busy,health=self.health.get(p['id'],{}))
                if record:
                    entry['launch']={k:v for k,v in record.items() if k not in ('proc','baseline')}
                    if entry['health'].get('checked',0)<record['started_wall']:entry['health']={'responding':False}
                    entry.update(pid=record['pid'],uptime=max(0,int(time.time()-record['started_wall'])))
                    if running:
                        try:
                            proc=self.metric_procs.get((record['pid'],record['started_wall']))
                            if proc is None:proc=psutil.Process(record['pid']);self.metric_procs[(record['pid'],record['started_wall'])]=proc
                            entry['ram_mb']=round(proc.memory_info().rss/1024**2);entry['cpu_percent']=round(proc.cpu_percent(None),1);entry['disk_free_gb']=round(shutil.disk_usage(p['root']).free/1024**3,1)
                        except (psutil.Error,OSError):pass
                runtime[p['id']]=entry
            state=copy.deepcopy(self.manager.state)
            with self.event_lock:events=[copy.deepcopy(e) for e in self.events if e['id']>since]
            from release_info import VERSION,BUILD
            return dict(version=VERSION,build=BUILD,state=state,runtime=runtime,events=events,event_id=self.event_id,jobs=[j for j in self.jobs.values() if j['status'] in ('queued','running')]+[j for j in self.jobs.values() if j['status'] not in ('queued','running')][-50:],console=self.redact(plain_terminal(self.console[-100000:])),steam_profile=self.steam_profile,service=self.service)
    def patch_state(self,changes):
        from server_schedule import next_restart
        boolean={'auto_firewall','query_enabled','auto_update','start_after_install','update_game','scheduled_restart','maintenance_backup','crash_recovery','autostart'}
        prepared=[]
        with self.manager.lock:
            for change in changes:
                p=self.profile(change['id']);candidate=copy.deepcopy(p)
                for key,pair in change['fields'].items():
                    if key not in EDITABLE:raise ValueError('Innstillingen kan ikke endres fra panelet: '+key)
                    if p.get(key)!=pair.get('before'):raise ValueError('Oppsettet er endret fra en annen klient. Last inn på nytt.')
                    if key in boolean and not isinstance(pair['after'],bool):raise ValueError(key+' må være av/på.')
                    candidate[key]=pair['after']
                if any(k in {'name','root','steamcmd','steam_user','login_mode','workshop','config','profiles','port','mods','mission','extra_args','auto_firewall','query_enabled'} for k in change['fields']) and (self.manager.running(p) or p['id'] in self.manager.busy):raise ValueError('Stopp serveren før du endrer serveroppsett.')
                if candidate['root']:validate(candidate)
                if candidate.get('restart_mode','clock') not in ('clock','interval'):raise ValueError('Ukjent restartplan.')
                next_restart(candidate)
                if not 1<=int(candidate.get('backup_keep',10))<=100:raise ValueError('Behold 1–100 backuper.')
                prepared.append((p,candidate))
            for p,candidate in prepared:p.update(candidate)
            self.manager.save()
        return True
    def remove_profile(self,key,expected):
        from batch_import import fingerprint
        from core import DEFAULT
        with self.manager.lock,self.pending_lock:
            p=self.profile(key)
            if fingerprint(p)!=expected:raise ValueError('Profilen er endret. Last inn profilen på nytt før sletting.')
            if self.manager.running(p) or key in self.manager.busy or self.steam_profile==key:raise ValueError('Stopp serveren og vent til jobbene er ferdige før profilen slettes.')
            if any(j.get('server')==key and j.get('status') in ('queued','running') for j in self.jobs.values()):raise ValueError('Profilen har jobber i kø eller under kjøring. Vent til de er ferdige.')
            original=self.manager.state;state=dict(original);state['servers']=[q for q in original['servers'] if q['id']!=key]
            if not state['servers']:
                blank=copy.deepcopy(DEFAULT);blank.update(id=uuid.uuid4().hex,name='Ny server',login_mode='anonymous',mission='dayzOffline.chernarusplus',max_players=40);state['servers'].append(blank)
            if 'discord' in state:state['discord']=copy.deepcopy(state['discord']);state['discord'].get('server_roles',{}).pop(key,None)
            self.manager.state=state
            try:self.manager.save()
            except Exception:self.manager.state=original;raise
            for mapping in (self.manager.procs,self.manager.launches,self.check_due,self.retries,self.crashes,self.health,self.health_due,self.rcon_locks):mapping.pop(key,None)
            try:save_processes(self.manager)
            except OSError as error:self.log('Prosessregisteret kunne ikke oppdateres etter profilsletting: '+str(error))
            self.log('Windows-panel: serverprofil slettet • '+p['name']+' • '+key+'. Serverfiler, mods, backup og verdensdata er beholdt.')
            return {'selected':state['servers'][0]['id'],'removed':key}
    def enqueue(self,action,server='',params=None,actor='Windows-panel'):
        with self.manager.lock:return self._enqueue(action,server,params,actor)
    def _enqueue(self,action,server='',params=None,actor='Windows-panel'):

        if self.stop_event.is_set() or getattr(self,'upgrade_pending',False):raise ValueError('Agenten avsluttes eller oppdateres. Prøv igjen om litt.')
        if self.queue.qsize()>50:raise ValueError('Jobbkøen er full.')
        p=self.profile(server) if server else None;key=(action,p['id'] if p else '')
        with self.pending_lock:
            if key in self.pending_keys:raise ValueError('Denne jobben ligger allerede i kø eller kjører.')
            self.pending_keys.add(key)
        job=dict(id=uuid.uuid4().hex,action=action,server=p['id'] if p else '',actor=str(actor),status='queued',created=time.time())
        self.jobs[job['id']]=job
        if action in {'start','force_stop','restart','stop','cancel_restart','players','bans','lock','unlock','say','kick','ban','unban'}:
            thread=threading.Thread(target=self.perform,args=(job,params or {},key),daemon=True);self.fast_threads=[t for t in self.fast_threads if t.is_alive()];self.fast_threads.append(thread);thread.start()
        else:self.queue.put((job,params or {},key))
        return copy.deepcopy(job)
    def start(self):
        from release_info import VERSION,BUILD
        settings=self.manager.state.get('updates',{})
        if settings.get('pending_version')==VERSION and settings.get('pending_build')==BUILD and settings.get('pending_exe') and Path(settings['pending_exe']).is_file():
            from host_security import atomic_private
            path=Path(settings['pending_exe']).resolve()
            if path.is_relative_to((self.home/'program_versions').resolve()):atomic_private(self.home/'active_program.json',{'exe':str(path)})
        self.log('Bakgrunnsagent startet • '+VERSION+' / bygg '+str(BUILD))
        self.worker=threading.Thread(target=self.work,daemon=True);self.worker.start();self.schedule_thread=threading.Thread(target=self.schedule,daemon=True);self.schedule_thread.start()
        for p in self.manager.state['servers']:
            if p.get('desired_running') and p.get('autostart',True) and p.get('maintenance_state')!='failed' and not self.manager.running(p):self.enqueue('start',p['id'],actor='Oppstart med bakgrunnsagent')
    def work(self):
        while not self.stop_event.is_set():
            try:job,params,key=self.queue.get(timeout=.5)
            except queue.Empty:continue
            self.perform(job,params,key);self.queue.task_done()
    def perform(self,job,params,key):
        job['status']='running';self.log(job['actor']+': '+job['action']+' • '+job['server'])
        try:
            result=self.execute(job['action'],job['server'],params)
            raw=json.dumps(result,ensure_ascii=False) if isinstance(result,(dict,list)) else str(result)
            if len(raw.encode())>64000:
                from host_security import protect_file
                folder=self.home/'job_results';folder.mkdir(exist_ok=True);path=folder/(job['id']+'.txt');path.write_text(raw,encoding='utf-8');protect_file(path);result={'artifact':path.name,'size':path.stat().st_size}
            job.update(status='completed',result=result,finished=time.time());self.log('Fullført: '+job['action']+' • '+job['server'])
        except Exception as error:job.update(status='failed',error=self.redact(error),finished=time.time());self.log('FEIL '+job['action']+': '+self.redact(error))
        finally:
            with self.pending_lock:self.pending_keys.discard(key)
            if len(self.jobs)>150:
                for old in list(self.jobs)[:50]:
                    if self.jobs[old]['status'] in ('completed','failed'):
                        self.jobs.pop(old,None);(self.home/'job_results'/(old+'.txt')).unlink(missing_ok=True)
    def rcon(self,p,text):
        with self.rcon_locks.setdefault(p['id'],threading.RLock()):return server_command(p,text)
    def execute(self,action,server,params):
        p=self.profile(server) if server else None
        if action=='start':
            self.retries.pop(p['id'],None);self.manager.start(p);p['desired_running']=True;self.manager.save();return 'Serverprosess startet. Kontroller serverstatus og RPT.'
        if action=='force_stop':
            p['desired_running']=False;p.pop('shutdown_request',None);self.retries.pop(p['id'],None);self.manager.force_stop(p);self.manager.save();return 'Tvungen stopp sendt.'
        if action in ('restart','stop'):
            with self.rcon_locks.setdefault(p['id'],threading.RLock()):
                if not self.manager.running(p):raise ValueError('Serveren kjører ikke.')
                minutes=int(params.get('minutes',10))
                if not 1<=minutes<=1440:raise ValueError('Velg 1–1440 minutter.')
                self.rcon(p,'say -1 Server '+('restart' if action=='restart' else 'shutdown')+' in '+str(minutes)+' minutes. Please find a safe place.')
                p['shutdown_request']=dict(deadline=time.time()+minutes*60,restart=action=='restart',phase='countdown',announced=[minutes]);self.manager.save();return 'Nedtelling startet.'
        if action=='cancel_restart':
            with self.rcon_locks.setdefault(p['id'],threading.RLock()):
                request=p.get('shutdown_request')
                if not request or request['phase']!='countdown':raise ValueError('Ingen nedtelling kan avbrytes.')
                self.rcon(p,'say -1 Scheduled restart/shutdown cancelled.');p.pop('shutdown_request',None);self.manager.save();return 'Nedtelling avbrutt.'
        if action in ('players','bans','lock','unlock','say','kick','ban','unban'):
            text={'players':'players','bans':'bans','lock':'#lock','unlock':'#unlock'}.get(action)
            if action=='say':text='say -1 '+str(params.get('message',''))
            if action in ('kick','ban'):
                player=int(params['player']);reason=str(params.get('reason','Administrator action'))
                if player<0:raise ValueError('Ugyldig spiller-ID.')
                text=action+' '+str(player)+' '+((str(max(0,int(params.get('minutes',0))))+' ') if action=='ban' else '')+reason
            if action=='unban':text='removeBan '+str(max(0,int(params['ban'])))
            result=self.rcon(p,text)
            if action in ('ban','unban'):self.rcon(p,'writeBans')
            return result or 'RCon bekreftet kommandoen.'
        if action=='mods':return [{'index':i,**{key:m.get(key) for key in ('folder','id','title','enabled','load_mode','source','installed_updated','remote_updated')}} for i,m in enumerate(p['mods'])]
        if action=='backups':return [{'archive':f.name,'size_mb':round(f.stat().st_size/1024**2,2),'created':f.stat().st_mtime} for f in sorted((self.home/'backups'/p['id']).glob('*.zip'),reverse=True)]
        if action=='files':return catalog(p)
        if action=='file_history':
            doc=Document(p,params['file'],self.home);version=params.get('version')
            if not version:return sorted(f.name for f in doc.history_dir.glob('*') if f.name!='source.json')
            doc.restore(doc.history_dir/version);return doc.text
        if action=='file_restore':
            self.editable(p);doc=Document(p,params['file'],self.home)
            if digest(doc.original)!=params['base']:raise ValueError('Filen er endret. Hent fersk SHA før gjenoppretting.')
            doc.restore(doc.history_dir/params['version']);doc.save();return 'Konfigurasjonsversjonen er gjenopprettet med backup.'
        if action=='logs':
            if not p.get('root','').strip():raise ValueError('Velg servermappe først.')
            folder=local_path(p['root'],p['profiles']);files=[f for f in folder.glob('*') if f.suffix.casefold() in ('.rpt','.log','.adm') and f.is_file()]
            if not files:raise ValueError('Ingen serverlogger funnet.')
            path=max(files,key=lambda f:f.stat().st_mtime)
            with path.open('rb') as file:file.seek(max(0,path.stat().st_size-16000));return self.redact(file.read().decode('utf-8',errors='replace'))
        if action=='schedule_set':
            allowed={'scheduled_restart','restart_mode','restart_times','restart_interval','auto_update','update_minutes','update_game','crash_recovery','maintenance_backup','backup_keep','autostart'}
            if set(params)-allowed:raise ValueError('Ukjent driftsinnstilling.')
            self.patch_state([{'id':p['id'],'fields':{k:{'before':p.get(k),'after':v} for k,v in params.items()}}]);return 'Driftsoppsettet er lagret. Native restartplaner gjelder fra neste serverstart.'
        if action=='workshop_search':
            from steam_services import search
            return [{'id':i['id'],'title':i['title']} for i in search(str(params.get('query','')),int(params.get('page',1)))][:20]
        if action=='local_mod_scan':
            from local_mods import scan_mods
            return scan_mods(params['root'])
        if action=='local_mod_add':
            self.editable(p);from local_mods import inspect_mod,import_mods
            info=inspect_mod(params['path']);added,skipped=import_mods(p,[info],load_mode=params.get('mode','client'));self.manager.save();return {'added':len(added),'skipped':skipped}
        if action=='mod_collection':
            self.editable(p);from steam_services import collection
            items=collection(params['id']);existing={m.get('id') for m in p['mods']};mode=params.get('mode','client');count=0
            for item in items:
                if item['id'] in existing:continue
                mod=dict(folder='@'+item['id'],id=item['id'],title=item['title'],enabled=True,load_mode=mode,server=mode=='server',remote_updated=item['updated']);validate_mod(mod);p['mods'].append(mod);existing.add(item['id']);count+=1
            self.manager.save();return str(count)+' mods lagt til.'
        if action=='bootstrap':return self.bootstrap(p)
        if action=='create_config':
            self.editable(p);return provision(p,name=p['name'],players=p.get('max_players',40),mission=p.get('mission','dayzOffline.chernarusplus'))
        if action=='backup':return self.backup(p)
        if action=='restore':return self.restore(p,params['archive'])
        if action=='clone':return self.clone(p,params)
        if action=='rollback_mods':return self.rollback_mods(p)
        if action=='maintenance':return self.maintenance(p,bool(params.get('restart',False)))
        if action=='steam':return self.steam(p,params.get('kind','all'),params.get('ids'),bool(params.get('chained',False)))
        if action=='check_mods':return self.check_mods(p)
        if action=='mod_add':
            self.editable(p);from steam_services import workshop_id
            item=details([workshop_id(str(params['id']))])[0]
            if item['file_type']!=0:raise ValueError('Velg en Workshop-mod, ikke en samling.')
            if any(m.get('id')==item['id'] for m in p['mods']):raise ValueError('Modden finnes allerede.')
            mode=params.get('mode','client');mod=dict(folder='@'+item['id'],id=item['id'],title=item['title'],enabled=True,load_mode=mode,server=mode=='server',remote_updated=item['updated']);validate_mod(mod);p['mods'].append(mod);self.manager.save();return item['title']
        if action in ('mod_remove','mod_mode','mod_move'):
            self.editable(p);i=int(params['index']);mod=p['mods'][i]
            if action=='mod_remove':p['mods'].pop(i)
            elif action=='mod_mode':
                candidate=dict(mod,load_mode=params['mode'],server=params['mode']=='server');validate_mod(candidate);mod.update(candidate)
            else:p['mods'].insert(max(0,min(len(p['mods'])-1,int(params['position']))),p['mods'].pop(i))
            self.manager.save();return 'Modlisten er lagret.'
        if action=='document_save':
            from mission_settings import check_config_edit
            check_config_edit(self.manager,p,params['file']);doc=Document(p,params['file'],self.home)
            if digest(doc.original)!=params['base']:raise ValueError('Filen er endret av en annen klient.')
            doc.text=params['text'];warnings=doc.warnings();doc.save();return {'file':doc.relative,'warnings':warnings}
        if action=='list_add':
            self.editable(p);kind=params['list']
            if kind not in ('whitelist.txt','priority.txt','ban.txt'):raise ValueError('Ukjent tilgangsliste.')
            uid=str(params['uid']).strip()
            if not re.fullmatch(r'[A-Za-z0-9+/=_-]{10,80}',uid):raise ValueError('Ugyldig ID. Bruk ID-formatet denne DayZ-listen krever.')
            path=local_path(p['root'],kind);old=path.read_text('utf-8-sig') if path.exists() else ''
            if uid not in re.split(r'[;\s]+',old):
                if path.exists():shutil.copy2(path,path.with_name(path.name+'.'+str(time.time_ns())+'.bak'))
                path.write_text(old.rstrip()+'\n'+uid+'\n',encoding='utf-8')
            return 'Tilgangslisten er lagret.'
        if action=='program_prepare':
            from program_updates import check,download,stage_install
            settings=self.manager.state.setdefault('updates',{});info=check(settings.get('repository','Krussedull86/TaldrisServerStudio'),settings.get('channel','dev'))
            if not info['newer']:return 'Ingen nyere programutgave.'
            exe=stage_install(info,download(info,self.home/'program_updates'),self.home);settings.update(pending_exe=exe,pending_version=info['version'],pending_build=info['build']);self.manager.save()
            if params.get('install',True):self.pending_upgrade_exe=exe
            return 'Programutgaven er klargjort. Agenten installerer den når jobbene er ferdig, uten å stoppe DayZ. Tilkoblede paneler bytter også utgave.'
        raise ValueError('Ukjent handling: '+action)
    @offline_job
    def bootstrap(self,p):
        from steam_services import install_steamcmd
        exe=install_steamcmd(Path(p['steamcmd']).parent,self.log);p['steamcmd']=exe;self.manager.save();return exe
    @offline_job
    def backup(self,p):
        self.manager.backup(p);return 'Backup fullført.'
    def check_mods(self,p):
        ids=[m['id'] for m in p['mods'] if m.get('id') and m.get('enabled',True) and m.get('source')!='local']
        items=details(ids) if ids else [];new=[]
        with self.manager.lock:
            for item in items:
                for mod in p['mods']:
                    if mod.get('id')==item['id']:
                        mod['remote_updated']=item['updated']
                        if not mod.get('installed_updated') or item['updated']>mod['installed_updated']:new.append(item['title'])
            p['mods_pending']=bool(new);self.manager.save()
        return new
    def steam(self,p,kind='all',ids=None,chained=False,backup=True):
        self.editable(p)
        if kind not in ('login','server','mods','all'):raise ValueError('Ukjent SteamCMD-jobb.')
        if os.name!='nt':raise ValueError('SteamCMD-jobber krever Windows.')
        ids=list(dict.fromkeys(ids if ids is not None else [m['id'] for m in p['mods'] if m.get('enabled',True) and m.get('id') and m.get('source')!='local'])) if kind in ('mods','all') else []
        if any(not str(wid).isdigit() for wid in ids):raise ValueError('Ugyldig Workshop-ID.')
        if kind=='mods' and not ids:raise ValueError('Ingen aktive Workshop-mods.')
        if backup and kind!='login' and (Path(p['root'])/p['config']).exists() and p.get('maintenance_backup',True):self.backup(p)
        with self.manager.lock:self.editable(p);self.manager.busy.add(p['id'])
        self.steam_profile=p['id'];self.console=''
        installed_versions={m['id']:m.get('remote_updated',0) for m in p['mods'] if m.get('id')}
        try:
            from winpty import PtyProcess
            exe=Path(p['steamcmd']).resolve()
            if not exe.is_file():raise ValueError('Last ned SteamCMD i Kom i gang først.')
            self.pty=PtyProcess.spawn([str(exe),*steam_arguments(p,kind,ids)],cwd=str(exe.parent),dimensions=(40,180));readq=queue.Queue()
            def reader():
                try:
                    while True:readq.put(self.pty.read(8192))
                except Exception as e:readq.put(None)
            threading.Thread(target=reader,daemon=True).start();last=time.monotonic()
            while True:
                if self.stop_event.is_set():raise ValueError('Agenten avslutter. SteamCMD avbrytes uten modinstallasjon.')
                try:chunk=readq.get(timeout=.5)
                except queue.Empty:
                    if time.monotonic()-last>900:raise TimeoutError('SteamCMD ventet 15 minutter uten utdata. Kontroller innlogging og Steam Guard.')
                    continue
                if chunk is None:break
                if chunk:self.console=(self.console+chunk)[-1000000:];last=time.monotonic()
            until=time.monotonic()+3
            while self.pty.exitstatus is None and time.monotonic()<until:time.sleep(.05)
            code=self.pty.exitstatus if self.pty.exitstatus is not None else 1
            ok,message=result_summary(self.console,kind,ids,code,(Path(p['root'])/'DayZServer_x64.exe').is_file())
            if not ok:raise ValueError(message)
            self.log(message)
            if ids:
                bases=[]
                for match in re.finditer(r'Success\.\s*Downloaded item\s+(\d+)\s+to\s+"([^"]+)"',plain_terminal(self.console),re.I):
                    if match.group(1) in ids:bases.append(Path(match.group(2)).parent)
                bases.extend([exe.parent/'steamapps/workshop/content/221100',Path(p['root'])/'steamapps/workshop/content/221100',Path(p.get('workshop',''))])
                base=next((b for b in bases if all((b/wid/'addons').is_dir() for wid in ids)),None)
                if base is None:raise ValueError('SteamCMD bekreftet nedlasting, men komplette modmapper ble ikke funnet.')
                p['workshop']=str(base);self.manager.deploy(p)
                for mod in p['mods']:
                    if mod.get('id') in ids:mod.update(installed_at=time.time(),installed_updated=installed_versions.get(mod['id'],0))
            if chained and not local_path(p['root'],p['config']).exists():provision(p,name=p.get('name','DayZ'),players=p.get('max_players',40),mission=p.get('mission','dayzOffline.chernarusplus'))
            p['mods_pending']=False;self.manager.save();return message
        finally:
            if self.pty:
                try:self.pty.close(force=True)
                except Exception:pass
            self.pty=None;self.steam_profile=None;self.manager.busy.discard(p['id'])
    def steam_input(self,value):
        if not self.pty:raise ValueError('Ingen SteamCMD-økt venter på input.')
        if any(c in value for c in '\r\n\x00'):raise ValueError('Send én linje om gangen.')
        self.secrets.append(value);self.pty.write(value+'\r\n')
    def maintenance(self,p,restart):
        with self.manager.lock:
            shared=any(q['id']!=p['id'] and self.manager.running(q) and Path(q['root']).resolve()==Path(p['root']).resolve() for q in self.manager.state['servers'])
            if shared:
                if self.manager.running(p) or p['id'] in self.manager.busy:raise ValueError('Stopp denne serveren før vedlikehold.')
                if restart:self.manager.start(p)
                p.update(maintenance_state='idle',maintenance_deferred=True);self.manager.save();self.log(p['name']+': backup og filoppdateringer er utsatt fordi en annen server bruker samme mappe. Andre servere stoppes ikke.');return 'Filvedlikehold utsatt; serveren er startet igjen.' if restart else 'Filvedlikehold utsatt til de andre serverne er stoppet.'
        self.editable(p);p['maintenance_deferred']=False;p.update(maintenance_state='backup',maintenance_error='');self.manager.save()
        try:
            if p.get('maintenance_backup',True):
                self.backup(p);files=sorted((self.home/'backups'/p['id']).glob('*.zip'),key=lambda f:f.stat().st_mtime)
                automatic=p.setdefault('automatic_backups',[])
                if files:automatic.append(str(files[-1]))
                while len(automatic)>int(p.get('backup_keep',10)):
                    old=Path(automatic.pop(0))
                    if old.parent.resolve()==(self.home/'backups'/p['id']).resolve():old.unlink(missing_ok=True)
            if p.get('auto_update'):
                kind='all' if p.get('update_game',True) else 'mods'
                if kind=='all' or any(m.get('id') and m.get('enabled',True) for m in p['mods']):p['maintenance_state']='steam';self.steam(p,kind,backup=False)
            p.update(maintenance_state='idle',mods_pending=False);self.manager.save()
            if restart:self.manager.start(p)
            return 'Vedlikehold fullført.'
        except Exception as error:p.update(maintenance_state='failed',maintenance_error=self.redact(error));self.manager.save();raise
    @offline_job
    def rollback_mods(self,p):
        self.editable(p);self.backup(p);count=0
        for mod in p['mods']:
            if mod.get('source')=='local' or not mod.get('id'):continue
            dest=local_path(p['root'],mod['folder']);old=dest.with_name(dest.name+'.previous');temp=dest.with_name(dest.name+'.rollback')
            if not old.is_dir():continue
            if temp.exists():raise ValueError('En tidligere rollback må kontrolleres: '+str(temp))
            dest.rename(temp)
            try:old.rename(dest);temp.rename(old)
            except Exception:
                if temp.exists() and not dest.exists():temp.rename(dest)
                raise
            for key in dest.rglob('*.bikey'):
                keys=Path(p['root'])/'keys';keys.mkdir(exist_ok=True);shutil.copy2(key,keys/key.name)
            mod['installed_updated']=0;count+=1
        self.manager.save();return str(count)+' mods byttet med forrige installasjon.'
    @offline_job
    def restore(self,p,archive):
        self.editable(p);folder=(self.home/'backups'/p['id']).resolve();source=(folder/str(archive)).resolve()
        if source.parent!=folder or source.suffix!='.zip':raise ValueError('Velg et backup-arkiv for denne serveren.')
        root=Path(p['root']).resolve();stage=root/('.taldris-restore-'+uuid.uuid4().hex);moved=[]
        from restore_transaction import write_journal,recover
        if (root/'.taldris-restore.json').exists():raise ValueError('En avbrutt gjenoppretting må repareres før du fortsetter.')
        stage.mkdir();journal={'stage':stage.name,'entries':[],'committed':False}
        try:
            with zipfile.ZipFile(source) as z:
                if sum(i.file_size for i in z.infolist())>min(50*1024**3,shutil.disk_usage(root).free):raise ValueError('Ikke nok plass til full gjenoppretting.')
                allowed=[local_path(root,value).relative_to(root).as_posix() for value in [p['config'],p['profiles'],'mpmissions','battleye']]
                if '.' in allowed:raise ValueError('Profiles kan ikke være hele serverroten ved gjenoppretting.')
                for item in z.infolist():
                    name=item.filename.replace('\\','/')
                    if name.startswith('/') or '..' in Path(name).parts or ':' in name or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Utrygt backup-innhold.')
                    if not any(name.casefold()==a.casefold() or name.casefold().startswith(a.casefold().rstrip('/')+'/') for a in allowed):raise ValueError('Arkivet har uventede filer: '+name)
                    target=local_path(stage,name)
                    if item.is_dir():target.mkdir(parents=True,exist_ok=True)
                    else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(item))
            self.backup(p)
            # Whole directory swaps prevent old persistence files surviving a restore.
            paths=sorted(allowed,key=lambda value:len(Path(value).parts));handled=[]
            for relative in paths:
                if any(Path(relative).is_relative_to(Path(parent)) for parent in handled):continue
                staged=local_path(stage,relative)
                if not staged.exists():continue
                dest=local_path(root,relative);old=dest.with_name(dest.name+'.restore-'+uuid.uuid4().hex[:8]);dest.parent.mkdir(parents=True,exist_ok=True)
                existed=dest.exists()
                entry={'file':dest.relative_to(root).as_posix(),'old':old.relative_to(root).as_posix(),'existed':existed,'done':False};journal['entries'].append(entry);write_journal(root,journal)
                if existed:dest.rename(old)
                moved.append((dest,old,existed));staged.rename(dest);entry['done']=True;write_journal(root,journal);handled.append(relative)
            journal['committed']=True;write_journal(root,journal)
            try:recover(root)
            except OSError as error:self.log('Gjenoppretting er fullført; gamle mapper ryddes ved neste agentstart: '+str(error))
            return 'Backup gjenopprettet. Serveren er fortsatt stoppet.'
        except Exception:
            if (root/'.taldris-restore.json').exists():recover(root)
            raise
        finally:shutil.rmtree(stage,ignore_errors=True)
    @offline_job
    def clone(self,p,params):
        self.editable(p);target=Path(params['root']).resolve();source=Path(p['root']).resolve()
        if target.exists() or target.is_relative_to(source) or source.is_relative_to(target):raise ValueError('Velg en ny, separat mappe som ikke finnes.')
        q=self.manager.add();port=q['port'];key=q['id'];q.update(copy.deepcopy(p));q.update(id=key,name=params.get('name',p['name']+' test'),root=str(target),port=port,scheduled_restart=False,auto_update=False,crash_recovery=False,desired_running=False,maintenance_state='idle')
        q.pop('shutdown_request',None);q['automatic_backups']=[];self.manager.busy.add(q['id'])
        try:
            shutil.copytree(source,target,symlinks=False,ignore=lambda directory,names:set(shutil.ignore_patterns('storage_*','steamapps','*.RPT','*.mdmp','*.log','*.previous','*.staging','*.rollback','*.taldris.tmp')(directory,names))|{name for name in names if (Path(directory)/name).is_symlink()})
            from windows_firewall import set_query_port
            cfg=local_path(target,q['config']);cfg.write_text(set_query_port(cfg.read_text('utf-8-sig'),port+3),encoding='utf-8');q['rcon_config']=''
            import secrets
            password=secrets.token_urlsafe(24)
            for file in target.rglob('*.cfg'):
                if file.name.casefold().startswith('beserver'):
                    text=file.read_text('utf-8-sig');text=re.sub(r'(?im)^RConPort\s+.*$', 'RConPort '+str(port+4),text);text=re.sub(r'(?im)^RConPassword\s+.*$', 'RConPassword '+password,text);file.write_text(text,encoding='utf-8')
                    if not q['rcon_config']:q['rcon_config']=file.relative_to(target).as_posix()
            self.manager.save();return {'id':q['id'],'name':q['name'],'root':str(target),'port':port}
        except Exception:self.manager.state['servers'].remove(q);self.manager.save();raise
        finally:self.manager.busy.discard(q['id'])
    def schedule(self):
        while not self.stop_event.wait(2):
            try:self.tick()
            except Exception as error:self.log('Driftskontroll: '+str(error))
    def tick(self):
        if self.pending_upgrade_exe and not self.manager.busy and not any(j['status'] in ('queued','running') for j in self.jobs.values()) and hasattr(self,'api'):
            self.api.call('upgrade',{'exe':self.pending_upgrade_exe});self.pending_upgrade_exe=None;return
        if getattr(self,'upgrade_pending',False):return
        now=time.time();events=self.manager.poll_processes()
        for event in events:
            p=self.profile(event['profile_id']);record=self.manager.launches[p['id']];request=p.get('shutdown_request');due=record.get('restart_due')
            planned=bool(due and abs(now-due)<300 and event['code']==0 and not event['expected_stop'])
            requested=bool(request and request['phase']=='stopping')
            if planned or requested:
                restart=planned or request['restart'];p.pop('shutdown_request',None);p['desired_running']=restart;self.manager.save()
                if restart:self.enqueue('maintenance',p['id'],{'restart':True},'Restartplan')
            elif p.get('crash_recovery') and not event['expected_stop']:
                history=self.crashes.setdefault(p['id'],deque())
                while history and now-history[0]>900:history.popleft()
                if len(history)<3:history.append(now);self.retries[p['id']]=now+30;self.log(p['name']+': krasjgjenstart om 30 sekunder.')
                else:self.log(p['name']+': krasjgjenstart blokkert etter 3 forsøk på 15 minutter.')
        for p in self.manager.state['servers']:
            key=p['id'];running=self.manager.running(p);request=p.get('shutdown_request')
            if not p.get('query_enabled',True):self.health[key]={'responding':False,'disabled':True,'checked':now}
            elif running and now>=self.health_due.get(key,0):
                self.health_due[key]=now+15
                from server_health import query
                try:
                    previous=self.health.get(key,{}).get('responding');self.health[key]=query(p)
                    if not previous:self.log(p['name']+': Steam query svarer. Kart '+self.health[key]['map']+'.')
                except (OSError,ValueError):self.health[key]={'responding':False,'checked':now}
            elif not running:self.health[key]={'responding':False,'checked':now}
            with self.rcon_locks.setdefault(p['id'],threading.RLock()):
                request=p.get('shutdown_request')
                if request and running:
                    if request['phase']=='countdown':
                        remaining=max(0,int((request['deadline']-now+59)//60))
                        if now>=request['deadline']:
                            self.manager.launches[key]['expected_stop']=True;request.update(phase='stopping',sent=now);save_processes(self.manager);self.manager.save()
                            try:self.rcon(p,'#shutdown');self.log(p['name']+': ordentlig avslutning sendt via RCon.')
                            except (OSError,ValueError) as error:self.log(p['name']+': avslutning er forespurt, men RCon-svaret er ubekreftet. Følger prosessen: '+str(error))
                        elif remaining in (30,15,10,5,2,1) and remaining not in request['announced']:
                            self.rcon(p,'say -1 Server maintenance in '+str(remaining)+' minutes.');request['announced'].append(remaining)
                    elif request['phase']=='stopping' and now-request['sent']>180:
                        self.log(p['name']+': serveren avsluttet ikke etter RCon-kommandoen. Ingen automatisk tvungen stopp.');request.update(phase='failed');self.manager.launches[key]['expected_stop']=False;self.manager.save()
            if key in self.retries and now>=self.retries[key] and not running and key not in self.manager.busy:
                self.retries.pop(key);self.enqueue('start',key,actor='Krasjgjenstart')
            if p.get('auto_update') and key not in self.manager.busy and now>=self.check_due.get(key,0):
                self.check_due[key]=now+max(5,int(p['update_minutes']))*60
                if running:self.enqueue('check_mods',key,actor='Automatisk Workshop-sjekk')
                elif p.get('maintenance_state','idle')=='idle':self.enqueue('maintenance',key,{'restart':False},'Automatisk vedlikehold')
    def stop(self):
        self.stop_event.set()
        if self.pty:
            try:self.pty.terminate(force=True)
            except Exception:pass
        if self.worker:
            while self.worker.is_alive():self.worker.join(timeout=1)
        for thread in self.fast_threads:
            while thread.is_alive():thread.join(timeout=1)
        save_processes(self.manager);self.manager.save()
        if self.discord:self.discord.stop()
