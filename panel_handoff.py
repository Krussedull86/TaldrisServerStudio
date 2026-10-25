"""Panel-only update handoff; no DayZ process is terminated."""
import json,re
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil


def wait_panel(pid,created,timeout=45):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        try:
            proc=psutil.Process(pid)
            if abs(proc.create_time()-created)>0.01 or not proc.is_running():return
        except psutil.NoSuchProcess:return
        time.sleep(.15)
    raise RuntimeError('Forrige kontrollpanel avsluttet ikke. Oppdateringen starter ikke et ekstra panel.')


def active_exe(home):
    path=Path(home)/'active_program.json'
    if not path.exists():return None
    info=json.loads(path.read_text('utf-8')); exe=Path(info['exe']).resolve()
    if not exe.is_relative_to((Path(home)/'program_versions').resolve()) or exe.name!='TaldrisServerStudio.exe' or not exe.is_file():raise ValueError('Ugyldig installert programsti.')
    from release_info import VERSION,BUILD
    match=re.search(r'(?:dev-)?v(\d+)\.(\d+)\.(\d+)\.b(\d+)',exe.parent.name)
    if match and tuple(map(int,match.groups()))<=tuple(map(int,VERSION.split('.')))+(BUILD,):return None
    return exe


def mark_active(home):
    exe=Path(sys.executable).resolve(); versions=(Path(home)/'program_versions').resolve()
    if not getattr(sys,'frozen',False) or not exe.is_relative_to(versions):return
    path=Path(home)/'active_program.json'; tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'exe':str(exe)}),encoding='utf-8'); tmp.replace(path)


def launch_handoff(exe,home):
    if not getattr(sys,'frozen',False):raise ValueError('Automatisk installasjon brukes fra Windows-EXE. Pakken er klargjort; kildekodekjøring oppdateres via Git.')
    me=psutil.Process()
    return subprocess.Popen([str(exe),'--home',str(home),'--wait-panel',str(me.pid),str(me.create_time())],cwd=str(Path(exe).parent),creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0),close_fds=True,env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
