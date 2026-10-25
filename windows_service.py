"""Native SCM host and explicit elevated installation; DayZ survives agent stop."""
import base64,json,os,shutil,subprocess,sys,threading,time
from pathlib import Path
from windows_firewall import ps_quote,encoded
NAME='TaldrisServerStudioAgent'


def install_service(home,source=None):
    if sys.platform!='win32' or not getattr(sys,'frozen',False):raise ValueError('Tjenesteinstallasjon krever den pakkede Windows-EXE-en.')
    from release_info import VERSION,BUILD
    from host_api import AgentClient
    home=Path(home).resolve();target=home/'agent_versions'/f'{VERSION}-b{BUILD}'/'TaldrisAgent.exe';target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():shutil.copy2(source or sys.executable,target)
    # Shared data must remain private but readable by both owner and SYSTEM.
    from host_security import protect_file
    protect_file(home)
    try:AgentClient(home).call('shutdown')
    except (OSError,ValueError) as error:
        if 'Vent til' in str(error):raise
    command=subprocess.list2cmdline([str(target),'--windows-service','--home',str(home)])
    script=f"""$ErrorActionPreference='Stop'
$existing=Get-Service -Name '{NAME}' -ErrorAction SilentlyContinue
if ($existing -and $existing.Status -ne 'Stopped') {{ Stop-Service -Name '{NAME}'; (Get-Service '{NAME}').WaitForStatus('Stopped',[TimeSpan]::FromSeconds(45)) }}
if ($existing) {{ & sc.exe config '{NAME}' binPath= {ps_quote(command)} start= auto | Out-Null }}
else {{ & sc.exe create '{NAME}' binPath= {ps_quote(command)} start= auto DisplayName= 'Taldris Server Studio Agent' | Out-Null }}
if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}
& sc.exe failure '{NAME}' reset= 86400 actions= restart/10000/restart/30000 | Out-Null
Start-Service -Name '{NAME}'
(Get-Service '{NAME}').WaitForStatus('Running',[TimeSpan]::FromSeconds(60))
"""
    ps=str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe')
    outer=f"$ErrorActionPreference='Stop'; try {{ $p=Start-Process -FilePath {ps_quote(ps)} -ArgumentList '-NoProfile -NonInteractive -EncodedCommand {encoded(script)}' -Verb RunAs -Wait -PassThru; exit $p.ExitCode }} catch {{ exit 1 }}"
    result=subprocess.run([ps,'-NoProfile','-NonInteractive','-EncodedCommand',encoded(outer)],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=150)
    if result.returncode:raise ValueError('Windows-tjenesten ble ikke installert/startet. Godta administratorforespørselen og kontroller Windows Hendelsesliste. DayZ er ikke stoppet.')
    return 'Windows-tjenesten er installert. Agenten starter med Windows og kjører etter RDP-avlogging.'


def run_service(home):
    import servicemanager,win32service,win32serviceutil
    class Service(win32serviceutil.ServiceFramework):
        _svc_name_=NAME;_svc_display_name_='Taldris Server Studio Agent';_svc_description_='DayZ drift, Discord, oppdateringer og restarter uten åpent programvindu.'
        def __init__(self,args):super().__init__(args);self.stop_request=threading.Event();self.finished=threading.Event()
        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING);self.stop_request.set()
            def heartbeat():
                while not self.finished.wait(5):self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING,waitHint=15000)
            threading.Thread(target=heartbeat,daemon=True).start()
        def SvcDoRun(self):
            from host_api import serve
            try:serve(home,service=True,external_stop=self.stop_request)
            except Exception as error:servicemanager.LogErrorMsg('Taldris agent: '+str(error));raise
            finally:self.finished.set()
    servicemanager.Initialize();servicemanager.PrepareToHostSingle(Service);servicemanager.StartServiceCtrlDispatcher()


def replace_running_service(home,source):
    import win32service,win32serviceutil
    from release_info import VERSION,BUILD
    home=Path(home).resolve();target=home/'agent_versions'/f'{VERSION}-b{BUILD}'/'TaldrisAgent.exe';target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():shutil.copy2(source,target)
    scm=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
    handle=win32service.OpenService(scm,NAME,win32service.SERVICE_CHANGE_CONFIG)
    try:win32service.ChangeServiceConfig(handle,win32service.SERVICE_NO_CHANGE,win32service.SERVICE_NO_CHANGE,win32service.SERVICE_NO_CHANGE,subprocess.list2cmdline([str(target),'--windows-service','--home',str(home)]),None,0,None,None,None,None)
    finally:win32service.CloseServiceHandle(handle);win32service.CloseServiceHandle(scm)
    win32serviceutil.StopService(NAME);win32serviceutil.WaitForServiceStatus(NAME,win32service.SERVICE_STOPPED,60);win32serviceutil.StartService(NAME)
