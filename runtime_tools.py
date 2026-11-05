"""Validated per-server runtime automation settings."""
from pathlib import Path
from batch_import import tokenize

def arguments(value):
    if not isinstance(value,str) or len(value)>8192 or any(ord(c)<32 for c in value):raise ValueError('Invalid program arguments.')
    return [v for v,_ in tokenize(value)]

def validate_runtime(profile):
    from performance_policy import policy
    from telemetry_store import settings
    policy(profile);settings(profile)
    for key in ('log_rotation_enabled','mod_restart_enabled'):
        if not isinstance(profile.get(key,False),bool):raise ValueError(key+' must be on/off.')
    for key,default,low,high in [('log_keep_days',14,1,3650),('log_keep_archives',20,1,1000),('log_max_mb',1024,10,102400),('mod_grace_minutes',15,1,1440)]:
        value=profile.get(key,default)
        if isinstance(value,bool) or not isinstance(value,int) or not low<=value<=high:raise ValueError(f'{key} must be {low}–{high}.')
    programs=profile.get('programs',[])
    if not isinstance(programs,list) or len(programs)>50:raise ValueError('Use no more than 50 companion programs per server.')
    ids=set()
    for p in programs:
        if not isinstance(p,dict) or not isinstance(p.get('id'),str) or not p['id'] or p['id'] in ids:raise ValueError('Program IDs must be unique.')
        ids.add(p['id'])
        for key in ('enabled','on_start','on_restart','required'):
            if not isinstance(p.get(key,True),bool):raise ValueError('Program options must be on/off.')
        if not isinstance(p.get('name',''),str) or len(p.get('name',''))>200:raise ValueError('Invalid program name.')
        path=p.get('path','');cwd=p.get('cwd','')
        if not isinstance(path,str) or not Path(path).is_absolute() or Path(path).suffix.casefold()!='.exe' or any(ord(c)<32 for c in path):raise ValueError('Choose an absolute path to an EXE file.')
        if Path(path).name.casefold()=='dayzserver_x64.exe':raise ValueError('Manage DayZ servers through server profiles rather than the EXE list.')
        if not isinstance(cwd,str) or (cwd and not Path(cwd).is_absolute()):raise ValueError('The working directory must be an absolute path or empty.')
        wait=p.get('wait_seconds',2)
        if isinstance(wait,bool) or not isinstance(wait,int) or not 0<=wait<=120:raise ValueError('Wait time must be 0–120 seconds.')
        arguments(p.get('args',''))
    return profile
