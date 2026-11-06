"""Stable CDS icon and matching Windows identity for installed shortcuts."""
import hashlib,os,sys
from pathlib import Path

APP_ID='CruzDoodelZ.ServerStudio'

def refresh_shortcuts(root,home,launcher):
    if sys.platform!='win32':return
    import ctypes,pythoncom
    import win32com.client
    from win32com.shell import shell
    from win32com.propsys import propsys,pscon
    root=Path(root);launcher=Path(launcher).resolve()
    source=Path(__file__).resolve().parent/'assets/dzsa_tools.ico'
    raw=source.read_bytes();stamp=hashlib.sha256(raw).hexdigest()[:12]
    icon=root/('cds-'+stamp+'.ico');marker=root/'shell-identity.txt'
    root.mkdir(parents=True,exist_ok=True)
    if not icon.is_file():
        temp=icon.with_suffix('.tmp');temp.write_bytes(raw);temp.replace(icon)
    pythoncom.CoInitialize()
    try:
        ws=win32com.client.Dispatch('WScript.Shell')
        name='DZSA Tools'
        links=[Path(ws.SpecialFolders('Programs'))/name/(name+'.lnk'),Path(ws.SpecialFolders('Desktop'))/(name+'.lnk')]
        pinned=Path(os.environ.get('APPDATA',''))/'Microsoft/Internet Explorer/Quick Launch/User Pinned/TaskBar'
        if pinned.is_dir():links.extend(pinned.glob('*.lnk'))
        changed=False
        for path in links:
            if not path.is_file():continue
            # Only touch this installation's shortcuts, including existing pins.
            old=ws.CreateShortcut(str(path))
            if not old.TargetPath or Path(old.TargetPath).resolve()!=launcher:continue
            desired=str(icon)+',0'
            link=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink)
            persist=link.QueryInterface(pythoncom.IID_IPersistFile);persist.Load(str(path))
            store=link.QueryInterface(propsys.IID_IPropertyStore)
            current=store.GetValue(pscon.PKEY_AppUserModel_ID).GetValue()
            if old.IconLocation==desired and current==APP_ID and old.Description==name:continue
            link.SetDescription(name);link.SetIconLocation(str(icon),0)
            store.SetValue(pscon.PKEY_AppUserModel_ID,propsys.PROPVARIANTType(APP_ID));store.Commit();persist.Save(str(path),True);changed=True
        if changed or not marker.is_file() or marker.read_text('utf-8')!=stamp:
            ctypes.windll.shell32.SHChangeNotify(0x08000000,0,None,None)
            marker.write_text(stamp,encoding='utf-8')
    finally:pythoncom.CoUninitialize()
    return str(icon)
