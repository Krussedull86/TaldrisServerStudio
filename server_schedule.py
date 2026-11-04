"""DayZ's own messages.xml countdown/shutdown, preserving user messages."""
from datetime import datetime,timedelta
import math
from pathlib import Path
import re
import shutil
import time
import xml.etree.ElementTree as ET
from windows_firewall import mask_config


def restart_times(value):
    result=[]
    for item in value.replace(';',',').split(','):
        item=item.strip()
        if not item:continue
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',item):
            raise ValueError('Use HH:MM times separated by commas, for example 00:00, 06:00, 12:00, 18:00.')
        result.append(item)
    return sorted(set(result))


def next_restart(profile, now=None):
    now=now or datetime.now().astimezone()
    if not profile.get('scheduled_restart'):return None
    if profile.get('restart_mode','clock')=='interval':
        minutes=int(profile.get('restart_interval',240))
        if not 10<=minutes<=10080:raise ValueError('Restart interval must be 10–10080 minutes.')
        return now+timedelta(minutes=minutes)
    times=restart_times(profile.get('restart_times','00:00, 06:00, 12:00, 18:00'))
    if not times:raise ValueError('Choose at least one restart time.')
    candidates=[]
    for day in (0,1):
        for clock in times:
            hour,minute=map(int,clock.split(':'))
            candidate=(now+timedelta(days=day)).replace(hour=hour,minute=minute,second=0,microsecond=0)
            if candidate>now+timedelta(minutes=2):candidates.append(candidate)
    return min(candidates)


def prepare_messages(profile,log,now=None):
    now=now or datetime.now().astimezone(); target=next_restart(profile,now)
    root=Path(profile['root']).resolve()
    config=(root/profile['config']).read_text('utf-8-sig')
    # Mission is a string literal; comments are masked without masking strings here.
    cleaned=re.sub(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*',lambda m:m.group() if m.group().startswith('"') else ' '*len(m.group()),config,flags=re.S)
    missions=re.findall(r'\btemplate\s*=\s*"([A-Za-z0-9_.-]+)"\s*;',cleaned)
    if not missions:
        if target:raise ValueError('Mission template was not found in the server configuration. A safe restart cannot be scheduled.')
        return None
    path=root/'mpmissions'/missions[-1]/'db'/'messages.xml'
    if not path.parent.is_dir():
        if target:raise ValueError('The mission db folder does not exist: '+str(path.parent))
        return None
    if path.exists():
        tree=ET.parse(path,parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))); xml=tree.getroot()
        if xml.tag!='messages':raise ValueError('Invalid messages.xml.')
    else:xml=ET.Element('messages'); tree=ET.ElementTree(xml)
    changed=False
    for child in list(xml):
        if child.get('taldris')=='restart':xml.remove(child); changed=True
        elif target and child.findtext('shutdown','0').strip()=='1':
            raise ValueError('messages.xml already contains a shutdown schedule. Remove the old schedule or disable the application restart schedule.')
    if target:
        # DayZ locks/kicks at the deadline and exits about one minute later.
        minutes=max(1,math.ceil((target-now).total_seconds()/60)-1)
        node=ET.SubElement(xml,'message',{'taldris':'restart'})
        for key,value in [('deadline',str(minutes)),('shutdown','1'),('text','Server restart in #tmin minutes. Please find a safe place.')]:ET.SubElement(node,key).text=value
        changed=True
    if changed:
        if path.exists():shutil.copy2(path,path.with_name('messages.xml.'+str(time.time_ns())+'.bak'))
        ET.indent(tree,space='  '); tmp=path.with_suffix('.tmp'); tree.write(tmp,encoding='utf-8',xml_declaration=True); tmp.replace(path)
    if target:log('Scheduled restart approximately '+target.strftime('%d.%m %H:%M')+' (local system time). DayZ warns players and saves before shutting down.')
    return target.timestamp() if target else None
