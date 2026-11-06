"""Only the gateway's dedicated TCP port; rules belong to this CDS installation."""
import hashlib,os,subprocess,sys
from pathlib import Path
from windows_firewall import ps_quote,encoded

def run(home,port,log,remove=False):
    if sys.platform!='win32':return
    name='CDS-Mobile-'+hashlib.sha256(str(Path(home).resolve()).casefold().encode()).hexdigest()[:20]
    action=f"New-NetFirewallRule -Name $name -DisplayName 'CDS Mobile HTTPS' -Group 'CruzDoodelZ Server Studio' -Direction Inbound -Action Allow -Enabled True -Profile Any -Protocol TCP -LocalPort {int(port)} | Out-Null" if not remove else ''
    check=(f"$p=$r | Get-NetFirewallPortFilter; if ($r.Enabled -eq 'True' -and $r.Action -eq 'Allow' -and $r.Direction -eq 'Inbound' -and $r.Profile -eq 'Any' -and ($p.Protocol -eq 'TCP' -or $p.Protocol -eq '6') -and @($p.LocalPort).Count -eq 1 -and $p.LocalPort -eq '{int(port)}') {{ exit 0 }}" if not remove else '')
    script=f"""$ErrorActionPreference='Stop'
$name={ps_quote(name)}
$r=Get-NetFirewallRule -PolicyStore PersistentStore -Name $name -ErrorAction SilentlyContinue
if ($r) {{ {check} }} else {{ {'exit 0' if remove else ''} }}
$admin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {{ exit 5 }}
if ($r) {{ Remove-NetFirewallRule -PolicyStore PersistentStore -Name $name }}
{action}
exit 0
"""
    powershell=str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe');options=dict(capture_output=True,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));args=[powershell,'-NoProfile','-NonInteractive','-EncodedCommand',encoded(script)];result=subprocess.run(args,**options)
    if result.returncode==5:
        log('Windows will request administrator access for the mobile HTTPS firewall rule.')
        elevated=f"$ErrorActionPreference='Stop';try {{$p=Start-Process -FilePath {ps_quote(powershell)} -ArgumentList '-NoProfile -NonInteractive -EncodedCommand {encoded(script)}' -Verb RunAs -Wait -PassThru;exit $p.ExitCode}} catch {{exit 1}}"
        result=subprocess.run([powershell,'-NoProfile','-NonInteractive','-EncodedCommand',encoded(elevated)],**options)
    if result.returncode:raise ValueError('Mobile firewall rule could not be changed. Accept the Windows administrator prompt or manage the rule manually.')
    log('Mobile TCP firewall rule removed.' if remove else 'Mobile TCP '+str(port)+' firewall rule ready. Router port forwarding and external firewalls must be configured separately.')

def ensure_rule(home,port,log):run(home,port,log)
def remove_rule(home,log):run(home,0,log,True)
