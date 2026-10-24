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
