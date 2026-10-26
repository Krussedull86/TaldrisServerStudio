"""Bounded DayZ arguments, always passed directly to the EXE without a shell."""
import re
FLAGS={'filepatching','netlog','dosimulate','nosound','nosplash','nopause','scrallowfilewrite'}
VALUES={'name','cpucount','maxmem','limitfps','bepath'}
BASE={'dologs','adminlog','freezecheck'}

def validate_extra(args):
    if not isinstance(args,list) or len(args)>64:raise ValueError('Bruk maksimalt 64 ekstra startvalg.')
    if sum(len(a) for a in args if isinstance(a,str))>8192:raise ValueError('Ekstra startvalg er for lange.')
    seen=set()
    for arg in args:
        if not isinstance(arg,str) or len(arg)>2048 or any(ord(c)<32 for c in arg) or '"' in arg:raise ValueError('Ugyldig ekstra startvalg.')
        m=re.fullmatch(r'-([A-Za-z]+)(?:=(.+))?',arg)
        if not m:raise ValueError('Startvalg må skrives som -valg eller -valg=verdi.')
        key,value=m[1].casefold(),m[2]
        if key in seen:raise ValueError('Startvalget er oppgitt flere ganger: '+key)
        seen.add(key)
        if key in FLAGS and value is None:continue
        if key in VALUES and value is not None:
            if key in {'cpucount','maxmem','limitfps'} and (not value.isdigit() or not 1<=int(value)<=1000000):raise ValueError('Ugyldig tall for '+key)
            continue
        raise ValueError('Startvalget støttes ikke som ekstra argument: '+key)
    return args
