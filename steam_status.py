"""Turn terminal control codes into a readable transcript and honest job status."""
import re

def plain_terminal(text):
    text=re.sub(r'\x1b\][^\x07]*(?:\x07|\x1b\\)','',text)
    text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
    text=re.sub(r'\x1b[()][A-Z0-9]','',text)
    # Retain progress updates rather than silently dropping overwritten terminal rows.
    return text.replace('\r\n','\n').replace('\r','\n').replace('\x00','')

def progress_percent(text):
    # SteamCMD emits "progress: 12.34 (bytes / total)" without a percent sign.
    matches=re.findall(r'(?:progress:\s*|\[\s*)(\d+(?:\.\d+)?)\s*(?:%|\()',text,re.I)
    return max(0,min(100,int(float(matches[-1])))) if matches else None

def stage(text):
    lines=[line.strip() for line in plain_terminal(text).splitlines() if line.strip()]
    for line in reversed(lines[-40:]):
        lower=line.casefold()
        if any(s in lower for s in ['password:','password for','enter your password','enter password']):return 'Venter på Steam-passord — bruk feltet nedenfor'
        if any(s in lower for s in ['steam guard','auth code','two-factor','two factor','confirmation code']):return 'Innlogging / Steam Guard — les meldingen i konsollen'
        if any(s in lower for s in ['error!','no subscription','access denied','invalid password','failed to install']):return 'Steam melder en feil — se konsollen'
        if any(s in lower for s in ['downloading','download item','download workshop']):return 'Laster ned — '+line[:180]
        if any(s in lower for s in ['validating','verifying','reconfiguring','preallocating']):return 'Kontrollerer / klargjør filer — '+line[:180]
        if "success! app" in lower or 'success. downloaded item' in lower:return 'Steam har bekreftet en nedlasting — jobben fortsetter til alle trinn er ferdige'
        if any(s in lower for s in ['logging in','connecting anonymously','waiting for user info','logged in']):return 'Kobler til / logger inn på Steam — '+line[:160]
        if 'checking for available updates' in lower or 'updating steamcmd' in lower:return 'Oppdaterer SteamCMD'
    return 'SteamCMD er startet — venter på neste melding'


def phase(text):
    lines=plain_terminal(text).casefold()
    # The last recognizable transition wins, including jobs with several downloads.
    result='Starting'
    for line in lines.splitlines():
        if any(k in line for k in ('error!','failed','access denied','no subscription')):result='Failed — read console'
        elif any(k in line for k in ('logging in','steam guard','password:','connecting anonymously')):result='Login / Steam Guard'
        elif any(k in line for k in ('workshop','download item')):result='Workshop mods'
        elif any(k in line for k in ('validating','verifying')):result='Validating'
        elif any(k in line for k in ('downloading','update state','updating app')):result='Updating server'
        elif 'success!' in line or 'success. downloaded' in line:result='Download confirmed — finishing job'
    return result
