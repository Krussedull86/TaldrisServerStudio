"""Scoped, idempotent Windows Firewall rules for a DayZ server."""
import base64
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys


def mask_config(text):
    # Keep positions while masking comments and strings, including URLs in strings.
    return re.sub(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*', lambda m: ' ' * len(m.group()), text, flags=re.S)


def set_query_port(text, port):
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError('Steam query-port må være 1–65535.')
    matches = list(re.finditer(r'\bsteamQueryPort\s*=\s*\d+\s*;', mask_config(text), re.I))
    if len(matches) > 1:
        raise ValueError('Flere steamQueryPort finnes. Fjern duplikatene i konfigurasjonseditoren.')
    line = f'steamQueryPort = {port};'
    if matches:
        match = matches[0]
        return text[:match.start()] + line + text[match.end():]
    return line + '\n' + text


def server_ports(profile):
    config = (Path(profile['root']) / profile['config']).read_text('utf-8-sig')
    config = mask_config(config)
    matches = re.findall(r'\bsteamQueryPort\s*=\s*(\d+)\s*;', config, re.I)
    if not matches:
        raise ValueError('steamQueryPort mangler. Åpne Konfigurasjon → Steam query-port, velg port og lagre før oppstart.')
    if len(matches) != 1:
        raise ValueError('Flere steamQueryPort finnes. Fjern duplikatene før oppstart.')
    query = int(matches[0])
    game = int(profile['port'])
    ports = sorted({game, game + 1, game + 2, query})
    if any(not 1 <= port <= 65535 for port in ports):
        raise ValueError('Ugyldig spillport eller steamQueryPort i serverkonfigurasjonen.')
    return ports


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def encoded(script):
    return base64.b64encode(script.encode('utf-16-le')).decode('ascii')


def rule_script(profile, ports):
    exe = str((Path(profile['root']) / 'DayZServer_x64.exe').resolve())
    identity = hashlib.sha256(str(profile['id']).encode()).hexdigest()[:20]
    name = ps_quote('Taldris-DayZ-' + identity)
    port_list = ','.join(ps_quote(p) for p in ports)
    return f"""
$ErrorActionPreference = 'Stop'
$name = {name}
$exe = {ps_quote(exe)}
$ports = @({port_list})
$r = Get-NetFirewallRule -PolicyStore PersistentStore -Name $name -ErrorAction SilentlyContinue
if ($r) {{
    $p = $r | Get-NetFirewallPortFilter
    $a = $r | Get-NetFirewallApplicationFilter
    $samePorts = (@(Compare-Object @($p.LocalPort | Sort-Object) @($ports | Sort-Object)).Count -eq 0)
    if ($r.Enabled -eq 'True' -and $r.Action -eq 'Allow' -and $r.Direction -eq 'Inbound' -and $r.Profile -eq 'Any' -and ($p.Protocol -eq 'UDP' -or $p.Protocol -eq '17') -and $a.Program -eq $exe -and $samePorts) {{ exit 0 }}
}}
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {{ exit 5 }}
if ($r) {{ Remove-NetFirewallRule -PolicyStore PersistentStore -Name $name }}
New-NetFirewallRule -PolicyStore PersistentStore -Name $name -DisplayName {ps_quote('Taldris DayZ ' + str(profile['name']))} -Group 'Taldris Server Studio' -Direction Inbound -Action Allow -Enabled True -Profile Any -Program $exe -Protocol UDP -LocalPort $ports | Out-Null
exit 0
"""


def ensure_firewall(profile, log):
    if sys.platform != 'win32' or not profile.get('auto_firewall', True):
        return
    ports = server_ports(profile)
    script = rule_script(profile, ports)
    powershell = str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe')
    args = [powershell, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded(script)]
    options = dict(capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=120)
    log('Kontrollerer Windows-brannmur: UDP ' + ', '.join(map(str, ports)))
    result = subprocess.run(args, **options)
    if result.returncode == 5:
        log('Windows ber om administratortilgang for å opprette serverens brannmurregel.')
        elevate = f"$ErrorActionPreference='Stop'; try {{ $p=Start-Process -FilePath {ps_quote(powershell)} -ArgumentList '-NoProfile -NonInteractive -EncodedCommand {encoded(script)}' -Verb RunAs -Wait -PassThru; exit $p.ExitCode }} catch {{ exit 1 }}"
        result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded(elevate)], **options)
    if result.returncode:
        raise ValueError('Brannmurregelen ble ikke opprettet. Godta Windows-administratorforespørselen og prøv igjen. Du kan slå av automatisk brannmur i Innstillinger hvis reglene administreres separat.')
    log('Windows-brannmurregel er klar for DayZServer_x64.exe, UDP ' + ', '.join(map(str, ports)) + '. Ruter og eventuell ekstern brannmur må konfigureres separat.')
