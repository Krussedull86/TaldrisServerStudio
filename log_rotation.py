"""Archive closed DayZ logs; never truncate a running server's log files."""
import os,re,time,uuid,zipfile
from pathlib import Path
from core import local_path
EXTENSIONS={'.rpt','.log','.adm'}

def archive_folder(home,profile):return Path(home)/'log_archives'/profile['id']

def rotate(profile,home,log=lambda message:None):
    folder=local_path(profile['root'],profile['profiles']);destination=archive_folder(home,profile);destination.mkdir(parents=True,exist_ok=True)
    if folder.resolve()==destination.resolve() or destination.resolve().is_relative_to(folder.resolve()):raise ValueError('Loggarkivet må ligge utenfor profiles-mappen.')
    files=[]
    if folder.is_dir():
        for path in folder.iterdir():
            if path.is_file() and not path.is_symlink() and path.suffix.casefold() in EXTENSIONS:files.append(path)
    count=0;skipped=0;archive=None
    if files:
        archive=destination/('logs-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.zip');temp=archive.with_suffix('.partial');stable=[]
        try:
            with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as z:
                for path in sorted(files):
                    try:
                        before=path.stat();z.write(path,path.name);after=path.stat()
                        if (before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino):stable.append((path,after))
                        else:skipped+=1
                    except (OSError,ValueError):skipped+=1
            temp.replace(archive)
            for path,before in stable:
                try:
                    now=path.stat()
                    if path.is_symlink() or (now.st_size,now.st_mtime_ns,now.st_ino)!=(before.st_size,before.st_mtime_ns,before.st_ino):skipped+=1;continue
                    path.unlink();count+=1
                except OSError:skipped+=1
        finally:temp.unlink(missing_ok=True)
    # Retention is restricted to ZIP files created by this feature. Always retain
    # the archive just written, even if a single session exceeds the size limit.
    archives=sorted((p for p in destination.glob('logs-*.zip') if p.is_file() and not p.is_symlink() and re.fullmatch(r'logs-\d{8}-\d{6}-[a-f0-9]{8}\.zip',p.name)),key=lambda p:p.stat().st_mtime,reverse=True)
    total=0;removed=0;now=time.time()
    for index,path in enumerate(archives):
        info=path.stat();total+=info.st_size
        over=index>=profile.get('log_keep_archives',20) or now-info.st_mtime>profile.get('log_keep_days',14)*86400 or total>profile.get('log_max_mb',1024)*1024**2
        if over and index>0:path.unlink();removed+=1
    if files or removed:log(f'Loggrotasjon: {count} logger arkivert/fjernet fra profiles, {skipped} beholdt/ikke tilgjengelig, {removed} gamle arkiver fjernet.')
    return dict(archived=count,skipped=skipped,removed_archives=removed,archive=str(archive) if archive else '',folder=str(destination))
