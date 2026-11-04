"""Loss-aware DZSA table model and local saved revisions, ported from our desktop editor."""
import copy,json,re,time,uuid
from pathlib import Path
from config_documents import parse_xml,xml_text,MAX_BYTES
FIELDS=('nominal','lifetime','restock','min','quantmin','quantmax','cost')
FLAGS=('count_in_cargo','count_in_hoarder','count_in_map','count_in_player','crafted','deloot')
LABELS=('category','tag','usage','value')

def validate_rows(rows):
    if not isinstance(rows,list) or len(rows)>50000:raise ValueError('Invalid loot rows (maximum 50,000).')
    seen=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid loot row.')
        name=row.get('name')
        if not isinstance(name,str) or not name or name in seen:raise ValueError('Missing or duplicate item name.')
        seen.add(name)
        for key in FIELDS:
            value=row.get(key);low=-1 if key.startswith('quant') else 0;high=100 if key.startswith('quant') else 2147483647
            if type(value) is not int or not low<=value<=high:raise ValueError(f'{name}: invalid {key} ({low}–{high}).')
        for key in FLAGS:
            if type(row.get('flags',{}).get(key)) is not int or row['flags'][key] not in (0,1):raise ValueError(f'{name}: {key} must be 0 or 1.')
        for key in LABELS:
            if not isinstance(row.get(key),str):raise ValueError(f'{name}: invalid {key}.')
    return rows

def parse_types(text):
    if len(text.encode('utf-8'))>MAX_BYTES:raise ValueError('XML exceeds 8 MB.')
    root=parse_xml(text)
    if root.tag!='types':raise ValueError('Expected a <types> root.')
    rows=[]
    for node in root.findall('type'):
        row={'name':node.get('name','')}
        for key in FIELDS:
            found=node.findall(key)
            if len(found)!=1:raise ValueError(row['name']+': expected one '+key+' element.')
            row[key]=int(found[0].text or '')
        flags=node.find('flags');row['flags']={key:int(flags.get(key,'0')) if flags is not None else 0 for key in FLAGS}
        for key in LABELS:row[key]=', '.join(n.get('name','') for n in node.findall(key))
        rows.append(row)
    return validate_rows(rows)

def export_types(original,rows):
    validate_rows(rows);root=parse_xml(original);sources={n.get('name'):n for n in root.findall('type')};result=[]
    for row in rows:
        if row['name'] not in sources:raise ValueError('Unknown item: '+row['name'])
        node=copy.deepcopy(sources[row['name']])
        for key in FIELDS:node.find(key).text=str(row[key])
        flags=node.find('flags')
        if flags is None:
            import xml.etree.ElementTree as ET
            flags=ET.SubElement(node,'flags')
        for key in FLAGS:flags.set(key,str(row['flags'][key]))
        for key in LABELS:
            old=node.findall(key);position=list(node).index(old[0]) if old else len(node)
            for child in old:node.remove(child)
            import xml.etree.ElementTree as ET
            for offset,value in enumerate(filter(None,(v.strip() for v in row[key].split(',')))):
                child=copy.deepcopy(old[offset]) if offset<len(old) else ET.Element(key)
                child.set('name',value);node.insert(position+offset,child)
        result.append(node)
    index=0
    for position,node in enumerate(list(root)):
        if node.tag=='type':
            root.remove(node)
            if index<len(result):root.insert(position,result[index]);index+=1
    for node in result[index:]:root.append(node)
    text=xml_text(root)
    if len(text.encode('utf-8'))>MAX_BYTES:raise ValueError('Edited XML exceeds 8 MB.')
    return text

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(data,encoding='utf-8');temp.replace(path)

class LootStore:
    def __init__(self,home):
        self.base=Path(home)/'loot_projects';self.base.mkdir(parents=True,exist_ok=True);self.active=None
        try:self.load(json.loads((self.base/'active.json').read_text())['id'])
        except (OSError,ValueError,KeyError):pass
    def folder(self,identity):
        if not isinstance(identity,str) or not re.fullmatch(r'[a-f0-9-]{36}',identity):raise ValueError('Invalid project ID.')
        return self.base/identity
    def meta(self,identity):return json.loads((self.folder(identity)/'project.json').read_text('utf-8'))
    def commit(self,meta):
        atomic(self.folder(meta['id'])/'project.json',json.dumps(meta));atomic(self.base/'active.json',json.dumps({'id':meta['id']}));self.active=meta
    def create(self,text,title,target=None):
        rows=parse_types(text);p=dict(id=str(uuid.uuid4()),title=title,rev=0,revisions=[0],modified=time.strftime('%Y-%m-%dT%H:%M:%S'),target=target)
        folder=self.folder(p['id']);atomic(folder/'original.xml',text);atomic(folder/'revision-0.json',json.dumps(rows));self.commit(p);return self.state()
    def rows(self,p,rev):
        if type(rev) is not int or rev not in p['revisions']:raise ValueError('Saved revision not found.')
        return json.loads((self.folder(p['id'])/f'revision-{rev}.json').read_text('utf-8'))
    def state(self):
        if self.active is None:return dict(id='empty',title='Import XML or open the active mission',rev=0,revisions=[],modified='',rows=[],originalRows=[])
        return dict(self.active,rows=self.rows(self.active,self.active['rev']),originalRows=parse_types((self.folder(self.active['id'])/'original.xml').read_text('utf-8')))
    def load(self,identity,rev=None):
        p=self.meta(identity)
        if rev is not None:p['rev']=rev
        self.rows(p,p['rev']);self.commit(p);return self.state()
    def save(self,rows):
        validate_rows(rows)
        if self.active is None:raise ValueError('Import XML or open a mission first.')
        p=self.active
        if rows==self.rows(p,p['rev']):return {'data':'Already up-to-date'}
        self.xml(rows=rows);rev=max(p['revisions'])+1;atomic(self.folder(p['id'])/f'revision-{rev}.json',json.dumps(rows));self.commit(dict(p,rev=rev,revisions=p['revisions']+[rev],modified=time.strftime('%Y-%m-%dT%H:%M:%S')));return {'data':'Saved project revision '+str(rev)}
    def step(self,delta):
        if self.active is None:raise ValueError('No open project.')
        p=self.active;i=p['revisions'].index(p['rev'])+delta
        if not 0<=i<len(p['revisions']):raise ValueError('No further saved revisions.')
        self.load(p['id'],p['revisions'][i]);return dict(data=json.dumps(self.rows(self.active,self.active['rev'])),addon='Loaded saved revision '+str(self.active['rev']))
    def list(self):
        result=[]
        for folder in self.base.iterdir():
            if folder.is_dir():
                try:result.append(self.meta(folder.name))
                except (ValueError,OSError):pass
        return sorted(result,key=lambda p:p['modified'],reverse=True)
    def xml(self,identity=None,rev=None,rows=None):
        p=self.meta(identity) if identity else self.active
        if p is None:raise ValueError('No open project.')
        return export_types((self.folder(p['id'])/'original.xml').read_text('utf-8'),rows if rows is not None else self.rows(p,p['rev'] if rev is None else rev))
