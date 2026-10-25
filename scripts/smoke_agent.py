"""Run the packaged headless agent against an empty temporary home. No game starts."""
import os,subprocess,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from host_api import AgentClient


def smoke(command):
    with tempfile.TemporaryDirectory() as folder:
        proc=subprocess.Popen([*command,'--agent','--home',folder]);client=AgentClient(folder)
        try:
            deadline=time.monotonic()+50;snapshot=None
            while time.monotonic()<deadline:
                if proc.poll() is not None:raise RuntimeError('Agent exited early: '+str(proc.returncode))
                try:snapshot=client.call('snapshot',timeout=1);break
                except (OSError,ValueError):time.sleep(.25)
            if snapshot is None:raise RuntimeError('Agent did not expose its local API.')
            assert len(snapshot['state']['servers'])==1
            assert not any(item['running'] for item in snapshot['runtime'].values())
            client.call('shutdown');proc.wait(timeout=25)
            if proc.returncode:raise RuntimeError('Agent exited with '+str(proc.returncode))
            print('Headless agent API/start/stop smoke passed; no DayZ process launched.')
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=10)

if __name__=='__main__':
    smoke([str(Path(sys.argv[1]).resolve())] if len(sys.argv)>1 else [sys.executable,str(Path(__file__).resolve().parents[1]/'app.py')])
