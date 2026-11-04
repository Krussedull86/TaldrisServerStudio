"""Resolve active mission from server CFG; include its configured CE types files."""
from pathlib import Path
from core import local_path
from mission_settings import configured_mission
from config_documents import parse_xml,MAX_BYTES

def active_types(profile):
    mission=configured_mission(profile)
    if not mission:raise ValueError('Cannot resolve a single mission template from this profile’s server CFG.')
    folder=local_path(profile['root'],'mpmissions/'+mission)
    if not folder.is_dir():raise ValueError('Active mission folder not found: '+str(folder))
    candidates=[folder/'db/types.xml'];economy=folder/'cfgeconomycore.xml'
    if economy.is_file():
        if economy.stat().st_size>MAX_BYTES:raise ValueError('cfgeconomycore.xml exceeds 8 MB.')
        for ce in parse_xml(economy.read_text('utf-8-sig')).findall('ce'):
            for file in ce.findall('file'):
                if file.get('type')=='types':candidates.append(folder/ce.get('folder','')/file.get('name',''))
    result=[]
    for candidate in candidates:
        resolved=candidate.resolve()
        if not resolved.is_relative_to(folder):raise ValueError('CE types file escapes the active mission folder.')
        if resolved.is_file() and resolved not in result:result.append(resolved)
    return dict(mission=mission,folder=str(folder),files=[p.relative_to(Path(profile['root']).resolve()).as_posix() for p in result])
