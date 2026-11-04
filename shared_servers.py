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
        if len(values)>1:raise ValueError('Multiple '+key+' appears in the configuration. Cannot determine the persistence folder for a shared server folder.')
        return values[0] if values else default
    raw=one('template','')
    try:template=json.loads(raw)
    except (ValueError,TypeError):template=''
    if not isinstance(template,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',template):raise ValueError('A shared server folder requires an unambiguous mission template in the configuration.')
    instance=str(one('instanceId','1')).strip()
    if not re.fullmatch(r'\d+',instance):raise ValueError('A shared server folder requires a valid instanceId in the configuration.')
    mission=local_path(profile['root'],'mpmissions/'+template)
    return dict(profiles=local_path(profile['root'],profile['profiles']),mission=mission,storage=mission/('storage_'+str(int(instance))))

def check_shared(profile,other,other_record=None):
    ours,theirs=resources(profile),resources(other)
    if overlaps(ours['profiles'],theirs['profiles']):raise ValueError('Profiles conflict with '+other['name']+'. Choose separate profiles folders for simultaneous servers.')
    if overlaps(ours['storage'],theirs['storage']):raise ValueError('World data conflict with '+other['name']+'. The same mission and instanceId share persistence. Choose a separate mission or instanceId in CFG before starting both servers.')
    same_mission=ours['mission'].resolve()==theirs['mission'].resolve()
    if same_mission and (profile.get('scheduled_restart') or other.get('scheduled_restart') or (other_record or {}).get('restart_due')):raise ValueError('The messages.xml restart schedule is shared with '+other['name']+'. Use separate mission folders for independent native restart schedules.')
    return same_mission
