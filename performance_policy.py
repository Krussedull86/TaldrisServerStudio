"""Per-profile process scheduling and optional Windows commit/CPU limits."""
import os,sys,copy
import psutil

PRIORITIES={'Idle':'IDLE_PRIORITY_CLASS','Below normal':'BELOW_NORMAL_PRIORITY_CLASS','Normal':'NORMAL_PRIORITY_CLASS','Above normal':'ABOVE_NORMAL_PRIORITY_CLASS','High':'HIGH_PRIORITY_CLASS'}
DEFAULTS=dict(priority='Normal',affinity=[],worker_count=0,fps_limit=0,cpu_budget=0,ram_warning_mb=0,ram_limit_mb=0)

def hardware():
    try:allowed=psutil.Process().cpu_affinity()
    except (AttributeError,psutil.Error):allowed=list(range(psutil.cpu_count() or 1))
    return dict(logical=psutil.cpu_count() or 1,physical=psutil.cpu_count(logical=False),allowed=allowed,total_ram_mb=int(psutil.virtual_memory().total/1024**2),windows=sys.platform=='win32')

def policy(profile):
    raw=profile.get('performance',{})
    if not isinstance(raw,dict) or set(raw)-set(DEFAULTS):raise ValueError('Invalid performance settings.')
    p={**DEFAULTS,**raw}
    if p['priority'] not in PRIORITIES:raise ValueError('Unknown process priority.')
    if not isinstance(p['affinity'],list) or len(p['affinity'])>256 or any(type(n) is not int or n<0 or n>255 for n in p['affinity']) or len(set(p['affinity']))!=len(p['affinity']):raise ValueError('CPU selection must contain unique logical CPU numbers.')
    for key,hi in [('worker_count',256),('fps_limit',200),('cpu_budget',100),('ram_warning_mb',4194304),('ram_limit_mb',4194304)]:
        if type(p[key]) is not int or not 0<=p[key]<=hi:raise ValueError(f'{key} must be 0–{hi}.')
    if 0<p['ram_limit_mb']<512:raise ValueError('A hard memory limit must be at least 512 MB.')
    if p['affinity'] and p['worker_count']>len(p['affinity']):raise ValueError('Worker count exceeds the selected logical CPUs.')
    if p['ram_warning_mb'] and p['ram_limit_mb'] and p['ram_warning_mb']>p['ram_limit_mb']:raise ValueError('The RAM warning threshold exceeds the hard limit.')
    return p

def launch_arguments(profile,args):
    p=policy(profile);out=list(args)
    for key,flag in [('worker_count','-cpuCount='),('fps_limit','-limitFPS=')]:
        if p[key]:
            if any(a.casefold().startswith(flag.casefold()) for a in out):raise ValueError('Remove '+flag+' from extra arguments before using Performance controls.')
            out.append(flag+str(p[key]))
    return out

class ProcessPolicies:
    def __init__(self):self.jobs={};self.applied={}
    def apply(self,profile,pid):
        p=policy(profile);h=hardware();proc=psutil.Process(pid)
        if p['affinity'] and not set(p['affinity']).issubset(h['allowed']):raise ValueError('One or more selected CPUs are unavailable to this agent.')
        if p['worker_count']>len(p['affinity'] or h['allowed']):raise ValueError('Worker count exceeds available logical CPUs.')
        if not h['windows']:
            if p!=DEFAULTS:raise ValueError('Performance controls require Windows.')
            return dict(settings=p,applied=False,message='Windows controls are unavailable on this platform.')
        # Remember the process identity; PID reuse must not reuse an old Job handle.
        identity=(pid,proc.create_time())
        if p['ram_limit_mb']:
            committed=getattr(proc.memory_info(),'private',None)
            if committed is not None and committed>p['ram_limit_mb']*1024**2:raise ValueError('The hard limit is below current private committed memory. Stop the server or choose a higher limit.')
        self.discover(pid,identity[1])
        old_priority=proc.nice();old_affinity=proc.cpu_affinity();handle=None;original=None;original_rate=None
        try:
            if p['cpu_budget'] or p['ram_limit_mb'] or identity in self.jobs:
                import win32job,win32api,win32con
                handle=self.jobs.get(identity)
                if handle is None:
                    handle=win32job.CreateJobObject(None,f'CDS.Performance.{pid}.{int(identity[1]*1000)}')
                    process=win32api.OpenProcess(win32con.PROCESS_SET_QUOTA|win32con.PROCESS_TERMINATE|win32con.PROCESS_QUERY_INFORMATION,False,pid)
                    try:
                        try:win32job.AssignProcessToJobObject(handle,process)
                        except Exception:
                            if not win32job.IsProcessInJob(process,handle):raise
                    finally:process.Close()
                    self.jobs[identity]=handle
                original=win32job.QueryInformationJobObject(handle,win32job.JobObjectExtendedLimitInformation)
                original_rate=cpu_rate(handle)
                info=copy.deepcopy(original)
                info['BasicLimitInformation']['LimitFlags']&=~(win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY|win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
                if p['ram_limit_mb']:info['BasicLimitInformation']['LimitFlags']|=win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
                info['ProcessMemoryLimit']=p['ram_limit_mb']*1024**2
                win32job.SetInformationJobObject(handle,win32job.JobObjectExtendedLimitInformation,info)
                cpu_rate(handle,(5 if p['cpu_budget'] else 0,p['cpu_budget']*100))
            proc.nice(getattr(psutil,PRIORITIES[p['priority']]))
            proc.cpu_affinity(p['affinity'] or h['allowed'])
        except Exception:
            if handle is not None and original is not None:
                try:
                    win32job.SetInformationJobObject(handle,win32job.JobObjectExtendedLimitInformation,original)
                    if original_rate is not None:cpu_rate(handle,original_rate)
                except Exception:pass
            try:proc.nice(old_priority);proc.cpu_affinity(old_affinity)
            except psutil.Error:pass
            raise
        self.applied[identity]=copy.deepcopy(p)
        return dict(settings=p,applied=True,pid=pid,affinity=proc.cpu_affinity(),priority=p['priority'],cpu_budget=p['cpu_budget'],ram_limit_mb=p['ram_limit_mb'])
    def discover(self,pid,created):
        identity=(pid,created)
        if sys.platform=='win32' and identity not in self.jobs:
            import win32job,pywintypes
            try:self.jobs[identity]=win32job.OpenJobObject(0x1F003F,False,f'CDS.Performance.{pid}.{int(created*1000)}')
            except pywintypes.error as error:
                if error.winerror not in (2,3):raise
        return self.jobs.get(identity)
    def inspect(self,pid):
        proc=psutil.Process(pid);result=dict(applied=False,pid=pid)
        if sys.platform!='win32':return result
        handle=self.discover(pid,proc.create_time());result.update(applied=True,affinity=proc.cpu_affinity(),priority=next((k for k,v in PRIORITIES.items() if getattr(psutil,v)==proc.nice()),'Unknown'),cpu_budget=0,ram_limit_mb=0)
        if handle is not None:
            import win32job
            info=win32job.QueryInformationJobObject(handle,win32job.JobObjectExtendedLimitInformation)
            if info['BasicLimitInformation']['LimitFlags']&win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY:result['ram_limit_mb']=int(info['ProcessMemoryLimit']/1024**2)
            flags,rate=cpu_rate(handle)
            if flags&1:result['cpu_budget']=rate/100
        return result
    def prune(self):
        for identity in set(self.jobs)|set(self.applied):
            try:alive=psutil.Process(identity[0]).create_time()==identity[1]
            except psutil.Error:alive=False
            if not alive:
                handle=self.jobs.pop(identity,None)
                if handle is not None:handle.Close()
                self.applied.pop(identity,None)


def cpu_rate(handle,value=None):
    import ctypes
    class Rate(ctypes.Structure):_fields_=[('ControlFlags',ctypes.c_uint32),('CpuRate',ctypes.c_uint32)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    if value is None:
        rate=Rate();kernel.QueryInformationJobObject.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p]
        ok=kernel.QueryInformationJobObject(int(handle),15,ctypes.byref(rate),ctypes.sizeof(rate),None)
    else:
        rate=Rate(*value);kernel.SetInformationJobObject.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32]
        ok=kernel.SetInformationJobObject(int(handle),15,ctypes.byref(rate),ctypes.sizeof(rate))
    if not ok:raise ctypes.WinError(ctypes.get_last_error())
    return rate.ControlFlags,rate.CpuRate
