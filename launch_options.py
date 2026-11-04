"""Bounded DayZ arguments, always passed directly to the EXE without a shell."""
import re
FLAGS={'filepatching','netlog','dosimulate','nosound','nosplash','nopause','scrallowfilewrite'}
VALUES={'name','cpucount','maxmem','limitfps','bepath'}
BASE={'dologs','adminlog','freezecheck'}

def validate_extra(args):
    if not isinstance(args,list) or len(args)>64:raise ValueError('Use no more than 64 extra launch options.')
    if sum(len(a) for a in args if isinstance(a,str))>8192:raise ValueError('Extra launch options are too long.')
    seen=set()
    for arg in args:
        if not isinstance(arg,str) or len(arg)>2048 or any(ord(c)<32 for c in arg) or '"' in arg:raise ValueError('Invalid extra launch option.')
        m=re.fullmatch(r'-([A-Za-z]+)(?:=(.+))?',arg)
        if not m:raise ValueError('Write launch options as -option or -option=value.')
        key,value=m[1].casefold(),m[2]
        if key in seen:raise ValueError('Launch option specified more than once: '+key)
        seen.add(key)
        if key in FLAGS and value is None:continue
        if key in VALUES and value is not None:
            if key in {'cpucount','maxmem','limitfps'} and (not value.isdigit() or not 1<=int(value)<=1000000):raise ValueError('Invalid number for '+key)
            continue
        raise ValueError('This launch option is not supported as an extra argument: '+key)
    return args
