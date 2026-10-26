"""Identify writable runtime resources when DayZ instances share executable files."""
import json,re
from pathlib import Path

def overlaps(a,b):
    a,b=Path(a).resolve(),Path(b).resolve()
    return a==b or a.is_relative_to(b) or b.is_relative_to(a)

def resources(profile):
    from core import local_path
    from config_documents import cfg_fields
    fields=cfg_fields(local_path(profile['root'],profile['config']).read_text('utf-8-sig'))
    def one(key,default):
        values=[f['value'] for f in fields if f['key'].casefold()==key.casefold()]
        if len(values)>1:raise ValueError('Flere '+key+' finnes i konfigurasjonen. Kan ikke avgjøre lagringsmappen for delt servermappe.')
        return values[0] if values else default
    raw=one('template','')
    try:template=json.loads(raw)
    except (ValueError,TypeError):template=''
    if not isinstance(template,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',template):raise ValueError('Delt servermappe krever en entydig mission template i konfigurasjonen.')
    instance=str(one('instanceId','1')).strip()
    if not re.fullmatch(r'\d+',instance):raise ValueError('Delt servermappe krever et gyldig instanceId i konfigurasjonen.')
    mission=local_path(profile['root'],'mpmissions/'+template)
    return dict(profiles=local_path(profile['root'],profile['profiles']),mission=mission,storage=mission/('storage_'+str(int(instance))))

def check_shared(profile,other,other_record=None):
    ours,theirs=resources(profile),resources(other)
    if overlaps(ours['profiles'],theirs['profiles']):raise ValueError('Profiles-konflikt med '+other['name']+'. Velg separate profiles-mapper for samtidige servere.')
    if overlaps(ours['storage'],theirs['storage']):raise ValueError('Verdensdata-konflikt med '+other['name']+'. Samme mission og instanceId bruker samme lagring. Velg egen mission eller eget instanceId i CFG før samtidig start.')
    same_mission=ours['mission'].resolve()==theirs['mission'].resolve()
    if same_mission and (profile.get('scheduled_restart') or other.get('scheduled_restart') or (other_record or {}).get('restart_due')):raise ValueError('Restartplanen i messages.xml deles med '+other['name']+'. Bruk separate missionmapper for uavhengige native restartplaner.')
    return same_mission
