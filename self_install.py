"""Per-user Windows installation with a stable launcher and side-by-side versions."""
import hashlib,json,os,shutil,sys
from pathlib import Path
from release_info import VERSION,BUILD
from windows_firewall import ps_quote

NAME='Taldris Server Studio'
REGKEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\TaldrisServerStudio'

def read_install(home):
    path=Path(home)/'installation.json'
    return json.loads(path.read_text('utf-8')) if path.is_file() else None

def launcher_target(home):
    info=read_install(home)
    if not info or Path(sys.executable).resolve()!=Path(info['launcher']).resolve():return None
    active=Path(home)/'active_program.json'
    target=Path(json.loads(active.read_text('utf-8'))['exe']) if active.is_file() else Path(info['initial_exe'])
    target=target.resolve()
    if not target.is_relative_to((Path(home)/'program_versions').resolve()) or target.name!='TaldrisServerStudio.exe' or not target.is_file():raise ValueError('Installert programfil mangler. Installer programmet på nytt fra nedlastet EXE.')
    return target

def register_windows(root,home,launcher):
    import winreg
    import win32com.client
    import pythoncom
    pythoncom.CoInitialize()
    shell=win32com.client.Dispatch('WScript.Shell')
    links=[Path(shell.SpecialFolders('Programs'))/NAME/(NAME+'.lnk'),Path(shell.SpecialFolders('Desktop'))/(NAME+'.lnk')]
    for path in links:
        path.parent.mkdir(parents=True,exist_ok=True);shortcut=shell.CreateShortcut(str(path));shortcut.TargetPath=str(launcher);shortcut.Arguments='--home "'+str(home)+'"';shortcut.WorkingDirectory=str(root);shortcut.IconLocation=str(launcher)+',0';shortcut.Save()
    powershell=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    script=root/'Avinstaller.ps1'
    # Only installation files and our own shortcuts are removed. Agent, versions,
    # settings and DayZ data stay outside this folder and are never stopped.
    script.write_text("$ErrorActionPreference='Stop'\n"+'\n'.join('Remove-Item -LiteralPath '+ps_quote(p)+' -Force -ErrorAction SilentlyContinue' for p in links)+"\nRemove-Item -LiteralPath 'HKCU:\\"+REGKEY+"' -Recurse -Force -ErrorAction SilentlyContinue\nRemove-Item -LiteralPath "+ps_quote(Path(home)/'installation.json')+" -Force -ErrorAction SilentlyContinue\nSet-Location $env:TEMP\nRemove-Item -LiteralPath "+ps_quote(root)+" -Recurse -Force\n",encoding='utf-8-sig')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,REGKEY) as key:
        values={'DisplayName':NAME,'DisplayVersion':f'{VERSION} (bygg {BUILD})','Publisher':'Taldris','InstallLocation':str(root),'DisplayIcon':str(launcher),'UninstallString':f'"{powershell}" -NoProfile -ExecutionPolicy Bypass -File "{script}"'}
        for name,value in values.items():winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)
        for name in ('NoModify','NoRepair'):winreg.SetValueEx(key,name,0,winreg.REG_DWORD,1)
    del shell
    pythoncom.CoUninitialize()

def install(home):
    if sys.platform!='win32' or not getattr(sys,'frozen',False):raise ValueError('Installer fra den nedlastede Windows-EXE-filen.')
    home=Path(home).resolve();source=Path(sys.executable).resolve()
    root=(Path(os.environ['LOCALAPPDATA'])/'Programs'/'TaldrisServerStudio').resolve()
    if home==root or home.is_relative_to(root) or root.is_relative_to(home):raise ValueError('Datamappen må ligge utenfor programmets installasjonsmappe.')
    tag=f'v{VERSION}.b{BUILD}';target=home/'program_versions'/tag/'TaldrisServerStudio.exe';target.parent.mkdir(parents=True,exist_ok=True)
    def copy_once(src,dest):
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).digest()!=hashlib.sha256(src.read_bytes()).digest():raise ValueError('Versjonsmappen inneholder en annen programfil. Installer en nyere utgave.')
            return
        temp=dest.with_suffix('.installing');shutil.copy2(src,temp);temp.replace(dest)
    copy_once(source,target);root.mkdir(parents=True,exist_ok=True);launcher=root/'TaldrisServerStudio.exe'
    # The launcher only forwards to the active version; never replace a running file.
    if not launcher.exists():copy_once(source,launcher)
    register_windows(root,home,launcher)
    info=dict(launcher=str(launcher),initial_exe=str(target),version=VERSION,build=BUILD)
    from host_security import atomic_private
    atomic_private(home/'installation.json',info);(home/'portable_mode.json').unlink(missing_ok=True)
    # Preserve a newer agent-selected version if an older installer is opened.
    active=home/'active_program.json'
    previous=json.loads(active.read_text('utf-8')).get('exe','') if active.is_file() else ''
    import re
    match=re.search(r'(?:dev-)?v(\d+\.\d+\.\d+)\.b(\d+)',Path(previous).parent.name)
    if not match or tuple(map(int,match[1].split('.')))+(int(match[2]),)<=tuple(map(int,VERSION.split('.')))+(BUILD,):atomic_private(active,{'exe':str(target)})
    return json.loads(active.read_text('utf-8'))['exe']


def refresh_version(home):
    if sys.platform!='win32' or not read_install(home):return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,REGKEY,0,winreg.KEY_SET_VALUE) as key:winreg.SetValueEx(key,'DisplayVersion',0,winreg.REG_SZ,f'{VERSION} (bygg {BUILD})')
    except OSError:pass
