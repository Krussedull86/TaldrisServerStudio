"""Discover local @mods without downloading, copying or modifying their sources."""
import os
from pathlib import Path

def canonical(path):return os.path.normcase(str(Path(path).resolve())).casefold()

def inspect_mod(path):
    path=Path(path).absolute()
    if not path.is_dir() or not path.name.startswith('@'):raise ValueError('Velg en modmappe som begynner med @.')
    if any(c in str(path) for c in [';','"','\n','\r','\x00']):raise ValueError('Modstien kan ikke inneholde semikolon, anførselstegn eller linjeskift.')
    # Steam !Workshop entries can be directory links; inspect but never alter them.
    addons=next((p for p in path.iterdir() if p.is_dir() and p.name.casefold()=='addons'),None)
    pbos=[p for p in addons.iterdir() if p.is_file() and p.suffix.casefold()=='.pbo'] if addons else []
    count=len({p.resolve() for p in pbos if p.is_file()})
    keys=[]
    for folder in path.iterdir():
        if folder.is_dir() and folder.name.casefold()=='keys':keys.extend(p for p in folder.iterdir() if p.is_file() and p.suffix.casefold()=='.bikey')
    return dict(name=path.name,path=str(path),pbo_count=count,key_count=len(keys),ready=count>0,status=f'{count} PBO • {len(keys)} nøkler' if count else 'Ingen pakket PBO i Addons – bygg modden først')

def scan_mods(directory,recursive=False):
    root=Path(directory).absolute()
    if not root.is_dir():raise ValueError('Mappen finnes ikke.')
    candidates=[]; seen=set(); warnings=[]
    def add(path):
        try:
            info=inspect_mod(path); identity=canonical(path)
            if identity not in seen:candidates.append(info); seen.add(identity)
        except (OSError,ValueError) as e:warnings.append(str(path)+': '+str(e))
    if root.name.startswith('@'):
        add(root); return {'mods':candidates,'warnings':warnings}
    if recursive:
        def onerror(error):warnings.append(str(error))
        for current,dirs,_ in os.walk(root,followlinks=False,onerror=onerror):
            if Path(current)!=root and Path(current).name.startswith('@'):dirs[:]=[]; continue
            for name in list(dirs):
                if name.startswith('@'):add(Path(current)/name); dirs.remove(name)
            dirs[:]=[n for n in dirs if n not in ('.git','node_modules','.venv')]
    else:
        for p in root.iterdir():
            if p.name.startswith('@') and p.is_dir():add(p)
    return {'mods':sorted(candidates,key=lambda m:m['name'].casefold()),'warnings':warnings}

def import_mods(profile,rows,server_only=False,load_mode=None):
    """Atomic list update. Same folder label is safe with distinct absolute paths."""
    from core import validate_mod
    mode=load_mode or ('server' if server_only else 'client')
    existing=list(profile['mods']); identities={canonical(m['path']) for m in existing if m.get('source')=='local'}
    # Existing root-relative mods must not load twice when found by the scanner.
    if profile.get('root'):
        identities.update(canonical(Path(profile['root'])/m['folder']) for m in existing if m.get('source')!='local')
    added=[]; skipped=0
    for row in rows:
        info=inspect_mod(row['path']); identity=canonical(info['path'])
        if identity in identities:skipped+=1; continue
        m=dict(folder=info['name'],id='',source='local',path=info['path'],enabled=info['ready'],server=mode=='server',load_mode=mode,title=info['name'])
        validate_mod(m); existing.append(m); added.append(m); identities.add(identity)
    profile['mods']=existing
    return added,skipped
