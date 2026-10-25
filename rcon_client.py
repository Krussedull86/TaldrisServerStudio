"""BattlEye RCon v2: CRC validation, multipart replies and message ACKs."""
import re,socket,struct,time,zlib
from pathlib import Path
from core import local_path


def packet(payload):
    body=b'\xff'+payload
    return b'BE'+struct.pack('<I',zlib.crc32(body)&0xffffffff)+body


def unpack(data):
    if len(data)<8 or data[:2]!=b'BE' or data[6]!=255:raise ValueError('Ugyldig RCon-pakke.')
    if struct.unpack('<I',data[2:6])[0]!=(zlib.crc32(data[6:])&0xffffffff):raise ValueError('RCon-kontrollsum stemmer ikke.')
    return data[7:]


def command(host,port,password,text,timeout=5):
    if not 1<=int(port)<=65535 or any(c in text for c in '\x00\r\n'):raise ValueError('Ugyldig RCon-kommando eller port.')
    if len(text.encode('utf-8'))>1000:raise ValueError('RCon-kommandoen er for lang.')
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.connect((host,int(port)));sock.settimeout(.7)
        def receive(until,kind):
            parts={};count=None
            while time.monotonic()<until:
                try:payload=unpack(sock.recv(65535))
                except socket.timeout:continue
                except ValueError:continue
                if payload[0]==2 and len(payload)>=2:sock.send(packet(payload[:2]));continue
                if payload[0]!=kind:continue
                if kind==0:
                    if payload!=b'\x00\x01':raise ValueError('RCon avviste passordet.')
                    return b''
                if len(payload)<2 or payload[1]!=0:continue
                body=payload[2:]
                if body.startswith(b'\x00') and len(body)>=3:
                    total,index=body[1:3]
                    if total<1 or index>=total or (count is not None and total!=count):raise ValueError('Ugyldig RCon-flerpakke.')
                    count=total;parts[index]=body[3:]
                    if len(parts)==count:return b''.join(parts[i] for i in range(count))
                else:return body
            raise TimeoutError('RCon svarte ikke innen tidsfristen. Kontroller RCon-port, passord og BattlEye.')
        sock.send(packet(b'\x00'+password.encode('ascii')));receive(time.monotonic()+timeout,0)
        # Never resend destructive commands automatically after an ambiguous timeout.
        sock.send(packet(b'\x01\x00'+text.encode('utf-8')))
        return receive(time.monotonic()+timeout,1).decode('utf-8',errors='replace')


def credentials(profile):
    relative=profile.get('rcon_config','')
    if not relative:raise ValueError('Velg BattlEye sin aktive BEServer_x64.cfg i RCon-oppsettet.')
    path=local_path(profile['root'],relative)
    if not path.exists() and path.name.casefold().startswith('beserver'):
        candidates=[p for p in path.parent.glob('*.cfg') if p.name.casefold().startswith('beserver_x64')]
        if len(candidates)==1:path=candidates[0]
    text=path.read_text('utf-8-sig');values={}
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith(('//','#')):continue
        pair=line.split(None,1)
        if len(pair)==2:values[pair[0].casefold()]=pair[1].strip()
    password=values.get('rconpassword','');port=int(values.get('rconport','0'))
    if not password or not 1<=port<=65535:raise ValueError('BattlEye-filen må ha RConPassword og en egen RConPort.')
    host=values.get('rconip') or '127.0.0.1'
    if host=='0.0.0.0':host='127.0.0.1'
    return host,port,password


def server_command(profile,text):return command(*credentials(profile),text)
