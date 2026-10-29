"""Local DayZ process manager. No third-party runtime dependencies."""
import json, os, re, shutil, subprocess, threading, time, uuid, zipfile
from pathlib import Path
from server_diagnostics import snapshot,current_logs,error_excerpt,exit_label
from windows_runtime import directx_issue
from windows_firewall import ensure_firewall,server_ports
from server_schedule import prepare_messages
from process_registry import save_processes,restore_processes,discover_processes

DEFAULT = dict(name='Taldris • DayZ', root='', steamcmd='', steam_user='', workshop='',
               config='serverDZ.cfg', profiles='profiles', port=2302, mods=[], markers=[],
               map_size=25600, map_image='', auto_firewall=True, query_enabled=True, auto_update=False, update_minutes=60)

def local_path(root, relative):
    p = (Path(root).resolve() / relative).resolve()
    if not p.is_relative_to(Path(root).resolve()):
        raise ValueError('Stien må være inne i servermappen.')
    return p

def reserved_ports(profile):
    config=Path(profile['root'])/profile['config']
    if config.is_file():
        try:
            if profile.get('query_enabled',True):return set(server_ports(profile))
            from windows_firewall import mask_config
            matches=re.findall(r'\bsteamQueryPort\s*=\s*(\d+)\s*;',mask_config(config.read_text('utf-8-sig')),re.I)
            return set(server_ports(profile))|{int(matches[0]) if len(matches)==1 and 1<=int(matches[0])<=65535 else int(profile['port'])+3}
        except ValueError as error:
            if 'mangler' not in str(error):raise
    game=int(profile['port'])
    return {game,game+1,game+2,game+3}


def mod_load_mode(m):
    return m.get('load_mode','server' if m.get('server',False) else 'client')

def mod_path(p,m):
    return Path(m['path']) if m.get('source')=='local' else Path(p['root'])/m['folder']

def validate_mod(m):
    name=m['folder']
    if mod_load_mode(m) not in ('client','server','both'):raise ValueError('Ukjent modlasting. Velg mod, servermod eller begge.')
    if not name.startswith('@') or len(name)<2 or re.search(r'[<>:"/\\|?*;\x00-\x1f]',name) or name.endswith((' ','.')):
        raise ValueError('Modmappe må begynne med @ og ha et gyldig Windows-mappenavn uten semikolon.')
    if m.get('id') and not m['id'].isdigit():raise ValueError('Workshop-ID må være tall.')
    if m.get('source')=='local':
        value=m.get('path','')
        if not Path(value).is_absolute() or any(c in value for c in [';','"','\n','\r','\x00']):raise ValueError('Lokal mod må ha en absolutt sti uten semikolon, anførselstegn eller linjeskift.')
        if m.get('id'):raise ValueError('En lokal utviklermod kan ikke samtidig styres av Workshop.')

def validate(p):
    if not p['root'].strip(): raise ValueError('Velg servermappe først.')
    if not 1024 <= int(p['port']) <= 65533: raise ValueError('Port må være 1024–65533.')
    local_path(p['root'], p['config'])
    local_path(p['root'], p['profiles'])
    if not 1 <= float(p['map_size']) <= 1000000: raise ValueError('Ugyldig kartstørrelse.')
    if int(p['update_minutes']) < 5: raise ValueError('Oppdateringsintervall: minst 5 minutter.')
    from runtime_tools import validate_runtime
    validate_runtime(p)
    from launch_options import validate_extra
    validate_extra(p.get('extra_args',[]))
    for m in p['mods']:validate_mod(m)

def command(p):
    validate(p)
    args=[str(Path(p['root'])/'DayZServer_x64.exe'), '-config='+p['config'], '-port='+str(p['port']),
          '-profiles='+p['profiles'], '-dologs', '-adminlog', '-freezecheck']
    for server, flag in [(False,'-mod='),(True,'-serverMod=')]:
        folders=[str(mod_path(p,m)) if m.get('source')=='local' else m['folder'] for m in p['mods'] if m.get('enabled',True) and mod_load_mode(m) in (('server','both') if server else ('client','both'))]
        if folders: args.append(flag+';'.join(folders))
    args.extend(p.get('extra_args',[]))
    return args

class Manager:
    def __init__(self, home, log=lambda s:None):
        self.home=Path(home); self.home.mkdir(parents=True,exist_ok=True)
        self.file=self.home/'settings.json'; self.log=log; self.procs={}; self.launches={}; self.busy=set(); self.lock=threading.RLock()
        self.state=json.loads(self.file.read_text('utf-8')) if self.file.exists() else {'servers':[]}
        if not self.state['servers']: self.add()
        for p in self.state['servers']:
            p.setdefault('login_mode','account' if p.get('steam_user') else 'anonymous')
            p.setdefault('mission','dayzOffline.chernarusplus')
            p.setdefault('max_players',40)
            p.setdefault('auto_firewall',True)
        self.save()
        restore_processes(self)
        discover_processes(self)
    def add(self):
        p=json.loads(json.dumps(DEFAULT))
        used=set().union(*(reserved_ports(q) for q in self.state['servers'])) if self.state['servers'] else set()
        port=2302
        while port<=65532 and used.intersection(range(port,port+4)):port+=100
        if port>65532:raise ValueError('Fant ingen ledig foreslått portblokk. Endre eksisterende profiler først.')
        p['port']=port
        if self.state['servers']:p['name']='DayZ-server '+str(len(self.state['servers'])+1)
        p.update(login_mode='anonymous',mission='dayzOffline.chernarusplus',max_players=40); p['id']=uuid.uuid4().hex; self.state['servers'].append(p); self.save(); return p
    def save(self):
        with self.lock:
            tmp=self.file.with_suffix('.tmp'); tmp.write_text(json.dumps(self.state,indent=2,ensure_ascii=False),'utf-8'); tmp.replace(self.file)
    def running(self,p):
        proc=self.procs.get(p['id']); return proc is not None and proc.poll() is None
    def start(self,p):
        with self.lock:
            self.poll_processes()
            if p['id'] in self.busy: raise ValueError('En jobb pågår for denne serveren.')
            if self.running(p): raise ValueError('Serveren kjører allerede.')
            shared_mission=False;sharing=[]
            for other in self.state['servers']:
                if other['id']==p['id']:continue
                same_root=Path(other['root']).resolve()==Path(p['root']).resolve()
                if same_root and other['id'] in self.busy:raise ValueError('En annen profil utfører filvedlikehold i samme servermappe. Vent til jobben er ferdig.')
                if self.running(other):
                    overlap=reserved_ports(p)&reserved_ports(other)
                    if overlap:raise ValueError('Portkonflikt med '+other['name']+': UDP '+', '.join(map(str,sorted(overlap)))+'. Velg egne spill- og Steam query-porter.')
                    if same_root:
                        from shared_servers import check_shared
                        shared_mission=check_shared(p,other,self.launches.get(other['id'])) or shared_mission;sharing.append(other['name'])
            args=command(p)
            if not Path(args[0]).is_file(): raise ValueError('Fant ikke DayZServer_x64.exe. Installer eller velg riktig mappe.')
            if not local_path(p['root'],p['config']).is_file(): raise ValueError('Serverkonfigurasjon mangler.')
            runtime_error=directx_issue(p['root'])
            if runtime_error:self.log(runtime_error); raise ValueError(runtime_error)
            for m in p['mods']:
                if not m.get('enabled',True):continue
                path=mod_path(p,m)
                if not path.is_dir():raise ValueError('Mangler modmappe: '+str(path))
                if m.get('source')=='local':
                    from local_mods import inspect_mod
                    info=inspect_mod(path)
                    if not info['ready']:raise ValueError('Ingen pakket PBO i lokal mod: '+str(path)+'. Bygg modden før oppstart.')
                    # Refresh public signing keys at each start, without touching source files.
                    for folder in path.iterdir():
                        if folder.is_dir() and folder.name.casefold()=='keys':
                            for key in folder.iterdir():
                                if key.is_file() and key.suffix.casefold()=='.bikey':
                                    dest=Path(p['root'])/'keys'/key.name; dest.parent.mkdir(exist_ok=True)
                                    if key.resolve()!=dest.resolve():shutil.copy2(key,dest)
            root=Path(p['root']).resolve(); profiles=local_path(root,p['profiles']); profiles.mkdir(parents=True,exist_ok=True)
            # Resolve every path against the intended server directory before creating the process.
            args[0]=str((root/'DayZServer_x64.exe').resolve())
            for i,arg in enumerate(args):
                if arg.startswith('-config='):args[i]='-config='+str(local_path(root,p['config']))
                if arg.startswith('-profiles='):args[i]='-profiles='+str(profiles)
            restart_due=None if shared_mission else prepare_messages(p,self.log)
            if sharing:self.log('Delt servermappe med '+', '.join(sharing)+'. Separate porter, profiles og verdensdata er kontrollert.')
            if not p.get('query_enabled',True):self.log('Lokal test: Steam Query er ikke påkrevd og overvåkes ikke. Koble direkte til 127.0.0.1:'+str(p['port'])+'. Dette sperrer ikke nettverkstilgang.')
            ensure_firewall(p,self.log)
            record=dict(name=p['name'],exe=args[0],cwd=str(root),profiles=str(profiles),args=list(args),restart_due=restart_due,baseline=snapshot(profiles),started=time.monotonic(),started_wall=time.time(),expected_stop=False,state='starting')
            flags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'CREATE_NEW_CONSOLE',0)
            try:proc=subprocess.Popen(args,cwd=str(root),creationflags=flags)
            except OSError as e:
                self.log('Kunne ikke starte '+args[0]+': '+str(e)); raise
            record.update(proc=proc,pid=proc.pid); self.procs[p['id']]=proc; self.launches[p['id']]=record
            save_processes(self)
            self.log('Starter EXE: '+args[0])
            self.log('Argumenter: '+subprocess.list2cmdline(args[1:]))
            self.log(p['name']+': prosess opprettet, PID '+str(proc.pid)+'. Eget servervindu er aktivert på Windows. Følger oppstarten …')
            self.log('Serverlogger: '+str(profiles))
    def force_stop(self,p):
        with self.lock:
            if not self.running(p): raise ValueError('Ingen administrert prosess kjører.')
            if p['id'] in self.launches:self.launches[p['id']]['expected_stop']=True
            save_processes(self)
            self.procs[p['id']].terminate(); self.log('Tvungen stopp sendt. Kontroller RPT før ny oppstart.')
    def poll_processes(self):
        events=[]
        with self.lock:
            for identity,record in self.launches.items():
                if record['state']=='exited':continue
                code=record['proc'].poll()
                if code is None:continue
                label,hint=exit_label(code); uptime=int(time.monotonic()-record['started']); paths=current_logs(record)
                record.update(state='exited',exit_code=int(code),exit_label=label,uptime=uptime,logs=[str(p) for p in paths])
                event=dict(profile_id=identity,pid=record['pid'],code=int(code),uptime=uptime,expected_stop=record['expected_stop'],logs=record['logs']); events.append(event)
                planned=record.get('restart_due') and abs(time.time()-record['restart_due'])<300 and code==0
                if planned:self.log(record['name']+': planlagt, ren avslutning. Vedlikehold venter på driftspanelet.')
                elif record['expected_stop']:self.log(record['name']+': prosessen er avsluttet etter stoppkommando, kode '+label+'.')
                else:
                    self.log(record['name']+': SERVERPROSESSEN AVSLUTTET etter '+str(uptime)+' s. PID '+str(record['pid'])+', kode '+label+'.')
                    if hint:self.log(hint)
                    error_path,excerpt=error_excerpt(paths)
                    if excerpt:self.log('Oppstartsfeil fra '+str(error_path)+':\n'+excerpt)
                    if paths:self.log('Logg fra denne oppstarten: '+str(next((p for p in paths if p.suffix.lower()=='.rpt'),paths[0])))
                    else:self.log('Ingen ny RPT/feillogg ble funnet fra denne oppstarten. Sjekk servervinduet, Windows-hendelsesloggen og at DayZ-serverfilene er komplette.')
        if events:save_processes(self)
        return events
    def job(self,p,fn):
        with self.lock:
            if p['id'] in self.busy or self.running(p): raise ValueError('Stopp serveren før oppdatering eller konsistent backup.')
            root=Path(p['root']).resolve()
            if any((q['id'] in self.busy or self.running(q)) and Path(q['root']).resolve()==root for q in self.state['servers'] if q['id']!=p['id']):
                raise ValueError('En annen profil bruker servermappen.')
            validate(p); self.busy.add(p['id'])
        def run():
            try: fn(p)
            except Exception as e: self.log('FEIL: '+str(e))
            finally:
                with self.lock: self.busy.discard(p['id'])
        threading.Thread(target=run,daemon=True).start()
    def backup(self,p):
        root=Path(p['root']).resolve(); out=self.home/'backups'/p['id']; out.mkdir(parents=True,exist_ok=True)
        dest=out/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.zip')
        sources=[local_path(root,p['config']),local_path(root,p['profiles']),root/'mpmissions',root/'battleye']
        if not any(x.exists() for x in sources): raise ValueError('Ingen serverdata å sikkerhetskopiere.')
        temp=dest.with_suffix('.partial')
        try:
            with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
                seen=set()
                for src in sources:
                    for f in ([src] if src.is_file() else src.rglob('*') if src.exists() else []):
                        if f.is_file() and not f.is_symlink() and f.resolve().is_relative_to(root.resolve()):
                            rel=f.relative_to(root).as_posix()
                            if rel not in seen: z.write(f,rel); seen.add(rel)
            temp.replace(dest)
        finally: temp.unlink(missing_ok=True)
        self.log('Backup fullført: '+str(dest))
    def update(self,p):
        exe=Path(p['steamcmd'])
        if not exe.is_file(): raise ValueError('Velg steamcmd.exe i oppsett.')
        if not p['steam_user'].strip(): raise ValueError('Oppgi Steam-brukernavn. Passord lagres ikke her.')
        if os.name!='nt': raise ValueError('SteamCMD-jobben i denne utgaven krever Windows.')
        args=[str(exe),'+force_install_dir',str(Path(p['root']).resolve()),'+login',p['steam_user'], '+app_update','223350']
        for m in p['mods']:
            if m.get('enabled',True) and m.get('id'): args.extend(['+workshop_download_item','221100',m['id']])
        args+=['+quit']
        self.log('SteamCMD åpnes. Fullfør Steam Guard i konsollvinduet om nødvendig.')
        code=subprocess.Popen(args,creationflags=subprocess.CREATE_NEW_CONSOLE).wait()
        if code: raise ValueError('SteamCMD avsluttet med kode '+str(code))
        self.log('SteamCMD avsluttet. Kontroller resultatet i steamcmd/logs/content_log.txt. Bruk «Installer nedlastede mods» etter vellykket nedlasting.')
    def deploy(self,p):
        base=Path(p['workshop'])
        if not p['workshop'] or not base.is_dir(): raise ValueError('Velg Workshop content/221100-mappen.')
        root=Path(p['root'])
        for m in p['mods']:
            if m.get('source')=='local' or not m.get('enabled',True) or not m.get('id'): continue
            src=base/m['id']; dst=root/m['folder']
            if not src.is_dir() or not (src/'addons').is_dir(): raise ValueError('Ufullstendig Workshop-mod: '+m['id'])
            stage=root/(m['folder']+'.staging'); old=root/(m['folder']+'.previous')
            if stage.exists(): raise ValueError('En staging-mappe finnes. Kontroller den før du fortsetter: '+m['folder'])
            shutil.copytree(src,stage)
            if old.exists():shutil.rmtree(old)
            try:
                if dst.exists(): dst.rename(old)
                stage.rename(dst)
            except Exception:
                if old.exists() and not dst.exists(): old.rename(dst)
                raise
            # Keep one complete previous version for an explicit rollback.
            keys=root/'keys'; keys.mkdir(exist_ok=True)
            for key in dst.rglob('*.bikey'): shutil.copy2(key, keys/key.name)
            self.log('Installert: '+m['folder'])
