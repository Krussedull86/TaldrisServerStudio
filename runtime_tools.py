"""Validated per-server runtime automation settings."""
from pathlib import Path
from batch_import import tokenize

def arguments(value):
    if not isinstance(value,str) or len(value)>8192 or any(ord(c)<32 for c in value):raise ValueError('Ugyldige programargumenter.')
    return [v for v,_ in tokenize(value)]

def validate_runtime(profile):
    for key in ('log_rotation_enabled','mod_restart_enabled'):
        if not isinstance(profile.get(key,False),bool):raise ValueError(key+' må være av/på.')
    for key,default,low,high in [('log_keep_days',14,1,3650),('log_keep_archives',20,1,1000),('log_max_mb',1024,10,102400),('mod_grace_minutes',15,1,1440)]:
        value=profile.get(key,default)
        if isinstance(value,bool) or not isinstance(value,int) or not low<=value<=high:raise ValueError(f'{key} må være {low}–{high}.')
    programs=profile.get('programs',[])
    if not isinstance(programs,list) or len(programs)>50:raise ValueError('Bruk maksimalt 50 tilleggsprogrammer per server.')
    ids=set()
    for p in programs:
        if not isinstance(p,dict) or not isinstance(p.get('id'),str) or not p['id'] or p['id'] in ids:raise ValueError('Program-ID må være unik.')
        ids.add(p['id'])
        for key in ('enabled','on_start','on_restart','required'):
            if not isinstance(p.get(key,True),bool):raise ValueError('Programvalg må være av/på.')
        if not isinstance(p.get('name',''),str) or len(p.get('name',''))>200:raise ValueError('Ugyldig programnavn.')
        path=p.get('path','');cwd=p.get('cwd','')
        if not isinstance(path,str) or not Path(path).is_absolute() or Path(path).suffix.casefold()!='.exe' or any(ord(c)<32 for c in path):raise ValueError('Velg en absolutt sti til en EXE-fil.')
        if Path(path).name.casefold()=='dayzserver_x64.exe':raise ValueError('DayZ-servere styres gjennom serverprofiler, ikke EXE-listen.')
        if not isinstance(cwd,str) or (cwd and not Path(cwd).is_absolute()):raise ValueError('Arbeidsmappe må være en absolutt sti eller tom.')
        wait=p.get('wait_seconds',2)
        if isinstance(wait,bool) or not isinstance(wait,int) or not 0<=wait<=120:raise ValueError('Ventetid må være 0–120 sekunder.')
        arguments(p.get('args',''))
    return profile
