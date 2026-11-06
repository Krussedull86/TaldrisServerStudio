"""Create profile-scoped BattlEye RCon configuration without exposing passwords."""
import re,secrets,shutil,time
from pathlib import Path
from core import local_path

def setup(profile,port=None,password=None):
    root=Path(profile['root']).resolve()
    if not profile.get('root') or not (root/'DayZServer_x64.exe').is_file():raise ValueError('Choose an installed DayZ server first.')
    folder=local_path(root,profile['profiles'])/'BattlEye'
    extra=list(profile.get('extra_args',[]))
    if any(str(a).lower().startswith('-bepath') for a in extra):raise ValueError('Remove the existing -BEpath argument before creating profile-scoped RCon.')
    port=int(port if port is not None else int(profile['port'])+3)
    if not 1<=port<=65535 or port in (int(profile['port']),int(profile['port'])+1,int(profile['port'])+2):raise ValueError('Choose a separate valid RCon UDP port.')
    from windows_firewall import mask_config
    text=local_path(root,profile['config']).read_text('utf-8-sig')
    queries=re.findall(r'\bsteamQueryPort\s*=\s*(\d+)',mask_config(text),re.I)
    if port in [int(v) for v in queries]:raise ValueError('RCon port conflicts with steamQueryPort. Choose another RCon port or change the query port first.')
    folder.mkdir(parents=True,exist_ok=True);path=folder/'BEServer_x64.cfg'
    active=list(folder.glob('BEServer_x64_active_*.cfg'))
    if len(active)>1:raise ValueError('Multiple active BattlEye files exist. Choose the correct file manually first.')
    source=active[0] if active else path
    old=source.read_text('utf-8-sig') if source.exists() else ''
    existing=re.search(r'(?im)^\s*RConPassword\s+(\S+)\s*$',old)
    password=password or (existing[1] if existing else secrets.token_urlsafe(24))
    if not 12<=len(password)<=64 or not password.isascii() or any(c.isspace() or ord(c)<33 for c in password):raise ValueError('Use a 12–64 character ASCII password without spaces.')
    lines=[line for line in old.splitlines() if not re.match(r'\s*(RConPassword|RConPort|RestrictRCon)\b',line,re.I)]
    lines+=['RConPassword '+password,'RConPort '+str(port),'RestrictRCon 0']
    for existing_path in {source,path}:
        if existing_path.exists():shutil.copy2(existing_path,existing_path.with_name(existing_path.name+'.'+str(time.time_ns())+'.bak'))
    from host_security import protect_file
    temporary=path.with_suffix('.tmp');temporary.touch(mode=0o600,exist_ok=True);protect_file(temporary);temporary.write_text('\n'.join(lines)+'\n',encoding='utf-8');temporary.replace(path)
    if active:active[0].unlink()
    dll=folder/'BEServer_x64.dll'
    if not dll.exists():
        original=next((p for p in (root/'battleye/BEServer_x64.dll',root/'BattlEye/BEServer_x64.dll') if p.is_file()),None)
        if original:shutil.copy2(original,dll)
    profile['rcon_config']=path.relative_to(root).as_posix()
    return 'RCon configuration saved in '+profile['rcon_config']+'; UDP '+str(port)+'. Restart the server to apply. Password preserved or generated; it is not included in this result.'
