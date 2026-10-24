"""Local DayZ process manager. No third-party runtime dependencies."""
import json, os, re, shutil, subprocess, threading, time, uuid, zipfile
from pathlib import Path

DEFAULT = dict(name='Taldris • DayZ', root='', steamcmd='', steam_user='', workshop='',
               config='serverDZ.cfg', profiles='profiles', port=2302, mods=[], markers=[],
               map_size=25600, map_image='', auto_update=False, update_minutes=60)

def local_path(root, relative):
    p = (Path(root).resolve() / relative).resolve()
    if not p.is_relative_to(Path(root).resolve()):
        raise ValueError('Stien må være inne i servermappen.')
    return p

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
    for m in p['mods']:validate_mod(m)

def command(p):
    validate(p)
    args=[str(Path(p['root'])/'DayZServer_x64.exe'), '-config='+p['config'], '-port='+str(p['port']),
          '-profiles='+p['profiles'], '-dologs', '-adminlog', '-freezecheck']
    for server, flag in [(False,'-mod='),(True,'-serverMod=')]:
        folders=[str(mod_path(p,m)) if m.get('source')=='local' else m['folder'] for m in p['mods'] if m.get('enabled',True) and mod_load_mode(m) in (('server','both') if server else ('client','both'))]
        if folders: args.append(flag+';'.join(folders))
    return args

class Manager:
    def __init__(self, home, log=lambda s:None):
        self.home=Path(home); self.home.mkdir(parents=True,exist_ok=True)
        self.file=self.home/'settings.json'; self.log=log; self.procs={}; self.busy=set(); self.lock=threading.RLock()
        self.state=json.loads(self.file.read_text('utf-8')) if self.file.exists() else {'servers':[]}
        if not self.state['servers']: self.add()
        for p in self.state['servers']:
            p.setdefault('login_mode','account' if p.get('steam_user') else 'anonymous')
            p.setdefault('mission','dayzOffline.chernarusplus')
            p.setdefault('max_players',40)
        self.save()
    def add(self):
        p=json.loads(json.dumps(DEFAULT)); p.update(login_mode='anonymous',mission='dayzOffline.chernarusplus',max_players=40); p['id']=uuid.uuid4().hex; self.state['servers'].append(p); self.save(); return p
    def save(self):
        tmp=self.file.with_suffix('.tmp'); tmp.write_text(json.dumps(self.state,indent=2,ensure_ascii=False),'utf-8'); tmp.replace(self.file)
    def running(self,p):
        proc=self.procs.get(p['id']); return proc is not None and proc.poll() is None
    def start(self,p):
        with self.lock:
            if p['id'] in self.busy: raise ValueError('En jobb pågår for denne serveren.')
            if self.running(p): raise ValueError('Serveren kjører allerede.')
            for other in self.state['servers']:
                if other['id']==p['id']:continue
                if (self.running(other) or other['id'] in self.busy) and Path(other['root']).resolve()==Path(p['root']).resolve():raise ValueError('En annen aktiv profil bruker samme servermappe.')
                if self.running(other) and int(other['port'])==int(p['port']):raise ValueError('En administrert server bruker allerede denne spillporten.')
            args=command(p)
            if not Path(args[0]).is_file(): raise ValueError('Fant ikke DayZServer_x64.exe. Installer eller velg riktig mappe.')
            if not local_path(p['root'],p['config']).is_file(): raise ValueError('Serverkonfigurasjon mangler.')
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
            # Do not redirect DayZ output: RPT logs are the authoritative source.
            self.procs[p['id']]=subprocess.Popen(args,cwd=p['root'],creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0))
            self.log(p['name']+': prosess startet. Dette bekrefter ikke at serveren er klar for spillere.')
    def force_stop(self,p):
        with self.lock:
            if not self.running(p): raise ValueError('Ingen administrert prosess kjører.')
            self.procs[p['id']].terminate(); self.log('Tvungen stopp sendt. Kontroller RPT før ny oppstart.')
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
        root=Path(p['root']); out=self.home/'backups'/p['id']; out.mkdir(parents=True,exist_ok=True)
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
                            rel=str(f.relative_to(root))
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
            if stage.exists() or old.exists(): raise ValueError('Tidligere staging/previous-mappe finnes. Kontroller den før du fortsetter: '+m['folder'])
            shutil.copytree(src,stage)
            try:
                if dst.exists(): dst.rename(old)
                stage.rename(dst)
            except Exception:
                if old.exists() and not dst.exists(): old.rename(dst)
                raise
            if old.exists(): shutil.rmtree(old)
            keys=root/'keys'; keys.mkdir(exist_ok=True)
            for key in dst.rglob('*.bikey'): shutil.copy2(key, keys/key.name)
            self.log('Installert: '+m['folder'])
