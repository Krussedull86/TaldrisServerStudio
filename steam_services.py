"""Steam transport, validated public Workshop metadata and server provisioning.
Network calls live outside the UI thread. Credentials are never part of this module.
"""
import io, json, os, re, stat, tempfile, zipfile
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen
from network_tls import tls_context
from html.parser import HTMLParser

STEAMCMD_URL='https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip'
DAYZ_APP=223350
WORKSHOP_APP=221100
MAX_RESPONSE=12*1024*1024

def read_url(url,data=None,limit=MAX_RESPONSE):
    req=Request(url,data=data,headers={'User-Agent':'TaldrisServerStudio/0.3','Accept-Language':'en-US,en;q=0.9'})
    with urlopen(req,timeout=40,context=tls_context()) as response:
        raw=response.read(limit+1)
        if len(raw)>limit:raise ValueError('Svaret fra Steam er for stort.')
        return raw

def workshop_id(value):
    value=value.strip()
    if re.fullmatch(r'[1-9][0-9]{0,19}',value):return value
    url=urlparse(value)
    if url.scheme not in ('http','https') or url.hostname not in ('steamcommunity.com','www.steamcommunity.com'):raise ValueError('Bruk Workshop-ID eller en steamcommunity.com-lenke.')
    wid=parse_qs(url.query).get('id',[''])[0]
    if not re.fullmatch(r'[1-9][0-9]{0,19}',wid):raise ValueError('Lenken mangler gyldig Workshop-ID.')
    return wid

def api(method,params):
    raw=read_url('https://api.steampowered.com/ISteamRemoteStorage/'+method+'/v1/',urlencode(params).encode())
    try:return json.loads(raw)['response']
    except (ValueError,KeyError,TypeError):raise ValueError('Steam returnerte et ukjent API-svar. Prøv igjen senere.')

def details(ids):
    ids=list(dict.fromkeys(workshop_id(str(w)) for w in ids))
    if len(ids)>100:raise ValueError('Hent høyst 100 mods om gangen.')
    if not ids:return []
    params={'itemcount':len(ids)}; params.update({f'publishedfileids[{i}]':w for i,w in enumerate(ids)})
    data=api('GetPublishedFileDetails',params).get('publishedfiledetails',[])
    by_id={str(d.get('publishedfileid')):d for d in data}; result=[]
    for wid in ids:
        d=by_id.get(wid,{})
        if int(d.get('result',0))!=1:raise ValueError('Workshop-elementet er privat, slettet eller utilgjengelig: '+wid)
        if int(d.get('consumer_app_id',0))!=WORKSHOP_APP:raise ValueError('Dette elementet tilhører ikke DayZ: '+wid)
        result.append(dict(id=wid,title=d.get('title',wid),updated=int(d.get('time_updated',0)),size=int(d.get('file_size',0)),file_type=int(d.get('file_type',0)),description=d.get('description',''),url='https://steamcommunity.com/sharedfiles/filedetails/?id='+wid))
    return result

def collection(value):
    wid=workshop_id(value); parent=details([wid])[0]
    if parent['file_type']!=2:raise ValueError('Dette er ikke en Workshop-samling. Bruk «Legg til via ID» for enkeltmods.')
    data=api('GetCollectionDetails',{'collectioncount':1,'publishedfileids[0]':wid}).get('collectiondetails',[])
    if not data or int(data[0].get('result',0))!=1:raise ValueError('Kunne ikke lese samlingen.')
    ids=[str(c['publishedfileid']) for c in data[0].get('children',[])]
    if len(ids)>100:raise ValueError('Denne utgaven støtter samlinger med høyst 100 direkte elementer.')
    items=details(ids)
    if any(x['file_type']!=0 for x in items):raise ValueError('Samlingen inneholder undersamlinger eller andre elementtyper. Importer enkeltmods separat.')
    return items

class BrowseParser(HTMLParser):
    """Public browse HTML, with an explicit failure if Steam changes layout."""
    def __init__(self):
        super().__init__(convert_charrefs=True); self.items=[]; self.current=None; self.title_depth=0; self.depth=0; self.title=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); classes=a.get('class','').split()
        if tag=='a' and 'sharedfiles/filedetails' in a.get('href',''):
            try:wid=workshop_id(a['href'])
            except ValueError:return
            if self.current is None or self.current['id']!=wid:self.current={'id':wid,'title':''}; self.items.append(self.current)
        if self.title_depth:self.title_depth+=1
        if 'workshopItemTitle' in classes and self.current is not None:self.title_depth=1; self.title=[]
    def handle_data(self,data):
        if self.title_depth:self.title.append(data)
    def handle_endtag(self,tag):
        if self.title_depth:
            self.title_depth-=1
            if not self.title_depth and self.current is not None:self.current['title']=''.join(self.title).strip()

def browse_ids(raw):
    """Read Valve's current SSR JSON, with a legacy HTML fallback. Never execute JS."""
    match=re.search(r'<script\b(?=[^>]*\bid=[\"\']valve-ssr-data[\"\'])[^>]*>(.*?)</script>',raw,re.S|re.I)
    if match:
        try:
            data=json.loads(match.group(1)); context=data.get('renderContext',{}); query=context.get('queryData',{})
            if isinstance(query,str):query=json.loads(query)
            for entry in query.get('queries',[]):
                payload=entry.get('state',{}).get('data',{})
                if not isinstance(payload,dict) or 'results' not in payload or 'current_page' not in payload:continue
                rows=payload['results']
                if not rows and payload.get('total_count')==0:return []
                if rows and all('publishedfileid' in row and 'consumer_appid' in row for row in rows):
                    return list(dict.fromkeys(str(row['publishedfileid']) for row in rows if int(row['consumer_appid'])==WORKSHOP_APP and int(row.get('file_type',0))==0))[:30]
        except (ValueError,KeyError,TypeError):pass
    parser=BrowseParser(); parser.feed(raw)
    ids=list(dict.fromkeys(x['id'] for x in parser.items if x['title']))[:30]
    if ids:return ids
    if 'No items matching' in raw:return []
    raise ValueError('Kunne ikke lese Workshop-søket. Steam kan ha endret siden eller kreve samtykke. Bruk ID/lenke, eller åpne Workshop-nettsiden.')

def search(text,page=1):
    q=urlencode(dict(appid=WORKSHOP_APP,searchtext=text,browsesort='textsearch' if text else 'trend',section='items',actualsort='textsearch' if text else 'trend',p=int(page),numperpage=30))
    raw=read_url('https://steamcommunity.com/workshop/browse/?'+q).decode('utf-8',errors='replace')
    return [d for d in details(browse_ids(raw)) if d['file_type']==0]

def install_steamcmd(directory,report=lambda s:None,fetch=read_url):
    """Download Valve's official bootstrap; do not overwrite an existing install."""
    target=Path(directory).resolve(); exe=target/'steamcmd.exe'
    if exe.is_file():report('SteamCMD finnes allerede.'); return str(exe)
    target.mkdir(parents=True,exist_ok=True); report('Laster ned SteamCMD fra Valve …')
    raw=fetch(STEAMCMD_URL,limit=50*1024*1024)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos=archive.infolist()
        if sum(i.file_size for i in infos)>100*1024*1024:raise ValueError('SteamCMD-arkivet er for stort.')
        for item in infos:
            p=Path(item.filename.replace('\\','/'))
            if p.is_absolute() or '..' in p.parts or ':' in item.filename or stat.S_ISLNK(item.external_attr>>16):raise ValueError('Utrygg filsti i SteamCMD-arkivet.')
        if not any(i.filename.lower()=='steamcmd.exe' for i in infos):raise ValueError('SteamCMD-arkivet mangler steamcmd.exe.')
        with tempfile.TemporaryDirectory(dir=target,prefix='.bootstrap-') as temp:
            archive.extractall(temp)
            # Valve currently ships one bootstrap executable. Keep other existing files untouched.
            src=next(p for p in Path(temp).iterdir() if p.name.lower()=='steamcmd.exe')
            if src.read_bytes()[:2]!=b'MZ':raise ValueError('SteamCMD er ikke en gyldig Windows-programfil.')
            if not exe.exists():os.replace(src,exe)
    report('SteamCMD lastet ned. Første kjøring oppdaterer SteamCMD automatisk.'); return str(exe)

def cfg_string(value):
    if any(c in value for c in ['"','\\','\n','\r','\x00']):raise ValueError('Navn og passord kan ikke inneholde anførselstegn, linjeskift eller omvendt skråstrek.')
    return '"'+value+'"'

def provision(profile,name,players,mission):
    from core import local_path,validate
    validate(profile)
    if not 1<=int(players)<=127:raise ValueError('Velg 1–127 spillerplasser.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',mission):raise ValueError('Ugyldig mission-navn.')
    root=Path(profile['root']); mission_dir=local_path(root,'mpmissions/'+mission)
    if not mission_dir.is_dir():raise ValueError('Mission finnes ikke etter installasjon: '+str(mission_dir))
    config=local_path(root,profile['config'])
    if config.exists():raise ValueError('Konfigurasjonen finnes allerede. Bruk konfigurasjonseditoren for endringer.')
    root.mkdir(parents=True,exist_ok=True); config.parent.mkdir(parents=True,exist_ok=True); local_path(root,profile['profiles']).mkdir(parents=True,exist_ok=True)
    text=(f'hostname = {cfg_string(name)};\nmaxPlayers = {int(players)};\nsteamQueryPort = {int(profile["port"])+3};\nverifySignatures = 2;\nforceSameBuild = 1;\n'
          'disableVoN = 0;\nvonCodecQuality = 20;\ndisable3rdPerson = 0;\ndisableCrosshair = 0;\n'
          'serverTime = "SystemTime";\nserverTimeAcceleration = 1;\nserverTimePersistent = 1;\n'
          'class Missions\n{\n class DayZ\n {\n  template = '+cfg_string(mission)+';\n };\n};\n')
    # Exclusive create: never replace a file generated by another process.
    with config.open('x',encoding='utf-8') as f:f.write(text)
    return str(config)

def steam_arguments(profile,kind,ids=None,verify=True):
    from core import validate
    validate(profile)
    user=profile.get('steam_user','').strip() if profile.get('login_mode','anonymous')=='account' else 'anonymous'
    if not user or not re.fullmatch(r'[A-Za-z0-9_@.\-]+',user):raise ValueError('Oppgi gyldig Steam-brukernavn i veiviseren.')
    args=['+@ShutdownOnFailedCommand','1','+@NoPromptForPassword','0','+force_install_dir',str(Path(profile['root']).resolve()),'+login',user]
    if kind in ('server','all'):
        args+=['+app_update',str(DAYZ_APP)]
        if verify:args+=['validate']
    if kind in ('mods','all'):
        ids=ids if ids is not None else [m['id'] for m in profile['mods'] if m.get('enabled',True) and m.get('id')]
        for wid in dict.fromkeys(ids):args+=['+workshop_download_item',str(WORKSHOP_APP),workshop_id(wid),'validate']
    return args+['+quit']

def result_summary(output,kind,ids,code,exe_exists=True):
    clean=re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',output)
    failed=bool(re.search(r'(ERROR!|FAILED\b|No subscription|Access Denied|Invalid Password|Invalid Login Auth Code|Rate Limit)',clean,re.I))
    server_ok=bool(re.search(r"Success!\s*App\s*'223350'\s*fully installed",clean,re.I)) and exe_exists
    downloaded={m.group(1) for m in re.finditer(r'Success\.\s*Downloaded item\s+(\d+)\b',clean,re.I)}
    expected=set(ids)
    ok=code==0 and not failed
    if kind in ('server','all'):ok=ok and server_ok
    if kind in ('mods','all'):ok=ok and expected.issubset(downloaded)
    if kind=='login':ok=ok and bool(re.search(r'(Logged in.*?OK|Logging in.*?OK|Waiting for user info.*?OK)',clean,re.I|re.S))
    if ok:return True,'SteamCMD bekreftet at jobben er fullført.'
    if re.search(r'(No subscription|Access Denied|Invalid Password|Invalid Login|FAILED.*log|Account Logon Denied)',clean,re.I):return False,'Steam avviste innlogging eller tilgang. Velg Steam-konto og prøv igjen. Workshop kan kreve en konto med DayZ-tilgang.'
    return False,'Jobben er ikke bekreftet fullført. Les SteamCMD-utdata. Ved anonym tilgangsfeil: velg Steam-konto og prøv igjen.'
