"""Public GitHub Release channels and checksum-verified portable downloads."""
import hashlib,json,re,zipfile
from pathlib import Path
from urllib.request import Request,urlopen
from network_tls import tls_context
from urllib.error import HTTPError
from urllib.parse import urlparse
from release_info import VERSION,BUILD
ASSET='TaldrisServerStudio-Windows.zip'

def repository(value):
    value=value.strip().removesuffix('.git').rstrip('/')
    if value.startswith('https://github.com/'):value=value[len('https://github.com/'):]
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',value):raise ValueError('Oppgi GitHub-repo som eier/navn, eller en GitHub-lenke.')
    if any(part in ('.','..') for part in value.split('/')):raise ValueError('Ugyldig repo.')
    return value

def get_json(url):
    req=Request(url,headers={'User-Agent':'TaldrisServerStudio','Accept':'application/vnd.github+json'})
    try:
        with urlopen(req,timeout=30,context=tls_context()) as r:raw=r.read(4*1024*1024+1)
    except HTTPError as e:
        if e.code==404:raise ValueError('Fant ikke offentlig repo eller publisert utgave for kanalen.')
        if e.code==403:raise ValueError('GitHub avviste forespørselen eller har nådd API-grensen. Prøv senere.')
        raise
    if len(raw)>4*1024*1024:raise ValueError('Oppdateringssvaret er for stort.')
    return json.loads(raw)

def asset_url(repo,tag,name):return f'https://github.com/{repo}/releases/download/{tag}/{name}'

def check(repo,channel,fetch=get_json):
    repo=repository(repo)
    if channel not in ('dev','stable'):raise ValueError('Ukjent oppdateringskanal.')
    releases=fetch(f'https://api.github.com/repos/{repo}/releases?per_page=100') if channel=='dev' else [fetch(f'https://api.github.com/repos/{repo}/releases/latest')]
    prefix='dev-v' if channel=='dev' else 'v'; candidates=[]
    for r in releases:
        tag=r.get('tag_name',''); match=re.fullmatch(re.escape(prefix)+r'(\d+)\.(\d+)\.(\d+)\.b(\d+)',tag)
        if match and not r.get('draft') and bool(r.get('prerelease'))==(channel=='dev'):candidates.append((tuple(map(int,match.groups())),r))
    if not candidates:raise ValueError('Ingen publisert '+channel+'-utgave finnes ennå.')
    version,r=max(candidates,key=lambda x:x[0]); tag=r['tag_name']; assets={a['name']:a for a in r.get('assets',[])}
    if ASSET not in assets or 'build.json' not in assets:raise ValueError('Utgaven mangler Windows-pakke eller kontrollsum.')
    for name in [ASSET,'build.json']:
        if assets[name].get('browser_download_url')!=asset_url(repo,tag,name):raise ValueError('Uventet nedlastingsadresse i utgaven.')
    info=fetch(asset_url(repo,tag,'build.json'))
    if info.get('asset')!=ASSET or not re.fullmatch('[0-9a-f]{64}',info.get('sha256','')):raise ValueError('Ugyldige oppdateringsdata.')
    expected='.'.join(str(n) for n in version[:3])
    if info.get('version')!=expected or int(info.get('build',-1))!=version[3]:raise ValueError('Versjon og kontrollsumfil stemmer ikke overens.')
    size=int(info.get('size',0))
    if not 0<size<=500*1024*1024:raise ValueError('Ugyldig pakkestørrelse.')
    current=tuple(map(int,VERSION.split('.')))+(BUILD,)
    return dict(info,tag=tag,channel=channel,repository=repo,url=asset_url(repo,tag,ASSET),newer=version>current)

def download(update,directory):
    repo=repository(update['repository']); tag=update['tag']
    if not re.fullmatch(r'(dev-)?v\d+\.\d+\.\d+\.b\d+',tag) or update['url']!=asset_url(repo,tag,ASSET):raise ValueError('Ugyldig oppdateringsadresse.')
    out=Path(directory); out.mkdir(parents=True,exist_ok=True); target=out/(tag+'-'+ASSET); part=target.with_suffix('.partial'); total=0; digest=hashlib.sha256()
    try:
        request=Request(update['url'],headers={'User-Agent':'TaldrisServerStudio'})
        with urlopen(request,timeout=60,context=tls_context()) as response,part.open('wb') as f:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                total+=len(chunk)
                if total>min(int(update['size']),500*1024*1024):raise ValueError('Nedlastingen er større enn oppgitt.')
                f.write(chunk); digest.update(chunk)
        if total!=int(update['size']) or digest.hexdigest()!=update['sha256']:raise ValueError('Kontrollsummen stemmer ikke. Pakken forkastes.')
        with zipfile.ZipFile(part) as z:
            if 'TaldrisServerStudio.exe' not in z.namelist():raise ValueError('Windows-programmet mangler i pakken.')
        part.replace(target); return str(target)
    finally:part.unlink(missing_ok=True)


def stage_install(update, archive, home):
    """Verify again, extract a bounded allowlist, never overwrite a running EXE."""
    archive=Path(archive); home=Path(home)
    if archive.stat().st_size!=int(update['size']) or hashlib.sha256(archive.read_bytes()).hexdigest()!=update['sha256']:
        raise ValueError('Oppdateringspakken er endret etter nedlasting.')
    tag=update['tag']
    if not re.fullmatch(r'(dev-)?v\d+\.\d+\.\d+\.b\d+',tag):raise ValueError('Ugyldig versjon.')
    target=home/'program_versions'/tag
    target.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)-{'TaldrisServerStudio.exe','LES_MEG.md','DRIFT_DISCORD_EDITORER.md'}:
            raise ValueError('Uventet innhold i oppdateringspakken.')
        for item in z.infolist():
            if item.file_size>600*1024*1024:raise ValueError('Utpakket fil er for stor.')
        if 'TaldrisServerStudio.exe' not in names:raise ValueError('Programfilen mangler.')
        for name in names:
            dest=target/name
            # A prior verified installation may already be running; never replace it.
            content=z.read(name)
            if dest.exists():
                if dest.read_bytes()!=content:raise ValueError('Versjonsmappen har annet innhold. Oppdateringen avbrytes.')
            else:
                tmp=dest.with_suffix('.partial'); tmp.write_bytes(content); tmp.replace(dest)
    exe=target/'TaldrisServerStudio.exe'
    if not exe.read_bytes().startswith(b'MZ'):raise ValueError('Ugyldig Windows-program.')
    return str(exe)
