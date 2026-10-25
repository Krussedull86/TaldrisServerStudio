"""Build and publish immutable releases. No user server/mod data is packaged."""
import hashlib,json,os,re,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def gh(*args):return subprocess.check_output(['gh',*args],text=True).strip()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def stamp():
    import release_info
    build=int(os.environ['BUILD']); repo=os.environ['REPOSITORY']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Invalid GitHub repository')
    (ROOT/'release_info.py').write_text(f'VERSION = {release_info.VERSION!r}\nBUILD = {build}\nREPOSITORY = {repo!r}\n',encoding='utf-8')
def package():
    import release_info as v
    out=ROOT/'release_output'; out.mkdir(exist_ok=True)
    binary=ROOT/'dist'/'TaldrisServerStudio.exe'
    if not binary.is_file():raise ValueError('Missing Windows executable')
    target=out/'TaldrisServerStudio-Windows.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(binary,binary.name); z.write(ROOT/'LES_MEG.md','LES_MEG.md'); z.write(ROOT/'DRIFT_DISCORD_EDITORER.md','DRIFT_DISCORD_EDITORER.md')
    info=dict(version=v.VERSION,build=v.BUILD,sha256=sha(target),size=target.stat().st_size,asset=target.name)
    (out/'build.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    (out/'SHA256SUMS.txt').write_text(info['sha256']+'  '+target.name+'\n',encoding='utf-8')
def publish_dev():
    out=ROOT/'release_output'; info=json.loads((out/'build.json').read_text())
    tag=f"dev-v{info['version']}.b{info['build']}"
    gh('release','create',tag,*[str(p) for p in sorted(out.iterdir())],'--target',os.environ['COMMIT'],'--title',f"Dev {info['version']} • bygg {info['build']}",'--notes','Automatisk dev-utgave. Stable er uendret.','--prerelease','--latest=false')
def promote():
    tag=os.environ['DEV_TAG']
    if not re.fullmatch(r'dev-v\d+\.\d+\.\d+\.b\d+',tag):raise ValueError('Invalid dev tag')
    source=json.loads(gh('api',f'repos/{os.environ["GH_REPO"]}/releases/tags/{tag}'))
    if not source.get('prerelease') or source.get('draft'):raise ValueError('Source must be a published dev prerelease')
    out=ROOT/'release_output'; out.mkdir(exist_ok=True)
    gh('release','download',tag,'--dir',str(out),'--pattern','TaldrisServerStudio-Windows.zip','--pattern','build.json','--pattern','SHA256SUMS.txt')
    info=json.loads((out/'build.json').read_text())
    if tag!=f"dev-v{info['version']}.b{int(info['build'])}":raise ValueError('Dev tag and metadata disagree')
    binary=out/'TaldrisServerStudio-Windows.zip'
    if sha(binary)!=info['sha256'] or binary.stat().st_size!=int(info['size']):raise ValueError('Checksum mismatch')
    stable=tag.removeprefix('dev-')
    # Use exact commit resolved from source tag, not a branch name or latest dev head.
    commit=gh('api',f'repos/{os.environ["GH_REPO"]}/commits/{tag}','--jq','.sha')
    gh('release','create',stable,*[str(p) for p in sorted(out.iterdir())],'--target',commit,'--title',f"Stable {info['version']} • bygg {info['build']}",'--notes',f'Godkjent fra {tag}. Samme Windows-pakke og SHA-256 som testutgaven.','--latest')
if __name__=='__main__':
    actions={'stamp':stamp,'package':package,'publish-dev':publish_dev,'promote':promote}
    actions[sys.argv[1]]()
