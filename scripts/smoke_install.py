"""Exercise the real packaged Windows installer on an isolated CI runner."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
import winreg
import win32com.client

REGKEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\TaldrisServerStudio'
def smoke(exe):
    shell=win32com.client.Dispatch('WScript.Shell');links=[Path(shell.SpecialFolders('Programs'))/'Taldris Server Studio'/'Taldris Server Studio.lnk',Path(shell.SpecialFolders('Desktop'))/'Taldris Server Studio.lnk']
    if any(p.exists() for p in links):raise RuntimeError('Use an isolated runner without an existing Taldris installation.')
    with tempfile.TemporaryDirectory() as folder:
        base=Path(folder);home=base/'data';home.mkdir();sentinel=home/'keep-server-data.txt';sentinel.write_text('keep')
        env={**os.environ,'LOCALAPPDATA':folder};root=base/'Programs/TaldrisServerStudio'
        try:
            for _ in range(2):subprocess.run([str(exe),'--install-only','--home',str(home)],env=env,check=True,timeout=90)
            info=json.loads((home/'installation.json').read_text());assert Path(info['initial_exe']).is_file();assert Path(info['launcher']).is_file()
            for link in links:
                assert link.is_file();shortcut=shell.CreateShortcut(str(link));assert Path(shortcut.TargetPath)==Path(info['launcher']);assert str(home) in shortcut.Arguments
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,REGKEY) as key:assert winreg.QueryValueEx(key,'DisplayName')[0]=='Taldris Server Studio'
            subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'Avinstaller.ps1')],check=True,timeout=30)
            assert sentinel.read_text()=='keep';assert Path(info['initial_exe']).is_file();assert not root.exists();assert not (home/'installation.json').exists();assert not any(p.exists() for p in links)
            print('Packaged per-user installation, repeat installation, Windows shortcuts, registration and data-preserving uninstall passed.')
        finally:
            for link in links:link.unlink(missing_ok=True)
            try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,REGKEY)
            except FileNotFoundError:pass
if __name__=='__main__':smoke(Path(sys.argv[1]).resolve())
