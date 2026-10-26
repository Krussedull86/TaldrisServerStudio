"""Replace only the manager agent; running DayZ processes remain independent."""
import json,os,subprocess,sys,time
from pathlib import Path
from release_info import VERSION,BUILD

def repair(home,client,timeout=60):
    if not getattr(sys,'frozen',False):raise ValueError('Agentbytte brukes fra Windows-EXE. Start kildekodeagenten på nytt ved utvikling.')
    snapshot=client.call('snapshot')
    if any(v.get('busy') for v in snapshot['runtime'].values()) or any(j['status'] in ('queued','running') for j in snapshot['jobs']):raise ValueError('Vent til SteamCMD, backup og andre kølagte jobber er ferdige før agentbyttet.')
    home=Path(home)
    if snapshot.get('service'):
        from windows_service import install_service
        install_service(home)
    else:
        identity=json.loads((home/'agent.json').read_text('utf-8'));client.call('shutdown')
        subprocess.Popen([sys.executable,'--agent','--home',str(home),'--wait-agent',str(int(identity['pid'])),str(float(identity['created']))],cwd=str(home),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0),close_fds=True,env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        try:
            current=client.call('snapshot',timeout=1)
            if current.get('version')==VERSION and current.get('build')==BUILD:return f'Bakgrunnsagent oppdatert til {VERSION} / bygg {BUILD}. DayZ-prosessene er ikke stoppet.'
        except (OSError,ValueError):pass
        time.sleep(.3)
    raise ValueError('Agentbyttet ble ikke bekreftet. Se host.log. DayZ-prosessene er ikke tvangsstoppet.')
