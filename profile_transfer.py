"""Portable settings only: never credentials, runtime PIDs or automatic starts."""
import copy,json,uuid
from pathlib import Path
from core import DEFAULT,validate
FIELDS={'performance','telemetry','name','root','steamcmd','login_mode','workshop','config','profiles','port','mods','markers','map_size','map_image','extra_args','auto_firewall','query_enabled','auto_update','update_minutes','mission','max_players','update_game','scheduled_restart','restart_mode','restart_times','restart_interval','maintenance_backup','backup_keep','crash_recovery','log_rotation_enabled','log_keep_days','log_keep_archives','log_max_mb','mod_restart_enabled','mod_grace_minutes'}
MOD_FIELDS={'folder','id','title','source','path','enabled','server','load_mode','installed_updated','remote_updated'}

def sanitized(raw):
    if not isinstance(raw,dict):raise ValueError('Invalid profile JSON.')
    fields={k:copy.deepcopy(v) for k,v in raw.items() if k in FIELDS}
    if not isinstance(fields.get('mods',[]),list):raise ValueError('Invalid mod list.')
    if any(not isinstance(m,dict) for m in fields.get('mods',[])):raise ValueError('Invalid mod entry.')
    for key in ('auto_firewall','query_enabled','auto_update','update_game','scheduled_restart','maintenance_backup','crash_recovery','log_rotation_enabled','mod_restart_enabled'):
        if key in fields and type(fields[key]) is not bool:raise ValueError(key+' must be on/off.')
    fields['mods']=[{k:v for k,v in m.items() if k in MOD_FIELDS} for m in fields.get('mods',[]) if isinstance(m,dict)]
    candidate=copy.deepcopy(DEFAULT);candidate.update(fields);candidate.setdefault('mission','dayzOffline.chernarusplus');candidate.setdefault('max_players',40);validate(candidate)
    if not isinstance(candidate.get('name'),str) or not candidate['name'].strip():raise ValueError('Profile name is required.')
    return fields

def export_profile(profile,path):
    fields=sanitized(profile);Path(path).write_text(json.dumps({'format':'cruz-server-profile','version':1,'profile':fields},indent=2,ensure_ascii=False),encoding='utf-8')

def read_profile(path):
    path=Path(path)
    if path.stat().st_size>2*1024*1024:raise ValueError('Profile exceeds 2 MB.')
    raw=json.loads(path.read_text('utf-8-sig'))
    if isinstance(raw,dict) and 'profile' in raw:
        if raw.get('format')!='cruz-server-profile' or raw.get('version')!=1:raise ValueError('Unsupported profile format/version.')
        raw=raw['profile']
    return sanitized(raw)

def import_profile(manager,raw):
    fields=sanitized(raw);candidate=copy.deepcopy(DEFAULT);candidate.update(fields);candidate.update(id=uuid.uuid4().hex,autostart=False,desired_running=False,programs=[])
    with manager.lock:
        manager.state['servers'].append(candidate)
        try:manager.save()
        except Exception:manager.state['servers'].remove(candidate);raise
    return copy.deepcopy(candidate)
