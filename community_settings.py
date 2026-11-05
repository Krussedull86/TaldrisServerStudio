from urllib.parse import urlparse

def validate_invite(value):
    value=value.strip()
    if not value:return ''
    p=urlparse(value)
    import re
    if p.scheme!='https' or p.username or p.password or p.port or p.query or p.fragment:raise ValueError('Use a direct HTTPS Discord invite URL.')
    code=p.path.removeprefix('/invite/') if p.hostname in ('discord.com','www.discord.com') else p.path[1:] if p.hostname=='discord.gg' else ''
    if not re.fullmatch('[A-Za-z0-9_-]{2,128}',code):raise ValueError('Use https://discord.gg/code or https://discord.com/invite/code.')
    if p.hostname!='discord.gg' and not p.path.startswith('/invite/'):raise ValueError('Use a Discord invite link.')
    return value

