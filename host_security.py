"""Owner-only local credentials; Windows secrets use machine DPAPI + ACL."""
import json,os,secrets,subprocess,sys
from pathlib import Path


def protect_file(path):
    path=Path(path)
    if sys.platform=='win32':
        import win32api,win32security,ntsecuritycon
        owner=win32security.GetNamedSecurityInfo(str(path.parent),win32security.SE_FILE_OBJECT,win32security.OWNER_SECURITY_INFORMATION).GetSecurityDescriptorOwner()
        acl=win32security.ACL()
        for sid in [owner,win32security.ConvertStringSidToSid('S-1-5-18'),win32security.ConvertStringSidToSid('S-1-5-32-544')]:acl.AddAccessAllowedAceEx(win32security.ACL_REVISION,(win32security.OBJECT_INHERIT_ACE|win32security.CONTAINER_INHERIT_ACE) if path.is_dir() else 0,ntsecuritycon.FILE_ALL_ACCESS,sid)
        win32security.SetNamedSecurityInfo(str(path),win32security.SE_FILE_OBJECT,win32security.DACL_SECURITY_INFORMATION|win32security.PROTECTED_DACL_SECURITY_INFORMATION,None,None,acl,None)
    else:path.chmod(0o600)


def atomic_private(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.new')
    tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8');protect_file(tmp);tmp.replace(path)


def store_secrets(home,data):
    raw=json.dumps(data).encode()
    if sys.platform=='win32':
        import win32crypt
        raw=win32crypt.CryptProtectData(raw,'Taldris host secrets',None,None,None,4)
        payload={'dpapi':raw.hex()}
    else:payload={'local':data}
    atomic_private(Path(home)/'host_secrets.json',payload)


def load_secrets(home):
    path=Path(home)/'host_secrets.json'
    if not path.exists():return {}
    data=json.loads(path.read_text('utf-8'))
    if 'dpapi' in data:
        import win32crypt
        return json.loads(win32crypt.CryptUnprotectData(bytes.fromhex(data['dpapi']),None,None,None,0)[1])
    return data.get('local',{})


class AgentLock:
    def __init__(self,home):self.path=Path(home)/'agent.lock';self.file=None
    def acquire(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);self.file=self.path.open('a+b');self.file.seek(0);self.file.write(b'0');self.file.flush();self.file.seek(0)
        try:
            if sys.platform=='win32':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:self.file.close();self.file=None;raise RuntimeError('En bakgrunnsagent eier allerede denne datamappen.')
    def close(self):
        if self.file:self.file.close();self.file=None
