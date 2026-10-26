"""Read a small, explicit subset of CMD syntax. Never execute a batch file."""
import copy,hashlib,json,ntpath,posixpath,re,uuid
from pathlib import Path
from launch_options import FLAGS,VALUES,BASE,validate_extra
LIMIT=1024*1024

def tokenize(text):
    """Windows argv quoting, retaining whether a token begins with a quote (START title)."""
    result=[];i=0
    while i<len(text):
        while i<len(text) and text[i].isspace():i+=1
        if i==len(text):break
        quoted=text[i]=='"';value='';inside=False
        while i<len(text) and (inside or not text[i].isspace()):
            if text[i]=='\\':
                start=i
                while i<len(text) and text[i]=='\\':i+=1
                count=i-start
                if i<len(text) and text[i]=='"':
                    value+='\\'*(count//2)
                    if count%2:value+='"'
                    else:inside=not inside
                    i+=1
                else:value+='\\'*count
            elif text[i]=='"':inside=not inside;i+=1
            else:value+=text[i];i+=1
        if inside:raise ValueError('Uavsluttet anførselstegn i BAT-linjen.')
        result.append((value,quoted))
    return result

def path_module(path):return ntpath if re.match(r'^[A-Za-z]:',str(path)) or '\\' in str(path) else posixpath

def absolute(value,cwd):
    pm=path_module(cwd)
    if not value or re.search(r'%[^%]+%|![^!]+!',value):return value
    if pm is ntpath:
        if value.startswith('\\') and not value.startswith('\\\\'):value=ntpath.splitdrive(cwd)[0]+value
        if re.match(r'^[A-Za-z]:[^\\/]',value):raise ValueError('Diskrelativ sti kan ikke avgjøres: '+value)
    return pm.normpath(value if pm.isabs(value) else pm.join(cwd,value))

def has_shell(text):
    quoted=False
    for c in text:
        if c=='"':quoted=not quoted
        elif not quoted and c in '&|<>':return True
    return False

def read_batch(path):
    path=Path(path)
    if path.suffix.casefold() not in ('.bat','.cmd'):raise ValueError('Velg en .bat- eller .cmd-fil.')
    with path.open('rb') as f:raw=f.read(LIMIT+1)
    if len(raw)>LIMIT:raise ValueError('BAT-filen er større enn 1 MB.')
    if raw.startswith((b'\xff\xfe',b'\xfe\xff')):text=raw.decode('utf-16')
    else:
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:text=raw.decode('cp1252')
    return parse_batch(text,str(path.resolve()))

def parse_batch(text,source):
    if len(text.encode('utf-8'))>LIMIT:raise ValueError('BAT-filen er for stor.')
    pm=path_module(source);base=pm.dirname(source);cwd=base;variables={};warnings=[];candidates=[];blocked=0
    if len(text.splitlines())>10000:raise ValueError('BAT-filen har mer enn 10 000 linjer.')
    lines=[];pending='';first=0
    for number,line in enumerate(text.splitlines(),1):
        if not pending:first=number
        tail=len(line)-len(line.rstrip('^'))
        if tail%2:pending+=line[:-1]+' ';continue
        lines.append((first,pending+line));pending=''
    if pending:warnings.append('Siste linje har ufullstendig ^-fortsettelse.')
    def expand(value):
        value=re.sub(r'%~dp0',lambda m:base+pm.sep,value,flags=re.I)
        value=re.sub(r'%([^%]+)%',lambda m:cwd if m[1].casefold()=='cd' else variables.get(m[1].casefold(),m[0]),value)
        if len(value)>32768:raise ValueError('Variabelutvidelsen i BAT-filen er for stor.')
        return value
    for number,raw in lines:
        line=raw.strip().lstrip('@').strip()
        if not line or line.startswith(('::',':')) or re.match(r'rem(?:\s|$)',line,re.I):continue
        if blocked:
            blocked+=line.count('(')-line.count(')');blocked=max(blocked,0);continue
        if re.match(r'(if|for|else)\b',line,re.I) or line=='(':
            warnings.append(f'Linje {number}: betingelse/løkke ble ikke tolket.');blocked=max(0,line.count('(')-line.count(')'));continue
        if has_shell(line):warnings.append(f'Linje {number}: sammensatt kommando/omdirigering ble ikke tolket.');continue
        m=re.match(r'set\s+(.*)',line,re.I)
        if m:
            value=m[1]
            if value.startswith('"') and value.endswith('"'):value=value[1:-1]
            if value.startswith('/') or '=' not in value:warnings.append(f'Linje {number}: dynamisk SET støttes ikke.');continue
            key,value=value.split('=',1);variables[key.casefold()]=expand(value);continue
        if re.match(r'(goto|timeout|taskkill|choice)\b',line,re.I):
            warnings.append(f'Linje {number}: stopp/restart/tidsstyring ble ikke overtatt. Bruk Automatisering i programmet.');continue
        line=expand(line)
        m=re.match(r'(?:cd|chdir)\s+(?:/d\s+)?(.+)',line,re.I)
        if m:
            cwd=absolute(m[1].strip().strip('"'),cwd);continue
        try:tokens=tokenize(line)
        except ValueError as error:warnings.append(f'Linje {number}: {error}');continue
        if not tokens:continue
        title='';working=cwd
        if tokens[0][0].casefold()=='start':
            tokens=tokens[1:];had_title=False
            while tokens:
                value,quoted=tokens[0]
                if quoted and not had_title:title=value;had_title=True;tokens=tokens[1:];continue
                if value.casefold()=='/d' and len(tokens)>1:working=absolute(tokens[1][0],cwd);tokens=tokens[2:];continue
                if value.casefold() in {'/wait','/b','/min','/max','/normal','/high','/low','/realtime','/belownormal','/abovenormal'}:tokens=tokens[1:];continue
                break
        elif tokens[0][0].casefold()=='call':tokens=tokens[1:]
        if not tokens or pm.basename(tokens[0][0]).casefold()!='dayzserver_x64.exe':
            if re.match(r'(call|cmd|powershell|pushd|popd)\b',line,re.I) or 'dayzserver_x64.exe' in line.casefold():warnings.append(f'Linje {number}: eksternt skript eller arbeidsmappekommando ble ikke tolket.')
            continue
        exe=absolute(tokens[0][0],working);root=pm.dirname(exe);notes=[];options={};extra=[];mods={}
        for value,_ in tokens[1:]:
            match=re.fullmatch(r'-([A-Za-z]+)(?:=(.*))?',value)
            if not match:notes.append('Ukjent argument: '+value);continue
            key,val=match[1].casefold(),match[2]
            if key in ('config','profiles','port'):
                if key in options:notes.append('Gjentatt valg, siste verdi brukes: '+key)
                options[key]=val or ''
            elif key in ('mod','servermod','servermods'):
                for entry in (val or '').split(';'):
                    if not entry.strip():continue
                    path=absolute(entry.strip(),working);identity=pm.normcase(path);mode='client' if key=='mod' else 'server'
                    if identity in mods:mods[identity]['load_mode']='both' if mods[identity]['load_mode']!=mode else mode
                    else:mods[identity]=dict(folder=pm.basename(path.rstrip('\\/')),id='',path=path,source='local',enabled=True,load_mode=mode)
            elif key in BASE and val is None:pass
            elif key in FLAGS|VALUES:
                try:validate_extra([value]);extra=[a for a in extra if a.split('=')[0].casefold()!=('-'+key)];extra.append(value)
                except ValueError:notes.append('Startvalg må korrigeres: '+value)
            else:notes.append('Ikke importert startvalg: '+value)
        def relative(value):
            path=absolute(value,working)
            try:
                rel=pm.relpath(path,root)
                if rel=='..' or rel.startswith('..'+pm.sep):raise ValueError()
                return rel
            except ValueError:notes.append('Sti ligger utenfor servermappen og må korrigeres: '+path);return path
        for mod in mods.values():mod['server']=mod['load_mode']=='server'
        try:port=int(options.get('port','2302'))
        except ValueError:port=2302;notes.append('Ugyldig spillport; korriger før import.')
        profile=dict(name=title or pm.basename(root) or 'Importert DayZ',root=root,config=relative(options.get('config','serverDZ.cfg')),profiles=relative(options.get('profiles','profiles')),port=port,mods=list(mods.values()),extra_args=extra)
        if re.search(r'%[^%]+%|![^!]+!',json.dumps(profile)):notes.append('Uløste variabler finnes. Korriger feltene før import.')
        if len(candidates)>=50:raise ValueError('BAT-filen har mer enn 50 serverstarter. Del den opp før import.')
        if len(mods)>512:raise ValueError('Serverstarten har mer enn 512 mods.')
        candidates.append(dict(line=number,profile=profile,warnings=notes,exe=exe))
    return dict(source=source,candidates=candidates,warnings=warnings)

def fingerprint(profile):return hashlib.sha256(json.dumps(profile,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def apply_profile(manager,data,target_id=None,expected=None):
    """Only commit reviewed settings; never write server files or start a process."""
    from core import DEFAULT,validate,local_path
    allowed={'name','root','config','profiles','port','mods','extra_args','query_enabled','auto_firewall'}
    if set(data)-allowed:raise ValueError('Importen inneholder ukjente profilfelt.')
    with manager.lock:
        old=next((p for p in manager.state['servers'] if p['id']==target_id),None) if target_id else None
        if target_id and old is None:raise ValueError('Profilen finnes ikke lenger.')
        if old is not None and fingerprint(old)!=expected:raise ValueError('Profilen er endret. Åpne importen på nytt.')
        backup=copy.deepcopy(old)
        candidate=copy.deepcopy(old if old is not None else DEFAULT);candidate.update(copy.deepcopy(data))
        candidate.setdefault('id',uuid.uuid4().hex);candidate.setdefault('login_mode','anonymous');candidate.setdefault('mission','dayzOffline.chernarusplus');candidate.setdefault('max_players',40)
        if any(re.search(r'%[^%]+%|![^!]+!',str(candidate.get(k,''))) for k in ('root','config','profiles')):raise ValueError('Uløste variabler må erstattes med faktiske stier.')
        if not isinstance(candidate.get('query_enabled',True),bool) or not isinstance(candidate.get('auto_firewall',True),bool):raise ValueError('Avhukinger må være av/på.')
        validate(candidate);root=Path(candidate['root']).resolve()
        if not (root/'DayZServer_x64.exe').is_file():raise ValueError('Fant ikke DayZServer_x64.exe i valgt servermappe.')
        cfg=local_path(root,candidate['config'])
        if not cfg.is_file():raise ValueError('Konfigurasjonsfilen finnes ikke. Korriger stien før import.')
        for p in manager.state['servers']:
            if (p is old or Path(p['root']).resolve()==root) and (manager.running(p) or p['id'] in manager.busy):raise ValueError('Stopp serveren og vent til jobbene er ferdig før import.')
        from config_documents import cfg_fields
        fields={f['key']:f['value'] for f in cfg_fields(cfg.read_text('utf-8-sig'))}
        if 'maxPlayers' in fields:
            try:candidate['max_players']=int(fields['maxPlayers'])
            except (ValueError,TypeError):pass
        from mission_settings import configured_mission
        actual=configured_mission(candidate)
        if actual:candidate['mission']=actual
        # The CFG stays authoritative, and is neither regenerated nor overwritten.
        if old is None:manager.state['servers'].append(candidate)
        else:old.update(candidate)
        try:manager.save()
        except Exception:
            if old is None:manager.state['servers'].remove(candidate)
            else:old.clear();old.update(backup)
            raise
        return copy.deepcopy(candidate)
