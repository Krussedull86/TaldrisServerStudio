"""Launch the local DayZ client, independently of the server/service process."""
import os,re,subprocess
from pathlib import Path
from core import mod_path,mod_load_mode

def steam_roots():
    roots=[]
    if os.name=='nt':
        import winreg
        for hive,key,value in [(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam','SteamPath'),(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\WOW6432Node\Valve\Steam','InstallPath')]:
            try:
                with winreg.OpenKey(hive,key) as entry:roots.append(Path(winreg.QueryValueEx(entry,value)[0]))
            except OSError:pass
    for root in list(roots):
        manifest=root/'steamapps/libraryfolders.vdf'
        try:
            for value in re.findall(r'"path"\s*"([^"\r\n]+)"',manifest.read_text('utf-8')):roots.append(Path(value.replace('\\\\','\\')))
        except OSError:pass
    return list(dict.fromkeys(roots))

def find_game(roots):
    for root in roots:
        folder=Path(root)/'steamapps/common/DayZ'
        if (folder/'DayZ_x64.exe').is_file():return str(folder)
    return ''

def client_mods(profile,game,roots,overrides=None):
    result=[];overrides=overrides or {};roots=list(roots)
    folder=Path(game).resolve()
    if len(folder.parents)>=3:roots.append(folder.parents[2])
    for index,mod in enumerate(profile.get('mods',[])):
        if not mod.get('enabled',True) or mod_load_mode(mod)=='server':continue
        identity=mod.get('id') or mod.get('path') or mod['folder']
        candidates=[]
        if overrides.get(identity):candidates=[Path(overrides[identity])]
        else:
            candidates.append(mod_path(profile,mod))
            if mod.get('id'):
                candidates.extend(Path(root)/'steamapps/workshop/content/221100'/str(mod['id']) for root in roots)
            candidates.append(Path(game)/'!Workshop'/mod['folder'])
        path=next((p.resolve() for p in candidates if (p/'addons').is_dir() or (p/'Addons').is_dir()),None)
        result.append(dict(identity=identity,title=mod.get('title') or mod['folder'],path=str(path) if path else '',index=index))
    return result

def command(game,profile,mods):
    folder=Path(game).resolve()
    if not (folder/'DayZ_x64.exe').is_file():raise ValueError('Velg DayZ-spillmappen med DayZ_x64.exe, ikke DayZServer-mappen.')
    be=folder/'DayZ_BE.exe'
    if not be.is_file():raise ValueError('DayZ_BE.exe mangler. Verifiser DayZ-klienten i Steam.')
    port=int(profile['port'])
    if not 1<=port<=65535:raise ValueError('Ugyldig spillport.')
    paths=[]
    for mod in mods:
        if not mod['path']:raise ValueError('Mangler klientmod: '+mod['title']+'. Velg lokal modmappe eller installer den via Steam Workshop.')
        path=Path(mod['path']).resolve()
        if ';' in str(path) or any(ord(c)<32 for c in str(path)):raise ValueError('Modsti kan ikke inneholde semikolon eller kontrolltegn.')
        if not ((path/'addons').is_dir() or (path/'Addons').is_dir()):raise ValueError('Modmappen finnes ikke lenger: '+str(path))
        if str(path) not in paths:paths.append(str(path))
    args=[str(be),'0','1','1','-exe','DayZ_x64.exe','-connect=127.0.0.1','-port='+str(port)]
    if paths:args.append('-mod='+';'.join(paths))
    if len(subprocess.list2cmdline(args))>30000:raise ValueError('Modlisten er for lang for Windows. Bruk kortere modstier.')
    return args

def launch(args):
    return subprocess.Popen(args,cwd=str(Path(args[0]).parent),close_fds=True,env={**os.environ,'SteamAppId':'221100','SteamGameId':'221100','PYINSTALLER_RESET_ENVIRONMENT':'1'})
