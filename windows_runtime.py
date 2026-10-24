"""Read PE headers to explain runtime problems without executing downloaded DLLs."""
import os,sys,struct
from pathlib import Path
DIRECTX_PAGE='https://www.microsoft.com/en-us/download/details.aspx?id=8109'
DIRECTX_DLL='XAPOFX1_5.dll'
MACHINES={0x014c:'32-bit (x86)',0x8664:'64-bit (x64)',0xAA64:'ARM64'}

def pe_machine(path):
    try:
        with Path(path).open('rb') as f:
            if f.read(2)!=b'MZ':return None
            f.seek(0x3c); raw=f.read(4)
            if len(raw)!=4:return None
            offset=struct.unpack('<I',raw)[0]
            if not 64<=offset<=4*1024*1024:return None
            f.seek(offset); header=f.read(6)
            if len(header)!=6 or header[:4]!=b'PE\x00\x00':return None
            return struct.unpack('<H',header[4:])[0]
    except OSError:return None

def directx_issue(server_root):
    if sys.platform!='win32':return ''
    root=Path(server_root); machine=pe_machine(root/'DayZServer_x64.exe')
    # Let the Windows loader handle invalid server executables; skip non-PE test fixtures.
    if machine is None:return ''
    try:local=next((p for p in root.iterdir() if p.is_file() and p.name.casefold()==DIRECTX_DLL.casefold()),None)
    except OSError:local=None
    instructions=('Installer Microsoft DirectX End-User Runtimes (June 2010): pakk ut pakken og kjør DXSETUP.exe. '
                  'Åpne Kom i gang → DirectX (Microsoft). Dette installeres på maskinen som kjører DayZ-serveren.')
    if local is not None:
        dll_machine=pe_machine(local)
        if dll_machine is None:return str(local)+' er ikke en lesbar Windows-DLL. Flytt den manuelt til en backupmappe utenfor servermappen. '+instructions
        if dll_machine!=machine:
            return (str(local)+' er '+MACHINES.get(dll_machine,hex(dll_machine))+' mens serveren er '+MACHINES.get(machine,hex(machine))+'. '
                    'Dette kan gi 0xc000007b. Flytt denne lokale DLL-kopien manuelt til en backupmappe utenfor servermappen. '+instructions)
        return ''
    system=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'/DIRECTX_DLL
    if pe_machine(system)==machine:return ''
    return DIRECTX_DLL+' mangler eller har feil format for serveren. '+instructions
