"""Bounded local DayZ snapshots, process history and occupancy heatmap storage."""
import json,math,re,shutil,sqlite3,threading,time,uuid
from pathlib import Path
from core import local_path

DEFAULTS=dict(enabled=False,interval=5,collect_players=True,collect_names=False,scan_loot=False,loot_radius=75,retention_days=7,low_fps=15)

def settings(profile):
    raw=profile.get('telemetry',{})
    if not isinstance(raw,dict) or set(raw)-set(DEFAULTS):raise ValueError('Invalid telemetry settings.')
    s={**DEFAULTS,**raw}
    for key in ('enabled','collect_players','collect_names','scan_loot'):
        if type(s[key]) is not bool:raise ValueError(key+' must be on/off.')
    for key,lo,hi in [('interval',2,60),('loot_radius',25,200),('retention_days',1,30),('low_fps',1,200)]:
        if type(s[key]) is not int or not lo<=s[key]<=hi:raise ValueError(f'{key} must be {lo}–{hi}.')
    return s

def install(profile):
    from release_info import VERSION
    s=settings(profile);root=Path(profile['root']).resolve();target=local_path(root,'@CDSTelemetry')
    source=Path(__file__).resolve().parent/'dayz_telemetry'/'@CDSTelemetry'
    if not (source/'addons/CDSTelemetry.pbo').is_file():raise ValueError('The bundled telemetry PBO is missing.')
    folder=local_path(root,profile['profiles'])/'CDSTelemetry';folder.mkdir(parents=True,exist_ok=True)
    config=folder/'config.json';bridge=''
    if config.is_file():
        try:bridge=json.loads(config.read_text('utf-8')).get('BridgeId','')
        except (OSError,ValueError):pass
    if not re.fullmatch('[0-9a-f]{32}',bridge):bridge=uuid.uuid4().hex
    # The marker prevents overwriting an unrelated local mod folder.
    marker=target/'cds-telemetry.json'
    if target.exists() and not marker.is_file():raise ValueError('@CDSTelemetry already exists without an application install marker. Choose another server folder or move that folder manually.')
    target.mkdir(parents=True,exist_ok=True);shutil.copytree(source,target,dirs_exist_ok=True)
    marker.write_text(json.dumps(dict(version=VERSION)),encoding='utf-8')
    payload=dict(BridgeId=bridge,Enabled=s['enabled'],IntervalSeconds=s['interval'],CollectPlayers=s['collect_players'],CollectNames=s['collect_names'],ScanLoot=s['scan_loot'],LootRadius=s['loot_radius'])
    temp=config.with_suffix('.tmp');temp.write_text(json.dumps(payload,indent=2),encoding='utf-8');temp.replace(config)
    mod=dict(folder='@CDSTelemetry',title='DZSA Tools Telemetry',id='',source='local',path=str(target),load_mode='server',server=True,enabled=True)
    existing=next((m for m in profile['mods'] if m.get('folder','').casefold()=='@cdstelemetry'),None)
    if existing:existing.update(mod)
    else:profile['mods'].append(mod)
    return dict(bridge_id=bridge,path=str(target),message='Server-only telemetry mod installed. Restart the DayZ server to load the mod/settings.')

class TelemetryStore:
    def __init__(self,home):
        self.path=Path(home)/'analytics.sqlite';self.lock=threading.RLock();self.latest={};self.signatures={};self.last_metrics={};self.prune_due={};self.prune_global=0;self.rejections={}
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS metrics(profile TEXT, ts REAL, cpu REAL, ram REAL, players INTEGER, fps REAL, frame REAL, peak REAL, PRIMARY KEY(profile,ts));
            CREATE TABLE IF NOT EXISTS heat(profile TEXT, ts REAL, x INTEGER, z INTEGER, seconds REAL);
            CREATE INDEX IF NOT EXISTS heat_lookup ON heat(profile,ts);
            CREATE INDEX IF NOT EXISTS metrics_lookup ON metrics(profile,ts);''')
            if 'engine' not in {r[1] for r in db.execute('PRAGMA table_info(metrics)')}:db.execute('ALTER TABLE metrics ADD COLUMN engine REAL')
    def db(self):return sqlite3.connect(self.path,timeout=3)
    def ingest(self,p,record,now=None):
        now=time.time() if now is None else now;s=settings(p);key=p['id']
        if not s['enabled']:return
        folder=local_path(p['root'],p['profiles'])/'CDSTelemetry';config=folder/'config.json'
        try:
            if config.stat().st_size>32768:return
            bridge=json.loads(config.read_text('utf-8')).get('BridgeId');candidates=[]
            for path in (folder/'snapshot0.json',folder/'snapshot1.json'):
                try:
                    st=path.stat()
                    if st.st_size>2*1024**2 or st.st_mtime<record.get('started_wall',now)-2 or now-st.st_mtime>max(30,s['interval']*4) or st.st_mtime>now+5:continue
                    raw=json.loads(path.read_text('utf-8-sig'));data=self.validate(raw,bridge,p)
                    data.update(received=now,file_time=st.st_mtime);candidates.append(data)
                except FileNotFoundError:continue
                except (OSError,ValueError,TypeError,KeyError) as error:self.rejections[key]='Snapshot rejected / not ready: '+str(error)[:200];continue
            if not candidates:return
            self.rejections.pop(key,None)
            latest=max(candidates,key=lambda d:(d['file_time'],d['sequence']))
            identity=(latest['session'],latest['sequence'])
            if self.signatures.get(key)==identity:return
            self.signatures[key]=identity
            previous=self.latest.get(key)
            if previous and previous['session']==latest['session'] and latest['sequence']<=previous['sequence']:return
            self.latest[key]=latest
            # Heat weights are seconds of occupancy per 100 m cell, capped to one
            # configured sample period; downtime and replay do not inflate counts.
            weight=s['interval'] if previous and previous['session']==latest['session'] else 0
            if previous:weight=min(weight,max(0,latest['uptime']-previous['uptime']))
            if weight and latest['players']:
                cells={}
                for player in latest['players']:
                    x,z=player['x'],player['z'];cell=(int(x//100),int(z//100));cells[cell]=cells.get(cell,0)+weight
                with self.lock,self.db() as db:db.executemany('INSERT INTO heat VALUES(?,?,?,?,?)',[(key,now,x,z,v) for (x,z),v in cells.items()])
        except (OSError,ValueError,TypeError):return
    @staticmethod
    def validate(raw,bridge,p):
        # Enforce member names share a namespace with engine/mod types. New
        # snapshots prefix every DTO member; accept legacy JSON as well.
        def members(value):
            return {(key[3:] if key.startswith('CDS') else key): item for key,item in value.items()}
        if isinstance(raw,dict):
            raw=members(raw)
            for key,limit in (('Players',128),('Loot',250)):
                values=raw.get(key)
                if isinstance(values,list):
                    if len(values)>limit:raise ValueError('Telemetry list exceeds limits.')
                    raw[key]=[members(item) if isinstance(item,dict) else item for item in values]
        if not isinstance(raw,dict) or not bridge or raw.get('BridgeId')!=bridge or raw.get('Schema')!=1:raise ValueError('Unknown telemetry source.')
        def number(v,lo,hi):
            if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid telemetry number.')
            return float(v)
        session=raw.get('Session','')
        if not isinstance(session,str) or not 1<=len(session)<=80:raise ValueError('Invalid telemetry session.')
        size=number(raw.get('WorldSize',p['map_size']),1,1000000);players=raw.get('Players',[]);loot=raw.get('Loot',[])
        if not isinstance(players,list) or len(players)>128 or not isinstance(loot,list) or len(loot)>250:raise ValueError('Telemetry list exceeds limits.')
        normalized=[]
        for v in players:
            if not isinstance(v,dict):raise ValueError('Invalid player sample.')
            name=str(v.get('Name','Player'))[:80] if settings(p)['collect_names'] else 'Player '+str(v.get('Slot','?'))[:12]
            normalized.append(dict(slot=int(number(v['Slot'],0,1000000)),name=name,x=number(v['X'],0,size),z=number(v['Z'],0,size),health=number(v.get('Health',0),0,100),ping=int(number(v.get('Ping',0),0,60000))))
        points=[]
        for v in loot:
            name=v.get('Type','')
            if not isinstance(name,str) or not re.fullmatch('[A-Za-z0-9_]{1,128}',name):raise ValueError('Invalid item type.')
            points.append(dict(type=name,x=number(v['X'],0,size),z=number(v['Z'],0,size)))
        return dict(schema=1,session=session,sequence=int(number(raw['Sequence'],0,2147483647)),uptime=number(raw['Uptime'],0,1e10),world=str(raw.get('WorldName',raw.get('World','')))[:80],world_size=number(raw.get('WorldSize',size),1,1000000),engine_fps=number(raw.get('EngineFps',0),0,100000),engine_min=number(raw.get('EngineMinFps',0),0,100000),engine_max=number(raw.get('EngineMaxFps',0),0,100000),fps=number(raw['UpdateFps'],0,100000),frame_ms=number(raw['MeanFrameMs'],0,1e8),peak_ms=number(raw['PeakFrameMs'],0,1e8),slow_frames=int(number(raw.get('SlowFrames',0),0,1e7)),player_count=int(number(raw.get('PlayerCount',0),0,128)),players=normalized,loot=points,loot_radius=number(raw.get('LootRadius',0),0,200),loot_x=number(raw.get('LootX',0),0,size),loot_z=number(raw.get('LootZ',0),0,size),loot_age=number(raw.get('LootAge',0),0,1e10),sampled_infected=int(number(raw.get('Infected',0),0,1e6)),sampled_vehicles=int(number(raw.get('Vehicles',0),0,1e6)),loot_truncated=bool(raw.get('LootTruncated',False)))
    def sample(self,p,record,metrics):
        now=time.time();key=p['id']
        if not record or now-self.last_metrics.get(key,0)<5:return
        self.last_metrics[key]=now
        if settings(p)['enabled']:self.ingest(p,record,now)
        t=self.status(p,now);data=t.get('sample') if t['connected'] else None
        with self.lock,self.db() as db:
            db.execute('INSERT OR REPLACE INTO metrics(profile,ts,cpu,ram,players,fps,frame,peak,engine) VALUES(?,?,?,?,?,?,?,?,?)',(key,now,metrics.get('cpu_percent'),metrics.get('ram_mb'),data.get('player_count') if data else None,data.get('fps') if data else None,data.get('frame_ms') if data else None,data.get('peak_ms') if data else None,data.get('engine_fps') if data else None))
            if now>=self.prune_global:
                db.execute('DELETE FROM metrics WHERE ts<?',(now-30*86400,));db.execute('DELETE FROM heat WHERE ts<?',(now-30*86400,));self.prune_global=now+300
            if now>=self.prune_due.get(key,0):
                # Keep histories bounded even when profile retention is changed.
                cutoff=now-settings(p)['retention_days']*86400
                db.execute('DELETE FROM metrics WHERE profile=? AND ts<?',(key,cutoff));db.execute('DELETE FROM heat WHERE profile=? AND ts<?',(key,cutoff));self.prune_due[key]=now+300
    def status(self,p,now=None):
        now=time.time() if now is None else now;s=settings(p);data=self.latest.get(p['id']);age=now-data['file_time'] if data else None
        connected=bool(s['enabled'] and data and age is not None and 0<=age<=max(30,s['interval']*4))
        return dict(enabled=s['enabled'],connected=connected,age=round(age,1) if age is not None else None,sample=data if connected else None,message='Live' if connected else 'Disabled' if not s['enabled'] else self.rejections.get(p['id'],'Waiting for a fresh server-mod snapshot'))
    def query(self,p,hours=1):
        hours=max(1,min(int(hours),settings(p)['retention_days']*24));since=time.time()-hours*3600
        with self.lock,self.db() as db:
            # At most 720 chart points, irrespective of the history range.
            bucket=max(5,int(hours*3600/720))
            rows=db.execute('SELECT AVG(ts),AVG(cpu),AVG(ram),AVG(players),AVG(fps),AVG(frame),MAX(peak),AVG(engine) FROM metrics WHERE profile=? AND ts>=? GROUP BY CAST(ts/? AS INTEGER) ORDER BY AVG(ts)',(p['id'],since,bucket)).fetchall()
            heat=db.execute('SELECT x,z,SUM(seconds) FROM heat WHERE profile=? AND ts>=? GROUP BY x,z ORDER BY SUM(seconds) DESC LIMIT 5000',(p['id'],since)).fetchall()
        return dict(status=self.status(p),history=[dict(zip(('ts','cpu','ram','players','fps','frame','peak','engine'),r)) for r in rows],heat=[dict(x=x*100+50,z=z*100+50,seconds=v) for x,z,v in heat],hours=hours)
