"""Build and publish immutable releases. No user server/mod data is packaged."""
import hashlib,json,os,re,shutil,subprocess,sys,zipfile
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
    shutil.copy2(binary,out/'TaldrisServerStudio-Setup.exe')
    shutil.copy2(binary,out/'CruzDoodelZServerStudio-Setup.exe')
    shutil.copy2(binary,out/'DZSA-Tools-Setup.exe')
    target=out/'TaldrisServerStudio-Windows.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(binary,binary.name); z.writestr('LES_MEG.md',(ROOT/'LES_MEG.md').read_text('utf-8')+'\n\n'+(ROOT/'DRIFT_DISCORD_EDITORER.md').read_text('utf-8')+'\n\n'+(ROOT/'CHANGES_0.10.0.md').read_text('utf-8')+'\n\n'+(ROOT/'MOBILE_ACCESS.md').read_text('utf-8')+'\n\n'+(ROOT/'CHANGES_0.11.1.md').read_text('utf-8'))
    info=dict(version=v.VERSION,build=v.BUILD,sha256=sha(target),size=target.stat().st_size,asset=target.name)
    (out/'build.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    modzip=out/'CDSTelemetry-ServerMod.zip'
    with zipfile.ZipFile(modzip,'w',zipfile.ZIP_DEFLATED) as z:
        for file in sorted((ROOT/'dayz_telemetry/@CDSTelemetry').rglob('*')):
            if file.is_file():z.write(file,file.relative_to(ROOT/'dayz_telemetry').as_posix())
        z.write(ROOT/'dayz_telemetry/README.md','README.md');z.write(ROOT/'dayz_telemetry/config.example.json','config.example.json')
    files=[target,out/'TaldrisServerStudio-Setup.exe',out/'CruzDoodelZServerStudio-Setup.exe',out/'DZSA-Tools-Setup.exe',modzip]
    (out/'SHA256SUMS.txt').write_text(''.join(sha(file)+'  '+file.name+'\n' for file in files),encoding='utf-8')

def publish_dev():
    out=ROOT/'release_output'; info=json.loads((out/'build.json').read_text())
    tag=f"dev-v{info['version']}.b{info['build']}"
    gh('release','create',tag,*[str(p) for p in sorted(out.iterdir())],'--target',os.environ['COMMIT'],'--title',f"Dev {info['version']} • build {info['build']}",'--notes','Automatic dev release. Stable is unchanged.','--prerelease','--latest=false')
def promote():
    tag=os.environ['DEV_TAG']
    if not re.fullmatch(r'dev-v\d+\.\d+\.\d+\.b\d+',tag):raise ValueError('Invalid dev tag')
    source=json.loads(gh('api',f'repos/{os.environ["GH_REPO"]}/releases/tags/{tag}'))
    if not source.get('prerelease') or source.get('draft'):raise ValueError('Source must be a published dev prerelease')
    out=ROOT/'release_output'; out.mkdir(exist_ok=True)
    gh('release','download',tag,'--dir',str(out),'--pattern','TaldrisServerStudio-Windows.zip','--pattern','build.json','--pattern','SHA256SUMS.txt')
    if any(a['name']=='TaldrisServerStudio-Setup.exe' for a in source.get('assets',[])):gh('release','download',tag,'--dir',str(out),'--pattern','TaldrisServerStudio-Setup.exe')
    for name in ('CDSTelemetry-ServerMod.zip','CDS-Android-dev.apk','DZSA-Tools-Android-dev.apk'):
        if any(a['name']==name for a in source.get('assets',[])):gh('release','download',tag,'--dir',str(out),'--pattern',name)
    expected_sums={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (out/'SHA256SUMS.txt').read_text().splitlines() if '  ' in line}
    for file in out.iterdir():
        if file.name in expected_sums and sha(file)!=expected_sums[file.name]:raise ValueError('Asset checksum mismatch: '+file.name)
    info=json.loads((out/'build.json').read_text())
    if tag!=f"dev-v{info['version']}.b{int(info['build'])}":raise ValueError('Dev tag and metadata disagree')
    binary=out/'TaldrisServerStudio-Windows.zip'
    if sha(binary)!=info['sha256'] or binary.stat().st_size!=int(info['size']):raise ValueError('Checksum mismatch')
    setup=out/'TaldrisServerStudio-Setup.exe'
    if setup.is_file():
        with zipfile.ZipFile(binary) as z:
            if sha(setup)!=hashlib.sha256(z.read('TaldrisServerStudio.exe')).hexdigest():raise ValueError('Installer and verified ZIP disagree')
        # Publish the branded installer from the verified bytes, including when
        # promoting an older dev release that only had the legacy filename.
        shutil.copy2(setup,out/'CruzDoodelZServerStudio-Setup.exe')
        shutil.copy2(setup,out/'DZSA-Tools-Setup.exe')
    files=sorted(p for p in out.iterdir() if p.suffix in ('.exe','.zip','.apk'))
    (out/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in files),encoding='utf-8')
    stable=tag.removeprefix('dev-')
    # Use exact commit resolved from source tag, not a branch name or latest dev head.
    commit=gh('api',f'repos/{os.environ["GH_REPO"]}/commits/{tag}','--jq','.sha')
    gh('release','create',stable,*[str(p) for p in sorted(out.iterdir())],'--target',commit,'--title',f"Stable {info['version']} • build {info['build']}",'--notes',f'Approved from {tag}. The same Windows package and SHA-256 as the dev release.','--latest')
if __name__=='__main__':
    actions={'stamp':stamp,'package':package,'publish-dev':publish_dev,'promote':promote}
    actions[sys.argv[1]]()
