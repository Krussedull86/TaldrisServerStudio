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
        if any(s in lower for s in ['password:','password for','enter your password','enter password']):return 'Waiting for Steam password — use the field below'
        if any(s in lower for s in ['steam guard','auth code','two-factor','two factor','confirmation code']):return 'Login / Steam Guard — read the console message'
        if any(s in lower for s in ['error!','no subscription','access denied','invalid password','failed to install']):return 'Steam reported an error — see the console'
        if any(s in lower for s in ['downloading','download item','download workshop']):return 'Downloading — '+line[:180]
        if any(s in lower for s in ['validating','verifying','reconfiguring','preallocating']):return 'Checking / preparing files — '+line[:180]
        if "success! app" in lower or 'success. downloaded item' in lower:return 'Steam confirmed a download — the job continues until all steps finish'
        if any(s in lower for s in ['logging in','connecting anonymously','waiting for user info','logged in']):return 'Connecting / logging in to Steam — '+line[:160]
        if 'checking for available updates' in lower or 'updating steamcmd' in lower:return 'Updating SteamCMD'
    return 'SteamCMD started — waiting for the next message'


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
