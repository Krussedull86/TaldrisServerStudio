"""Create an uncompressed server-only PBO; no private signing key is required."""
import hashlib,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build():
    source=ROOT/'dayz_telemetry/source';target=ROOT/'dayz_telemetry/@CDSTelemetry/addons/CDSTelemetry.pbo'
    entries=[];data=[]
    header=b'\0'+struct.pack('<5I',0x56657273,0,0,0,0)+b'prefix\0CDSTelemetry\0\0'
    for file in sorted(source.rglob('*')):
        if not file.is_file():continue
        content=file.read_bytes();name=file.relative_to(source).as_posix().replace('/','\\').encode()
        entries.append(name+b'\0'+struct.pack('<5I',0,len(content),0,0,len(content)));data.append(content)
    raw=header+b''.join(entries)+b'\0'+struct.pack('<5I',0,0,0,0,0)+b''.join(data)
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw+b'\0'+hashlib.sha1(raw).digest());return target
if __name__=='__main__':print(build())
