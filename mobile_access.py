"""Opt-in, certificate-pinned HTTPS gateway. Never exposes the local owner API."""
import copy,hashlib,hmac,ipaddress,json,re,secrets,sqlite3,ssl,threading,time,uuid
from collections import defaultdict,deque
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from host_security import atomic_private,protect_file

DEFAULTS=dict(enabled=False,port=8788,public_url='',auto_firewall=True)
SCOPES={'read','control','message'}
ACTIONS={'start':'control','stop':'control','restart':'control','cancel_restart':'control','say':'message'}

def endpoint(value):
    value=str(value).strip().rstrip('/');p=urlsplit(value)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.path or p.query or p.fragment:raise ValueError('Use https://hostname:port without a path or credentials.')
    try:port=p.port
    except ValueError:raise ValueError('Invalid endpoint port.')
    if port is not None and not 1<=port<=65535:raise ValueError('Invalid endpoint port.')
    return value

def cert_files(home):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    home=Path(home);cert=home/'mobile-cert.pem';keyfile=home/'mobile-key.pem'
    if cert.exists()!=keyfile.exists():raise ValueError('Mobile certificate/key pair is incomplete. Restore both files before enabling access.')
    if not cert.exists():
        key=ec.generate_private_key(ec.SECP256R1());name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'CDS Mobile Gateway')]);now=datetime.now(timezone.utc)
        certificate=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=3650)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),False).add_extension(x509.BasicConstraints(ca=False,path_length=None),True).sign(key,hashes.SHA256()))
        keyfile.touch(mode=0o600,exist_ok=False);protect_file(keyfile)
        keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));protect_file(keyfile)
        cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM));protect_file(cert)
    certificate=x509.load_pem_x509_certificate(cert.read_bytes())
    return cert,keyfile,certificate.fingerprint(hashes.SHA256()).hex()

class Gateway:
    def __init__(self,engine):
        self.engine=engine;self.home=engine.home;self.path=self.home/'mobile-access.json';self.lock=threading.RLock();self.server=None;self.thread=None;self.error='';self.pairings={};self.rates=defaultdict(deque)
        self.data=json.loads(self.path.read_text()) if self.path.exists() else dict(settings=copy.deepcopy(DEFAULTS),devices=[])
        self.journal=self.home/'mobile-commands.sqlite'
        with self.db() as db:db.execute('CREATE TABLE IF NOT EXISTS commands(device TEXT, request TEXT, server TEXT, action TEXT, created REAL, job TEXT, status TEXT, result TEXT, PRIMARY KEY(device,request))')
        protect_file(self.journal)
    def db(self):return sqlite3.connect(self.journal,timeout=5)
    def save(self):atomic_private(self.path,self.data)
    def local_status(self):
        with self.lock:
            fingerprint=cert_files(self.home)[2] if (self.home/'mobile-cert.pem').exists() else ''
            return dict(settings=self.data['settings'],listening=bool(self.server),error=self.error,fingerprint=fingerprint,devices=[{k:v for k,v in d.items() if k!='token_hash'} for d in self.data['devices']])
    def configure(self,settings):
        if not isinstance(settings,dict) or set(settings)-set(DEFAULTS):raise ValueError('Invalid mobile settings.')
        s={**DEFAULTS,**settings}
        if type(s['enabled']) is not bool or type(s['auto_firewall']) is not bool or type(s['port']) is not int or not 1024<=s['port']<=65535:raise ValueError('Choose a TCP port from 1024 to 65535.')
        if s['public_url']:s['public_url']=endpoint(s['public_url'])
        if s['enabled'] and not s['public_url']:raise ValueError('Enter the HTTPS address the phone will use.')
        self.stop()
        with self.lock:self.data['settings']=s;self.pairings.clear();self.save()
        if s['enabled']:self.start(strict=True)
        else:
            from mobile_firewall import remove_rule
            remove_rule(self.home,self.engine.log)
        return self.local_status()
    def start(self,strict=False):
        s=self.data['settings']
        if not s['enabled'] or self.server:return
        try:
            cert,key,pin=cert_files(self.home);ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.load_cert_chain(cert,key)
            gateway=self
            class Server(ThreadingHTTPServer):
                daemon_threads=True;allow_reuse_address=True;request_queue_size=16
                def __init__(self,*a,**kw):self.slots=threading.BoundedSemaphore(16);super().__init__(*a,**kw)
                def process_request(self,request,address):
                    if not self.slots.acquire(False):request.close();return
                    try:super().process_request(request,address)
                    except Exception:self.slots.release();raise
                def process_request_thread(self,request,address):
                    try:
                        request.settimeout(8);secure=ctx.wrap_socket(request,server_side=True)
                        try:self.finish_request(secure,address)
                        finally:self.shutdown_request(secure)
                    except (OSError,ssl.SSLError):request.close()
                    finally:self.slots.release()
            class Handler(BaseHTTPRequestHandler):
                protocol_version='HTTP/1.0'
                def log_message(self,*args):pass
                def do_POST(self):
                    try:
                        if self.headers.get('Origin') or self.path not in ('/v1/pair','/v1/request'):self.reply(403,{'error':'Access denied.'});return
                        gateway.rate(self.client_address[0],self.path)
                        size=int(self.headers.get('Content-Length','0'))
                        if self.headers.get('Transfer-Encoding') or not 0<size<=65536:raise ValueError('Invalid request size.')
                        body=json.loads(self.rfile.read(size))
                        if not isinstance(body,dict):raise ValueError('A JSON object is required.')
                        if self.path=='/v1/pair':result=gateway.pair(body)
                        else:
                            token=self.headers.get('Authorization','')
                            if not token.startswith('Bearer '):raise PermissionError('Device access denied. Pair again if access was revoked or expired.')
                            result=gateway.request(token[7:],body)
                        self.reply(200,{'result':result})
                    except PermissionError as error:self.reply(403,{'error':str(error)})
                    except (ValueError,KeyError,TypeError) as error:self.reply(400,{'error':str(error)[:250]})
                    except Exception:self.reply(503,{'error':'The gateway could not complete the request. Check the local agent log.'})
                def reply(self,code,value):
                    raw=json.dumps(value,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
            server=Server(('0.0.0.0',s['port']),Handler)
            try:
                from mobile_firewall import ensure_rule,remove_rule
                if s['auto_firewall']:ensure_rule(self.home,s['port'],self.engine.log)
                else:remove_rule(self.home,self.engine.log)
            except Exception:server.server_close();raise
            self.server=server;self.thread=threading.Thread(target=server.serve_forever,daemon=True);self.thread.start();self.error='';self.engine.log('Mobile HTTPS gateway listening on TCP '+str(s['port']))
        except Exception as error:
            try:
                from mobile_firewall import remove_rule
                remove_rule(self.home,self.engine.log)
            except Exception as cleanup:self.engine.log('Mobile firewall cleanup requires attention: '+str(cleanup))
            self.error=str(error);self.engine.log('Mobile gateway unavailable: '+str(error))
            if strict:raise
    def stop(self):
        if self.server:self.server.shutdown();self.server.server_close();self.server=None
    def rate(self,address,path):
        now=time.monotonic()
        with self.lock:
            if len(self.rates)>2048:
                self.rates={k:v for k,v in self.rates.items() if v and now-v[-1]<60};self.rates=defaultdict(deque,self.rates)
                if len(self.rates)>2048:raise PermissionError('Gateway busy. Try later.')
            q=self.rates[(address,path)]
            while q and q[0]<now-60:q.popleft()
            if len(q)>=(8 if path=='/v1/pair' else 120):raise PermissionError('Too many requests. Try again in a minute.')
            q.append(now)
    def new_pairing(self,params):
        with self.lock:
            if not self.server:raise ValueError('Enable the mobile gateway first.')
            servers=params.get('servers',[]);scopes=params.get('scopes',[])
            known={p['id'] for p in self.engine.manager.state['servers']}
            if not isinstance(servers,list) or not servers or any(s not in known for s in servers):raise ValueError('Choose one or more valid servers.')
            if not isinstance(scopes,list) or not set(scopes)<=SCOPES or 'read' not in scopes:raise ValueError('Read access is required; supported permissions: read, control, message.')
            if len(self.data['devices'])>=50:raise ValueError('Remove an old paired device first (maximum 50).')
            code=secrets.token_urlsafe(24);now=time.time();self.pairings={k:v for k,v in self.pairings.items() if v['expires']>now}
            if len(self.pairings)>=10:raise ValueError('Too many pairing invitations. Wait for an invitation to expire.')
            self.pairings[hashlib.sha256(code.encode()).hexdigest()]=dict(servers=list(set(servers)),scopes=list(set(scopes)),expires=now+300)
            return dict(protocol=1,url=self.data['settings']['public_url'],fingerprint=cert_files(self.home)[2],code=code,expires=now+300)
    def pair(self,body):
        code=str(body.get('code',''));name=str(body.get('name','Android')).strip()
        if not 1<=len(name)<=60 or any(ord(c)<32 for c in name):raise ValueError('Choose a device name (1–60 characters).')
        with self.lock:
            digest=hashlib.sha256(code.encode()).hexdigest();invitation=self.pairings.get(digest)
            if not invitation or invitation['expires']<time.time():raise PermissionError('Pairing invitation expired or invalid. Create a new QR code in CDS.')
            if len(self.data['devices'])>=50:raise PermissionError('Device limit reached.')
            self.pairings.pop(digest);token=secrets.token_urlsafe(48);device=dict(id=uuid.uuid4().hex,name=name,token_hash=hashlib.sha256(token.encode()).hexdigest(),servers=invitation['servers'],scopes=invitation['scopes'],created=time.time(),expires=time.time()+90*86400)
            self.data['devices'].append(device);self.save();self.engine.log('Mobile device paired: '+device['id'])
            return dict(token=token,device=device['id'],expires=device['expires'],scopes=device['scopes'])
    def revoke(self,identity):
        with self.lock:self.data['devices']=[d for d in self.data['devices'] if d['id']!=identity];self.save()
        self.engine.log('Mobile device revoked: '+str(identity));return self.local_status()
    def authorize(self,token):
        if not self.data['settings']['enabled']:raise PermissionError('Mobile access is disabled.')
        if not 20<=len(token)<=128:raise PermissionError('Device access denied.')
        digest=hashlib.sha256(token.encode()).hexdigest()
        for device in self.data['devices']:
            if hmac.compare_digest(digest,device['token_hash']) and device['expires']>time.time():return copy.deepcopy(device)
        raise PermissionError('Device access expired or revoked. Pair again in CDS.')
    def request(self,token,body):
        # Revocation and command acceptance share a lock. Only explicit, bounded
        # actions cross this boundary; no arbitrary RCon, files or owner methods.
        with self.lock:
            device=self.authorize(token);method=body.get('method')
            if method=='status':return self.status(device)
            server=body.get('server')
            if server not in device['servers']:raise PermissionError('No access to this server.')
            p=self.engine.profile(server)
            if method=='analytics':
                result=self.engine.analytics.query(p,1)
                # Mobile telemetry is aggregate only; no positions, names or loot.
                return dict(history=result['history'],hours=1)
            if method=='action':return self.action(device,p,body)
            raise ValueError('Unknown mobile method.')
    def status(self,device):
        snap=self.engine.snapshot();servers=[]
        for p in snap['state']['servers']:
            if p['id'] not in device['servers']:continue
            r=snap['runtime'].get(p['id'],{});sample=r.get('telemetry',{}).get('sample') or {};request=p.get('shutdown_request') or {}
            servers.append(dict(id=p['id'],name=p['name'],running=r.get('running',False),busy=r.get('busy',False),uptime=r.get('uptime',0),cpu=r.get('cpu_percent'),ram=r.get('ram_mb'),players=sample.get('player_count'),fps=sample.get('engine_fps'),restart_at=request.get('deadline') or r.get('launch',{}).get('restart_due'),warning=r.get('resource_warning','')))
        with self.db() as db:
            db.execute('DELETE FROM commands WHERE created<?',(time.time()-30*86400,))
            rows=db.execute('SELECT request,server,action,created,job,status,result FROM commands WHERE device=? ORDER BY created DESC LIMIT 30',(device['id'],)).fetchall();jobs=[]
            for request,server,action,created,job,status,result in rows:
                current=self.engine.jobs.get(job)
                if current:
                    status=current['status'];result=str(current.get('error',current.get('result','')))[:1000]
                    db.execute('UPDATE commands SET status=?, result=? WHERE device=? AND request=?',(status,result,device['id'],request))
                elif status in ('accepted','queued','running'):status='unknown';result='Agent restarted or job history expired. Check server status before trying again.'
                if server in device['servers']:jobs.append(dict(request=request,server=server,action=action,created=created,status=status,result=self.engine.redact(result)))
        return dict(at=time.time(),version=snap['version'],build=snap['build'],servers=servers,jobs=jobs,scopes=device['scopes'])
    def action(self,device,p,body):
        action=body.get('action')
        if action not in ACTIONS or ACTIONS[action] not in device['scopes']:raise PermissionError('This device cannot perform that action.')
        request=body.get('request','');expires=body.get('expires')
        if not isinstance(request,str) or not re.fullmatch('[a-f0-9]{32}',request):raise ValueError('Invalid request ID.')
        with self.db() as db:
            old=db.execute('SELECT job,server,action FROM commands WHERE device=? AND request=?',(device['id'],request)).fetchone()
            if old:
                if old[1:]!=(p['id'],action):raise ValueError('Request ID already used for another action.')
                return dict(request=request,job=old[0],duplicate=True)
        if type(expires) not in (int,float) or not time.time()<expires<=time.time()+120:raise ValueError('Command expired. Check phone/server clocks and try again.')
        params={'_mobile_deadline':expires}
        if action in ('stop','restart'):
            minutes=body.get('minutes',10)
            if type(minutes) is not int or not 1<=minutes<=60:raise ValueError('Countdown must be 1–60 minutes.')
            params['minutes']=minutes
        if action=='say':
            message=body.get('message','')
            if not isinstance(message,str) or not 1<=len(message)<=240 or any(ord(c)<32 for c in message):raise ValueError('Message must be 1–240 characters on one line.')
            params['message']=message
        with self.db() as db:db.execute('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?)',(device['id'],request,p['id'],action,time.time(),'','accepted',''))
        try:
            job=self.engine.enqueue(action,p['id'],params,'Mobile '+device['id'])
            with self.db() as db:db.execute('UPDATE commands SET job=?,status=? WHERE device=? AND request=?',(job['id'],job['status'],device['id'],request))
            return dict(request=request,job=job['id'],duplicate=False)
        except Exception as error:
            with self.db() as db:db.execute('UPDATE commands SET status=?,result=? WHERE device=? AND request=?',('failed',self.engine.redact(error)[:1000],device['id'],request))
            raise ValueError('Command was not accepted. Refresh command history before trying again.')
