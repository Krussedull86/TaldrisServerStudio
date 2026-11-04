"""Track one DayZ launch without treating successful process creation as readiness."""
import re,time
from pathlib import Path

def log_files(folder):
    folder=Path(folder)
    try:
        if not folder.is_dir():return []
        return [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ('.rpt','.log')]
    except OSError:return []

def snapshot(folder):
    result={}
    for path in log_files(folder):
        try:
            stat=path.stat(); result[str(path)]=(stat.st_size,stat.st_mtime_ns)
        except OSError:pass
    return result

def current_logs(record):
    baseline=record['baseline']; paths=[]
    for p in log_files(record['profiles']):
        try:
            stat=p.stat()
            if (stat.st_size,stat.st_mtime_ns)!=baseline.get(str(p)) and stat.st_mtime>=record['started_wall']-2:paths.append((stat.st_mtime,p))
        except OSError:pass
    return [p for _,p in sorted(paths,key=lambda item:item[0],reverse=True)]

def tail(path,limit=16000):
    with Path(path).open('rb') as f:f.seek(max(0,Path(path).stat().st_size-limit)); data=f.read()
    return data.decode('utf-8',errors='replace')

def error_excerpt(paths):
    candidates=sorted(paths,key=lambda p:(not p.name.lower().startswith('error'),p.suffix.lower()!='.rpt'))
    markers=re.compile(r'(error|cannot|can.t|failed|missing|not found|requires addon|compil|fatal|exception|address.*use)',re.I)
    for path in candidates:
        try:
            lines=[line.strip() for line in tail(path).splitlines() if markers.search(line)]
            if lines:return path,'\n'.join(lines[-6:])[:2400]
        except OSError:pass
    return None,''

def exit_label(code):
    value=int(code); unsigned=value&0xffffffff
    details={0xC0000135:'Windows could not find a required DLL/runtime.',0xC000007B:'Windows could not load an executable or DLL (invalid format).',0xC0000005:'The process stopped with a memory access violation.',0xC0000142:'Windows could not initialize a DLL.'}
    return f'{value} (0x{unsigned:08X})',details.get(unsigned,'')

def describe(record):
    pid=record['pid']; state=record.get('state','starting'); seconds=int(time.monotonic()-record['started'])
    if state=='exited':return f"STOPPED • PID {pid} • code {record['exit_label']} • after {record.get('uptime', seconds)} s"
    return f"{('STARTING' if seconds < 15 else 'PROCESS RUNNING')} • PID {pid} • {seconds} s • readiness for players is not confirmed"
