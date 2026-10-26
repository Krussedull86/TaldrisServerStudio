"""Read mission choices from the actual CFG and save one template with backup."""
import json,re
from pathlib import Path
from config_documents import Document,cfg_fields,cfg_set,digest

def configured_mission(profile):
    from core import local_path
    try:
        fields=[f for f in cfg_fields(local_path(profile['root'],profile['config']).read_text('utf-8-sig')) if f['key'].casefold()=='template']
        if len(fields)==1:
            value=json.loads(fields[0]['value'])
            if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.-]+',value):return value
    except (OSError,ValueError,TypeError):pass
    return None

def choices(profile):
    defaults=['dayzOffline.chernarusplus','dayzOffline.enoch','dayzOffline.sakhal','dayzOffline.nasdara']
    folder=Path(profile['root'])/'mpmissions' if profile.get('root') else None
    if folder and folder.is_dir():defaults+=[p.name for p in folder.iterdir() if p.is_dir()]
    current=configured_mission(profile) or profile.get('mission','dayzOffline.chernarusplus')
    return sorted(set(defaults+[current])),current

def check_config_edit(manager,p,relative):
    from core import local_path
    if not p.get('root'):raise ValueError('Velg servermappe først.')
    if manager.running(p) or p['id'] in manager.busy:raise ValueError('Stopp denne serveren og vent til jobben er ferdig før lagring.')
    root=Path(p['root']).resolve();path=local_path(root,relative)
    for other in manager.state['servers']:
        if other['id']==p['id'] or Path(other['root']).resolve()!=root:continue
        if not manager.running(other) and other['id'] not in manager.busy:continue
        own_cfg=path==local_path(root,p['config']) and path.parent==root
        if other['id'] in manager.busy or not own_cfg or path==local_path(root,other['config']):raise ValueError('Filen deles med en aktiv profil. Stopp berørte servere før lagring.')

def save_mission(manager,profile,mission,base):
    if not isinstance(mission,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',mission) or mission in ('.','..'):raise ValueError('Ugyldig mission-navn.')
    with manager.lock:
        check_config_edit(manager,profile,profile['config']);doc=Document(profile,profile['config'],manager.home)
        if digest(doc.original)!=base:raise ValueError('CFG er endret. Les konfigurasjonen på nytt før lagring.')
        fields=cfg_fields(doc.text);indexes=[i for i,f in enumerate(fields) if f['key'].casefold()=='template']
        if len(indexes)!=1:raise ValueError('CFG må inneholde én template under class Missions. Åpne Konfigurasjon og rett dette først.')
        doc.text=cfg_set(doc.text,indexes[0],json.dumps(mission));backup=doc.save() if doc.dirty else None
        profile['mission']=mission;manager.save()
        return dict(mission=mission,backup=backup,folder_exists=(Path(profile['root'])/'mpmissions'/mission).is_dir())
