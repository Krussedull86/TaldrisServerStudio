"""Recover directory swaps after process termination during a backup restore."""
import json,shutil
from pathlib import Path
from core import local_path


def write_journal(root,data):
    path=Path(root)/'.taldris-restore.json';tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data),encoding='utf-8');tmp.replace(path)


def remove(path):
    if path.is_dir():shutil.rmtree(path)
    elif path.exists():path.unlink()


def recover(root):
    root=Path(root).resolve();path=root/'.taldris-restore.json'
    if not path.exists():return False
    data=json.loads(path.read_text('utf-8'));entries=data.get('entries',[])
    for entry in reversed(entries):
        dest=local_path(root,entry['file']);old=local_path(root,entry['old'])
        if not old.name.startswith(dest.name+'.restore-'):raise ValueError('Ugyldig gjenopprettingsjournal.')
        if data.get('committed'):
            if old.exists():remove(old)
        elif old.exists():remove(dest);old.rename(dest)
        elif not entry['existed'] and entry.get('done'):remove(dest)
    stage=local_path(root,data['stage'])
    if not stage.name.startswith('.taldris-restore-'):raise ValueError('Ugyldig staging-mappe.')
    if stage.exists():remove(stage)
    path.unlink();return True
