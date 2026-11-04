"""Runtime check merged from the uploaded improvements, retaining PE architecture checks."""
import os,sys
from pathlib import Path
from windows_runtime import DIRECTX_PAGE,DIRECTX_DLL,pe_machine,directx_issue
VCREDIST_URL='https://aka.ms/vs/17/release/vc_redist.x64.exe'

def check_dependencies(root=''):
    system=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'
    if sys.platform!='win32':return [(False,'Windows runtime','Run this check on the Windows server.',DIRECTX_PAGE),(False,'Visual C++ x64','Run this check on Windows.',VCREDIST_URL)]
    issue=directx_issue(root) if root and pe_machine(Path(root)/'DayZServer_x64.exe') else ''
    dx=not issue and pe_machine(system/DIRECTX_DLL)==0x8664
    if root and pe_machine(Path(root)/DIRECTX_DLL)==0x8664 and not issue:dx=True
    vc=all(pe_machine(system/name)==0x8664 for name in ('vcruntime140.dll','msvcp140.dll'))
    return [(dx,'DirectX XAPOFX1_5 (x64)',issue or ('Present' if dx else 'Missing x64 DLL. Extract the June 2010 package and run DXSETUP.exe.'),DIRECTX_PAGE),(vc,'Visual C++ Redistributable x64','Present' if vc else 'Missing or wrong architecture. Install the Microsoft x64 runtime.',VCREDIST_URL)]
