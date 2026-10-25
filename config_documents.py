"""Loss-aware configuration documents, bounded parsing and compare-before-write."""
import copy,difflib,hashlib,json,re,shutil,time
from pathlib import Path
import xml.etree.ElementTree as ET
from core import local_path
from windows_firewall import mask_config

MAX_BYTES=8*1024*1024
EXTENSIONS={'.cfg','.json','.xml','.txt'}
BOOL_NAMES={'enabled','active','init','load','save','respawn','onconnect','shutdown','count_in_cargo','count_in_hoarder','count_in_map','count_in_player','crafted','deloot'}
SCHEMA={
 'hostname':('Servernavn','string'),'description':('Beskrivelse','string'),'password':('Spillerpassord','password'),'passwordAdmin':('Administratorpassord','password'),
 'steamQueryPort':('Steam query-port','integer'),'maxPlayers':('Spillerplasser','integer'),'enableWhitelist':('Aktiver whitelist','bool'),
 'verifySignatures':('Signaturkontroll (2)','integer'),'forceSameBuild':('Krev samme spillversjon','bool'),'disableVoN':('Deaktiver tale','bool'),
 'vonCodecQuality':('Talekvalitet','integer'),'disable3rdPerson':('Deaktiver tredjeperson','bool'),'thirdPersonView':('Perspektiv: 0 av / 1 på / 2 kjøretøy','integer'),
 'disableCrosshair':('Skjul siktekors','bool'),'disablePersonalLight':('Deaktiver personlig lys','bool'),'lightingConfig':('Lysoppsett','integer'),
 'serverTime':('Starttid / SystemTime','string'),'serverTimeAcceleration':('Tidshastighet','number'),'serverNightTimeAcceleration':('Ekstra nattmultiplikator','number'),
 'serverTimePersistent':('Behold spilltid ved restart','bool'),'enableCfgGameplayFile':('Bruk cfggameplay.json','bool'),'storageAutoFix':('Reparer skadet lagring automatisk','bool'),
 'loginQueueConcurrentPlayers':('Samtidige innlogginger','integer'),'loginQueueMaxPlayers':('Maks kø','integer'),'instanceId':('Lagringsinstans','integer'),
 'disableBaseDamage':('Deaktiver baseskade','bool'),'disableContainerDamage':('Deaktiver containerskade','bool'),'MaxPing':('Maks ping','integer'),
 'template':('Mission / kart','string'),'RConPassword':('RCon-passord','password'),'RConPort':('RCon-port','integer'),'RConIP':('Lokal RCon-IP','string')}


def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()

def parse_xml(text):
    if re.search(r'<!\s*(DOCTYPE|ENTITY)',text,re.I):raise ValueError('DTD og XML-entities støttes ikke i serverkonfigurasjoner.')
    return ET.fromstring(text,parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))


def xml_text(root):
    root=copy.deepcopy(root);ET.indent(root,space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root,encoding='unicode')+'\n'


def cfg_fields(text):
    masked=mask_config(text)
    pattern=re.compile(r'\b([A-Za-z_]\w*(?:\[\])?)\s*=')
    fields=[]
    if '=' not in masked:
        for match in re.finditer(r'(?m)^([A-Za-z_]\w*)[ \t]+([^\r\n]+)',text):
            key=match.group(1)
            if key.startswith('//'):continue
            fields.append(dict(key=key,start=match.start(2),end=match.end(2),value=match.group(2).strip(),kind=SCHEMA.get(key,('', 'raw'))[1],label=SCHEMA.get(key,(key,''))[0],style='line'))
        return fields
    for m in pattern.finditer(masked):
        start=m.end();end=masked.find(';',start)
        if end<0:raise ValueError('Mangler semikolon etter '+m.group(1))
        raw=re.sub(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*',lambda match:match.group() if match.group().startswith('"') else ' '*len(match.group()),text[start:end],flags=re.S).strip();key=m.group(1);kind=SCHEMA.get(key,('',None))[1]
        if not kind:
            kind='string' if raw.startswith('"') else 'bool' if raw in ('true','false') else 'number' if re.fullmatch(r'-?\d+(?:\.\d+)?',raw) else 'raw'
        fields.append(dict(key=key,start=start,end=end,value=raw,kind=kind,label=SCHEMA.get(key,(key,kind))[0]))
    return fields


def cfg_set(text,index,value):
    field=cfg_fields(text)[index]
    return text[:field['start']]+' '+str(value)+text[field['end']:]


def validate_text(text,suffix):
    if len(text.encode('utf-8'))>MAX_BYTES:raise ValueError('Konfigurasjonen er større enn 8 MB.')
    if suffix=='.json':json.loads(text)
    elif suffix=='.xml':parse_xml(text)
    elif suffix=='.cfg':
        masked=mask_config(text);stack=[]
        for char in masked:
            if char in '{[':stack.append(char)
            elif char in '}]':
                if not stack or stack.pop()!=('{' if char=='}' else '['):raise ValueError('Ubalanserte klammer i CFG.')
        if stack:raise ValueError('Uavsluttet blokk i CFG.')
        if '"' in masked or '/*' in masked:raise ValueError('Uavsluttet tekststreng eller kommentar i CFG.')
        import math
        for field in cfg_fields(text):
            raw=field['value'];kind=field['kind']
            try:
                if kind=='integer':int(raw)
                elif kind=='number':
                    if not math.isfinite(float(raw)):raise ValueError()
                elif kind=='bool' and raw not in ('0','1','true','false'):raise ValueError()
                elif kind in ('string','password') and field.get('style')!='line':
                    if not isinstance(json.loads(raw),str):raise ValueError()
            except ValueError:raise ValueError('Ugyldig verdi for '+field['key'])


def catalog(profile):
    root=Path(profile['root']).resolve()
    if not profile['root'] or not root.is_dir():return []
    skip={'addons','dta','steamapps','node_modules','.git','program_updates','backups'};found=[]
    import os
    for current,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if d.casefold() not in skip and not d.startswith('@') and not d.endswith(('.previous','.staging'))]
        for name in files:
            path=Path(current)/name
            if path.suffix.casefold() in EXTENSIONS and path.stat().st_size<=MAX_BYTES and path.resolve().is_relative_to(root):found.append(path.relative_to(root).as_posix())
            if len(found)>=3000:return sorted(found)
    return sorted(found,key=lambda value:(value!=profile['config'],value.casefold()))


class Document:
    def __init__(self,profile,relative,home):
        self.profile=profile;self.relative=relative;self.home=Path(home);self.path=local_path(profile['root'],relative)
        if self.path.suffix.casefold() not in EXTENSIONS:raise ValueError('Velg CFG, JSON, XML eller TXT.')
        if self.path.stat().st_size>MAX_BYTES:raise ValueError('Filen er større enn 8 MB.')
        self.original=self.path.read_text('utf-8-sig');self.text=self.original;self.suffix=self.path.suffix.casefold()
    @property
    def dirty(self):return self.text!=self.original
    @property
    def history_dir(self):return self.home/'config_history'/self.profile['id']/hashlib.sha256(self.relative.encode()).hexdigest()[:20]
    def diff(self):return ''.join(difflib.unified_diff(self.original.splitlines(True),self.text.splitlines(True),fromfile=self.relative+' (disk)',tofile=self.relative+' (endret)'))
    def warnings(self):
        validate_text(self.text,self.suffix);warnings=[]
        if self.suffix=='.xml':
            root=parse_xml(self.text)
            if root.tag=='types':
                names=set()
                for item in root.findall('type'):
                    name=item.get('name','')
                    if not name or name in names:warnings.append('Manglende eller gjentatt type-navn: '+name)
                    names.add(name)
                    nominal=item.findtext('nominal');minimum=item.findtext('min')
                    if nominal is not None and minimum is not None:
                        try:
                            if int(nominal)>0 and int(minimum)>int(nominal):warnings.append(name+': min er høyere enn nominal.')
                        except ValueError:raise ValueError(name+': nominal og min må være heltall.')
        return warnings
    def save(self):
        self.warnings()
        # Resolve again: a swapped directory link must not escape the server root.
        path=local_path(self.profile['root'],self.relative)
        if path!=self.path or path.read_text('utf-8-sig')!=self.original:raise ValueError('Filen er endret på disk. Last den inn på nytt og sammenlign endringene.')
        self.history_dir.mkdir(parents=True,exist_ok=True)
        old=self.history_dir/(str(time.time_ns())+self.suffix);old.write_bytes(path.read_bytes())
        (self.history_dir/'source.json').write_text(json.dumps({'file':self.relative}),encoding='utf-8')
        tmp=path.with_name(path.name+'.taldris.tmp');tmp.write_text(self.text,encoding='utf-8');tmp.replace(path)
        self.original=self.text;return str(old)
    def restore(self,backup):
        backup=Path(backup).resolve()
        if backup.parent!=self.history_dir.resolve() or backup.name=='source.json':raise ValueError('Ugyldig historikkfil.')
        self.text=backup.read_text('utf-8-sig');self.warnings()


TYPE_COLUMNS=['name','nominal','min','lifetime','restock','quantmin','quantmax','cost','category','usage','value','tag']

def type_rows(text):
    root=parse_xml(text)
    if root.tag!='types':raise ValueError('Dette er ikke en types.xml-fil.')
    result=[]
    for item in root.findall('type'):
        row={'name':item.get('name','')}
        for key in TYPE_COLUMNS[1:]:row[key]='; '.join(e.get('name',e.text or '') for e in item.findall(key))
        result.append(row)
    return result


def edit_type(text,index,key,value):
    if key not in TYPE_COLUMNS:raise ValueError('Ukjent types-felt.')
    root=parse_xml(text);item=root.findall('type')[index]
    if key=='name':
        if not re.fullmatch(r'[A-Za-z_]\w*',value):raise ValueError('Ugyldig klassenavn.')
        item.set('name',value)
    elif key in ('category','usage','value','tag'):
        for child in list(item.findall(key)):item.remove(child)
        for name in filter(None,(s.strip() for s in value.split(';'))):ET.SubElement(item,key,{'name':name})
    else:
        number=int(value)
        if number<(-1 if key in ('quantmin','quantmax') else 0):raise ValueError('Ugyldig negativ verdi.')
        if key in ('quantmin','quantmax') and number>100:raise ValueError('Mengde må være -1 eller 0–100.')
        node=item.find(key)
        if node is None:node=ET.SubElement(item,key)
        node.text=str(number)
    return xml_text(root)


def merge_types(text,other,replace=False):
    root=parse_xml(text);incoming=parse_xml(other)
    if root.tag!='types' or incoming.tag!='types':raise ValueError('Begge filer må være types.xml-format.')
    existing={item.get('name'):item for item in root.findall('type')};added=skipped=0
    for node in incoming.findall('type'):
        name=node.get('name')
        if not name:raise ValueError('En importert type mangler navn.')
        if name in existing:
            if not replace:skipped+=1;continue
            root.remove(existing[name])
        new=copy.deepcopy(node);root.append(new);existing[name]=new;added+=1
    return xml_text(root),added,skipped
