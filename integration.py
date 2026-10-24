"""Integrated SteamCMD and Steam Workshop workflow for native desktop UI."""
import json, os, re, sys, time
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread, QProcess, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QCheckBox,QLabel,QPushButton,QPlainTextEdit,QProgressBar,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QInputDialog,QMessageBox,QFileDialog,QScrollArea,QTabWidget)
from desktop import Studio, card, label, button
from steam_services import (install_steamcmd,search,details,collection,workshop_id,steam_arguments,result_summary,provision)
from core import validate, mod_load_mode
from steam_terminal import terminal_process
from steam_status import plain_terminal,progress_percent,stage
from windows_runtime import DIRECTX_PAGE

class Task(QThread):
    done=Signal(object); failed=Signal(str)
    def __init__(self,fn,parent):super().__init__(parent); self.fn=fn
    def run(self):
        try:self.done.emit(self.fn())
        except Exception as e:self.failed.emit(str(e))

class SteamSession(QObject):
    output=Signal(str); completed=Signal(object); active=Signal(bool); progress=Signal(int); detail=Signal(str)
    def __init__(self,manager,parent=None):
        super().__init__(parent); self.manager=manager; self.process=terminal_process(self); self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read); self.process.finished.connect(self.finish); self.process.errorOccurred.connect(self.error)
        self.profile=None; self.raw=''; self.secrets=[]; self.kind=''; self.ids=[]; self.was_cancelled=False; self.chained=False; self.watch=QTimer(self); self.watch.setInterval(1000); self.watch.timeout.connect(self.remind)
    def running(self):return self.profile is not None
    def start(self,profile,kind,ids=None,chained=False):
        if self.running():raise ValueError('En SteamCMD-jobb kjører allerede. Vent eller avbryt den først.')
        if os.name!='nt':raise ValueError('SteamCMD-installasjon og DayZ-kjøring krever Windows i denne utgaven.')
        validate(profile)
        if self.manager.running(profile) or profile['id'] in self.manager.busy:raise ValueError('Stopp serveren og vent til alle jobber er ferdige.')
        # One process per installation, even across profiles. Never update a live shared root.
        for p in self.manager.state['servers']:
            if p['id']!=profile['id'] and (self.manager.running(p) or p['id'] in self.manager.busy) and Path(p['root']).resolve()==Path(profile['root']).resolve():raise ValueError('En annen aktiv profil bruker samme servermappe.')
        exe=Path(profile['steamcmd'])
        if not exe.is_file():raise ValueError('Last ned SteamCMD først i «Kom i gang».')
        if kind not in ['login','server','mods','all']:raise ValueError('Ukjent Steam-jobb.')
        self.ids=list(dict.fromkeys(ids if ids is not None else [m['id'] for m in profile['mods'] if m.get('enabled',True) and m.get('id')])) if kind in ('all','mods') else []
        if kind=='mods' and not self.ids:raise ValueError('Legg til minst én aktiv Workshop-mod først.')
        args=steam_arguments(profile,kind,self.ids)
        self.profile=profile; self.kind=kind; self.chained=chained; self.raw=''; self.secrets=[]; self.was_cancelled=False; self.last_output=time.monotonic(); self.started_at=self.last_output; self.last_stage='Starter SteamCMD'; self.manager.busy.add(profile['id'])
        self.process.setProgram(str(exe.resolve())); self.process.setArguments(args); self.process.setWorkingDirectory(str(exe.resolve().parent)); self.active.emit(True); self.progress.emit(-1); self.raw='Starter SteamCMD.\nPlan: innlogging → '+('DayZ Server 223350 → ' if kind in ('server','all') else '')+(str(len(self.ids))+' Workshop-mods → ' if self.ids else '')+'avslutt.\nVenter på meldinger fra Steam …\n'; self.output.emit(self.sanitized()); self.detail.emit('Starter SteamCMD — ingen nedlasting er bekreftet ennå.'); self.process.start(); self.watch.start()
    def sanitized(self):
        text=plain_terminal(self.raw[-240000:])
        for value in self.secrets:
            if value:text=text.replace(value,'[skjult]')
        return plain_terminal(text)
    def read(self):
        data=bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace')
        if not data:return
        self.raw+=data
        # Keep output bounded. Passwords are never written to disk by this app.
        if len(self.raw)>1000000:self.raw=self.raw[-800000:]
        self.last_output=time.monotonic(); self.output.emit(self.sanitized())
        text=self.sanitized(); previous_stage=self.last_stage; self.last_stage=stage(text); self.detail.emit(self.last_stage)
        percent=progress_percent(plain_terminal(data))
        if percent is not None:self.progress.emit(percent)
        elif previous_stage!=self.last_stage:self.progress.emit(-1)
    def send_secret(self,value):
        if not self.running():raise ValueError('Start en SteamCMD-jobb først.')
        if any(c in value for c in ['\n','\r','\x00']):raise ValueError('Send én linje om gangen.')
        self.secrets.append(value); self.process.write((value+'\n').encode()); self.output.emit(self.sanitized())
    def cancel(self):
        if self.running():self.was_cancelled=True; self.process.kill()
    def error(self,error):
        if error==QProcess.FailedToStart:self.complete(False,'SteamCMD kunne ikke starte: '+self.process.errorString())
    def finish(self,code,status):
        self.read()
        if self.profile is None:return
        ok,msg=result_summary(self.raw,self.kind,self.ids,code,(Path(self.profile['root'])/'DayZServer_x64.exe').is_file())
        if status!=QProcess.NormalExit:ok=False
        if self.was_cancelled:ok=False; msg='SteamCMD-jobben ble avbrutt. Ingen automatisk installasjon eller serverstart utføres.'
        self.complete(ok,msg)
    def complete(self,ok,msg):
        if self.profile is None:return
        p=self.profile; data=dict(profile=p,kind=self.kind,ids=self.ids,ok=ok,message=msg,chained=self.chained,output=self.raw)
        self.manager.busy.discard(p['id']); self.watch.stop(); self.profile=None; self.active.emit(False); self.progress.emit(100 if ok else 0)
        # Do not publish raw stdout to application logs, only result summary.
        self.completed.emit(data); self.raw=''; self.secrets=[]
    def remind(self):
        if not self.running():return
        idle=int(time.monotonic()-self.last_output); elapsed=int(time.monotonic()-self.started_at)
        text=f'{self.last_stage} • kjørt {elapsed//60:02d}:{elapsed%60:02d} • siste melding for {idle} s siden'
        if idle>=30:text+=' • Ingen nye meldinger; nedlasting er ikke bekreftet.'
        self.detail.emit(text)

class IntegratedStudio(Studio):
    def __init__(self,home=None):
        self.tasks=set(); self.steam=None; self.workshop_results=[]; self.lookup_seq=0
        super().__init__(home); self.setWindowTitle('Taldris Server Studio • 0.4 / Lokale utviklermods')
        self.steam=SteamSession(self.manager,self); self.steam.output.connect(self.terminal_output); self.steam.completed.connect(self.steam_done); self.steam.active.connect(self.steam_active); self.steam.progress.connect(self.set_progress); self.steam.detail.connect(lambda text:self.terminal_detail.setText(text))
        self.page_names+=['Kom i gang','Steam Workshop']; self.setup_page(); self.workshop_page()
        side=self.nav[0].parentWidget().layout()
        for index,title,icon in [(8,'Kom i gang','▶'),(9,'Steam Workshop','▦')]:
            b=button(icon+'   '+title,lambda checked=False,n=index:self.go(n),'nav'); b.setCheckable(True); side.insertWidget(4+(index-8),b); self.nav.append(b)
        # Native controls remain usable at 1080p with ten destinations.
        self.setStyleSheet('QPushButton#nav {padding-top:10px;padding-bottom:10px;}')
        self.load_setup(); self.install_action_buttons(); self.install_local_controls(); self.go(8 if not self.p['root'] else 0)
    def run_task(self,fn,done,profile=None,description='Nettverksjobb'):
        if profile:
            self.editable_profile(profile); self.manager.busy.add(profile['id'])
        t=Task(fn,self); self.tasks.add(t)
        def release():
            if profile:self.manager.busy.discard(profile['id'])
        def success(value):
            release(); self.guard(lambda:done(value))
        def failure(msg):release(); self.events.put(description+': '+msg); QMessageBox.warning(self,description,msg)
        t.done.connect(success); t.failed.connect(failure); t.finished.connect(lambda:self.tasks.discard(t)); t.finished.connect(t.deleteLater); t.start()
    def editable_profile(self,p):
        if self.manager.running(p) or p['id'] in self.manager.busy:raise ValueError('Stopp serveren og vent til jobben er ferdig.')
        for other in self.manager.state['servers']:
            if other['id']!=p['id'] and (self.manager.running(other) or other['id'] in self.manager.busy) and Path(other['root']).resolve()==Path(p['root']).resolve():raise ValueError('En annen aktiv profil bruker samme servermappe.')
    def load(self):
        super().load()
        if hasattr(self,'setup_name'):self.load_setup()
    def install_local_controls(self):
        from PySide6.QtWidgets import QHBoxLayout
        row=QHBoxLayout(); row.addWidget(button('▣  Bla gjennom lokale @mods',self.action(self.browse_local_mods),'primary'))
        row.addWidget(button('Åpne valgt modmappe',self.action(self.open_local_mod)))
        self.stack.widget(2).layout().insertLayout(1,row)
    def browse_local_mods(self):
        self.editable()
        from local_mod_ui import LocalModDialog
        dialog=LocalModDialog(self.p.get('local_scan_root',self.p.get('root','')),self)
        if dialog.exec():
            self.editable()
            from local_mods import import_mods
            added,skipped=import_mods(self.p,dialog.selected_rows,load_mode=('client','server','both')[dialog.scope.currentIndex()])
            self.p['local_scan_root']=dialog.directory.text(); self.manager.save(); self.refresh_mods()
            self.events.put(f'{len(added)} lokale mods lagt til; {skipped} eksisterende hoppet over. PBO-filer lastes direkte fra utviklingsmappene.')
    def open_local_mod(self):
        from core import mod_path
        path=mod_path(self.p,self.p['mods'][self.mod_index()])
        if not path.is_dir():raise ValueError('Modmappen finnes ikke: '+str(path))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    def install_action_buttons(self):
        # Add a path into the installer from the existing dashboard.
        self.statusBar().showMessage('Steam-integrasjon klar • Anonym eller konto velges under Kom i gang')
    def setup_page(self):
        layout=self.page(); tabs=QTabWidget(); layout.addWidget(tabs,1)
        install=QWidget(); form_outer=QVBoxLayout(install); form_outer.setContentsMargins(16,16,16,16)
        f,c=card('FRA TOM MAPPE TIL DAYZ-SERVER','1. Velg mapper og innlogging. 2. Last ned SteamCMD. 3. Installer serveren og opprett konfigurasjon. 4. Start.'); form=QFormLayout(); c.addLayout(form)
        self.setup_name=QLineEdit(); self.setup_root=QLineEdit(); self.setup_steam=QLineEdit(); self.setup_user=QLineEdit(); self.setup_user.setPlaceholderText('Bare nødvendig når Steam krever konto')
        for title,w,kind in [('Servernavn',self.setup_name,None),('Servermappe',self.setup_root,'root'),('SteamCMD-mappe',self.setup_steam,'steam')]:
            row=QWidget(); r=QHBoxLayout(row); r.setContentsMargins(0,0,0,0); r.addWidget(w)
            if kind:r.addWidget(button('Velg …',lambda checked=False,k=kind:self.setup_browse(k)))
            form.addRow(title,row)
        self.login=QComboBox(); self.login.addItems(['Anonym','Steam-konto']); self.login.currentIndexChanged.connect(lambda i:self.setup_user.setEnabled(i==1)); form.addRow('Innlogging',self.login); form.addRow('Steam-brukernavn',self.setup_user)
        self.player_slots=QLineEdit('40'); form.addRow('Spillerplasser',self.player_slots)
        self.mission=QComboBox(); self.mission.setEditable(True); self.mission.addItems(['dayzOffline.chernarusplus','dayzOffline.enoch','dayzOffline.sakhal']); form.addRow('Mission / kart',self.mission)
        self.start_after=QCheckBox('Start serveren etter vellykket installasjon og klargjøring'); self.start_after.setChecked(True); c.addWidget(self.start_after)
        self.setup_status=label('Velg mapper for å begynne.','eyebrow'); c.addWidget(self.setup_status)
        buttons=QHBoxLayout(); buttons.addWidget(button('↓ Last ned SteamCMD',self.action(self.bootstrap))); buttons.addWidget(button('Test innlogging',self.action(self.login_test))); buttons.addWidget(button('Installer og klargjør',self.action(self.install_server),'primary')); c.addLayout(buttons)
        form_outer.addWidget(f); form_outer.addWidget(label('Anonym er førstevalg. Steam bestemmer tilgangen: DayZ Server og særlig Workshop kan kreve Steam-konto med nødvendig tilgang. Passord/Steam Guard sendes i fanen SteamCMD-konsoll, ikke i oppsettfilen.','muted')); form_outer.addStretch(); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(install); tabs.addTab(scroll,'Oppstartsveiviser')
        console=QWidget(); cl=QVBoxLayout(console); self.console_status=label('Ingen SteamCMD-jobb kjører.','eyebrow'); cl.addWidget(self.console_status); self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(0); self.progress.setFormat('Nedlasting / kontroll: %p%'); self.progress.setToolTip('Bevegelse uten prosent betyr bare at prosessen kjører. Nedlasting er først bekreftet når Steam rapporterer den.'); cl.addWidget(self.progress)
        self.terminal_detail=label('Ingen nedlasting er bekreftet.','muted'); cl.addWidget(self.terminal_detail)
        self.terminal=QPlainTextEdit(); self.terminal.setReadOnly(True); self.terminal.setFont(QFont('Consolas',10)); self.terminal.setPlaceholderText('Live utdata fra SteamCMD vises her under nedlasting og innlogging.'); cl.addWidget(self.terminal,1)
        self.secret=QLineEdit(); self.secret.setEchoMode(QLineEdit.Password); self.secret.setPlaceholderText('Passord eller Steam Guard-kode når Steam ber om det …'); self.secret.returnPressed.connect(self.send_secret); self.secret.setEnabled(False)
        row=QHBoxLayout(); row.addWidget(self.secret,1); row.addWidget(button('Send til SteamCMD',self.send_secret)); row.addWidget(button('Avbryt jobb',self.cancel_steam,'danger')); cl.addLayout(row)
        controls=QHBoxLayout(); self.follow_terminal=QCheckBox('Følg siste melding'); self.follow_terminal.setChecked(True); controls.addWidget(self.follow_terminal); controls.addStretch(); controls.addWidget(button('Åpne SteamCMD-loggmappe',self.open_steam_logs)); cl.addLayout(controls)
        cl.addWidget(label('Input skjules og lagres ikke i profil eller aktivitetslogg av programmet. SteamCMD kan selv beholde innloggingsdata i sin egen mappe. SteamCMD-jobben er separat fra abonnementer i Steam-klienten.','muted')); tabs.addTab(console,'SteamCMD-konsoll'); self.setup_tabs=tabs
        tools=QHBoxLayout(); tools.addWidget(button('Opprett konfigurasjon uten nedlasting',self.action(self.create_config))); tools.addWidget(button('DirectX (Microsoft)',lambda:QDesktopServices.openUrl(QUrl(DIRECTX_PAGE)))); tools.addWidget(button('Start eksisterende server',self.action(lambda:self.manager.start(self.p)),'primary')); tools.addStretch(); layout.addLayout(tools)
    def setup_browse(self,kind):
        p=QFileDialog.getExistingDirectory(self,'Velg mappe')
        if p:(self.setup_root if kind=='root' else self.setup_steam).setText(p)
    def load_setup(self):
        p=self.p; self.setup_name.setText(p['name']); self.setup_root.setText(p['root'] or str(self.manager.home/'servers'/p['id'][:8])); self.setup_steam.setText(str(Path(p['steamcmd']).parent) if p['steamcmd'] else str(self.manager.home/'SteamCMD'))
        self.login.setCurrentIndex(1 if p.get('login_mode')=='account' else 0); self.setup_user.setText(p['steam_user']); self.setup_user.setEnabled(self.login.currentIndex()==1); self.player_slots.setText(str(p.get('max_players',40))); self.mission.setCurrentText(p.get('mission','dayzOffline.chernarusplus'))
    def save_setup(self):
        self.editable(); p=dict(self.p); p.update(name=self.setup_name.text().strip(),root=self.setup_root.text().strip(),steamcmd=str(Path(self.setup_steam.text().strip())/'steamcmd.exe'),steam_user=self.setup_user.text().strip(),login_mode='anonymous' if self.login.currentIndex()==0 else 'account',max_players=int(self.player_slots.text()),mission=self.mission.currentText().strip())
        if not p['name']:raise ValueError('Oppgi servernavn.')
        if not self.setup_steam.text().strip():raise ValueError('Velg SteamCMD-mappe.')
        if not 1<=p['max_players']<=127:raise ValueError('Velg 1–127 spillerplasser.')
        if p['login_mode']=='account' and not p['steam_user']:raise ValueError('Oppgi Steam-brukernavn.')
        validate(p); p['workshop']=str(Path(p['steamcmd']).parent/'steamapps'/'workshop'/'content'/'221100'); self.p.update(p); self.manager.save(); self.load()
    def bootstrap(self,after=None):
        if self.steam.running():raise ValueError('Vent til SteamCMD-jobben er ferdig.')
        self.save_setup(); p=self.p; directory=Path(p['steamcmd']).parent; self.setup_status.setText('Laster ned SteamCMD fra Valve …')
        def ready(exe):
            p['steamcmd']=exe; self.manager.save(); self.events.put('SteamCMD lastet ned eller funnet.'); self.setup_status.setText('✓ SteamCMD er klar for første kjøring.')
            if after:after(p)
        self.run_task(lambda:install_steamcmd(directory,self.events.put),ready,p,'SteamCMD-nedlasting')
    def login_test(self):
        self.save_setup(); self.go(8); self.setup_tabs.setCurrentIndex(1); self.steam.start(self.p,'login')
    def install_server(self):
        self.save_setup(); p=self.p; p['start_after_install']=self.start_after.isChecked(); self.manager.save()
        def launch(target):self.go(8); self.setup_tabs.setCurrentIndex(1); self.steam.start(target,'all',chained=True)
        if not Path(p['steamcmd']).is_file():self.bootstrap(launch)
        else:launch(p)
    def create_config_for(self,p):
        path=Path(p['root'])/p['config']
        if path.exists():self.events.put('Beholder eksisterende serverkonfigurasjon: '+str(path)); return
        provision(p,p['name'],p.get('max_players',40),p.get('mission','dayzOffline.chernarusplus')); self.events.put('Serverkonfigurasjon opprettet.')
    def create_config(self):
        self.save_setup(); self.create_config_for(self.p); self.read_config(); self.setup_status.setText('✓ Konfigurasjonen er klar.')
    def terminal_output(self,text):
        bar=self.terminal.verticalScrollBar(); position=bar.value(); self.terminal.setPlainText(text)
        bar.setValue(bar.maximum() if self.follow_terminal.isChecked() else position)
    def open_steam_logs(self):
        p=self.steam.profile if self.steam and self.steam.running() else self.p
        if not p.get('steamcmd'):return
        path=Path(p['steamcmd']).parent/'logs'
        if not path.is_dir():path=path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    def steam_active(self,active):
        self.console_status.setText('● STEAMCMD KJØRER — følg utdata nedenfor' if active else '○ STEAMCMD AVSLUTTET'); self.secret.setEnabled(active)
    def set_progress(self,n):
        self.progress.setRange(0,0 if n<0 else 100)
        if n>=0:self.progress.setValue(n)
    def send_secret(self):
        value=self.secret.text(); self.secret.clear()
        if value:self.guard(lambda:self.steam.send_secret(value))
    def cancel_steam(self):
        if self.steam.running() and QMessageBox.question(self,'Avbryt SteamCMD?','Avbryte nedlastingen? Ufullstendige filer blir liggende og kan lastes ned på nytt.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.steam.cancel()
    def update_server(self,p=None):
        # The base class calls this from the GUI timer, never from a worker.
        if self.steam is None:return
        p=p or self.p; self.go(8); self.setup_tabs.setCurrentIndex(1); self.steam.start(p,'all')
    def steam_done(self,data):
        p=data['profile']; self.events.put(data['message']); self.console_status.setText(('✓ ' if data['ok'] else '✕ ')+data['message']); self.setup_status.setText(data['message']); self.terminal_detail.setText(data['message'])
        if not data['ok']:return
        if data['kind']=='login':
            self.events.put('Innlogging godkjent for denne SteamCMD-økten. Det garanterer ikke nedlastingstillatelse.'); return
        # Resolve SteamCMD's actual output location, not a guessed path.
        paths=[]
        for match in re.finditer(r'Success\.\s*Downloaded item\s+(\d+)\s+to\s+"([^"]+)"',data['output'],re.I):
            if match.group(1) in data['ids']:
                path=Path(match.group(2))
                if path.name==match.group(1) and path.is_dir():paths.append(path.parent)
        bases=paths+[Path(p['steamcmd']).parent/'steamapps'/'workshop'/'content'/'221100',Path(p['root'])/'steamapps'/'workshop'/'content'/'221100']
        if data['ids']:
            base=next((b for b in bases if all((b/wid/'addons').is_dir() for wid in data['ids'])),None)
            if base is None:
                self.events.put('Nedlasting bekreftet, men modmappene ble ikke funnet. Ingen serverstart utføres. Velg Workshop-mappe i Innstillinger.'); return
            p['workshop']=str(base); self.manager.save()
        def deploy_and_finish():
            if data['ids']:self.manager.deploy(p)
            if data['chained']:self.create_config_for(p)
            return True
        def ready(_):
            p['_deployment_ok']=True
            stamp=time.time()
            for m in p['mods']:
                if m.get('id') in data['ids']:m['installed_at']=stamp; m['installed_updated']=m.get('remote_updated',0)
            self.manager.save(); self.events.put('Klargjøring ferdig for '+p['name']); self.refresh_backups()
            if self.p is p:self.read_config(); self.refresh_mods()
            if data['chained'] and p.get('start_after_install'):
                self.manager.start(p); self.events.put('Serverprosessen er opprettet. Programmet følger oppstarten; se servervinduet og RPT for status.'); self.go(0)
        self.run_task(deploy_and_finish,ready,p,'Klargjøring')
    def workshop_page(self):
        l=self.page(); row=QHBoxLayout(); self.ws_query=QLineEdit(); self.ws_query.setPlaceholderText('Søk direkte i DayZ Steam Workshop …'); self.ws_query.returnPressed.connect(self.ws_search)
        self.ws_search_button=button('Søk',self.ws_search,'primary'); self.ws_page=1
        row.addWidget(self.ws_query,1); row.addWidget(self.ws_search_button); row.addWidget(button('Forrige',lambda:self.ws_search(-1))); row.addWidget(button('Neste',lambda:self.ws_search(1))); l.addLayout(row)
        row=QHBoxLayout(); row.addWidget(button('+ Legg til via ID / lenke',self.ws_by_id)); row.addWidget(button('Importer Workshop-samling',self.ws_collection)); row.addWidget(button('Sjekk modoppdateringer',self.ws_check)); row.addWidget(button('Åpne Workshop-nettside',self.ws_open_search)); l.addLayout(row)
        self.ws_status=label('Søk etter mods eller lim inn en Workshop-lenke. Ingen API-nøkkel kreves.','eyebrow'); l.addWidget(self.ws_status)
        self.ws_table=QTableWidget(0,4); self.ws_table.setHorizontalHeaderLabels(['MOD','WORKSHOP-ID','STØRRELSE','OPPDATERT']); self.ws_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch); self.ws_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents); self.ws_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.ws_table.setSelectionMode(QAbstractItemView.SingleSelection); self.ws_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.ws_table.itemSelectionChanged.connect(self.ws_selection); self.ws_table.doubleClicked.connect(lambda _:self.ws_add_selected()); l.addWidget(self.ws_table,1)
        self.ws_description=QPlainTextEdit(); self.ws_description.setReadOnly(True); self.ws_description.setMaximumHeight(115); self.ws_description.setPlaceholderText('Velg en mod for beskrivelse og detaljer.'); l.addWidget(self.ws_description)
        row=QHBoxLayout(); row.addWidget(button('Legg valgt mod til server',self.ws_add_selected,'primary')); row.addWidget(button('Åpne valgt Workshop-side',self.ws_open_selected)); row.addWidget(button('↓ Last ned og installer aktive mods',self.action(self.download_mods))); l.addLayout(row)
        l.addWidget(label('Søk og metadata hentes direkte fra Steam. Nedlasting skjer via SteamCMD. Avhengigheter og lastrekkefølge må kontrolleres på moddens side. Samlingsimport følger samlingens rekkefølge.','muted'))
        # Add one-click download to the existing mod library too.
        self.stack.widget(2).layout().addWidget(button('Endre valgt mod / mod, servermod eller begge',self.action(self.edit_selected_mod)))
        self.stack.widget(2).layout().addWidget(button('↓ Last ned og installer aktive Workshop-mods',self.action(self.download_mods),'primary'))
    def ws_search(self,delta=0):
        if not self.ws_search_button.isEnabled():return
        self.ws_page=max(1,self.ws_page+delta) if delta else 1; page=self.ws_page; text=self.ws_query.text().strip(); self.ws_search_button.setEnabled(False); self.ws_status.setText(f'Søker på Steam … side {page}')
        def loaded(items):self.ws_search_button.setEnabled(True); self.show_results(items); self.ws_status.setText(f'{len(items)} DayZ-mods • side {page}')
        t=Task(lambda:search(text,page),self); self.tasks.add(t); t.done.connect(loaded)
        def failed(msg):self.ws_search_button.setEnabled(True); self.ws_status.setText(msg)
        t.failed.connect(failed); t.finished.connect(lambda:self.tasks.discard(t)); t.finished.connect(t.deleteLater); t.start()
    def show_results(self,items):
        self.workshop_results=items; self.ws_table.setRowCount(len(items))
        for i,m in enumerate(items):
            for j,v in enumerate([m['title'],m['id'],f"{m['size']/1024/1024:.1f} MB",time.strftime('%d.%m.%Y',time.localtime(m['updated'])) if m['updated'] else 'Ukjent']):self.ws_table.setItem(i,j,QTableWidgetItem(v))
        if items:self.ws_table.selectRow(0)
    def ws_selection(self):
        i=self.ws_table.currentRow()
        if 0<=i<len(self.workshop_results):self.ws_description.setPlainText(self.workshop_results[i]['description'][:12000])
    def selected_item(self):
        i=self.ws_table.currentRow()
        if not 0<=i<len(self.workshop_results):raise ValueError('Velg en Workshop-mod først.')
        return self.workshop_results[i]
    def import_items(self,p,items):
        self.editable_profile(p); added=0
        for m in items:
            if m['file_type']!=0:raise ValueError('Bruk samlingsimport for Workshop-samlinger.')
            old=next((x for x in p['mods'] if x.get('id')==m['id']),None)
            if old:old.update(title=m['title'],remote_updated=m['updated']); continue
            p['mods'].append(dict(folder='@'+m['id'],id=m['id'],enabled=True,server=False,title=m['title'],remote_updated=m['updated'])); added+=1
        self.manager.save()
        if p is self.p:self.refresh_mods()
        self.events.put(f'{added} mods lagt til i '+p['name']); self.ws_status.setText(f'{added} mods lagt til. Last ned og installer for å bruke dem.')
    def ws_add_selected(self):self.guard(lambda:self.import_items(self.p,[self.selected_item()]))
    def ws_by_id(self):
        value,ok=QInputDialog.getText(self,'Hent Workshop-mod','Workshop-ID eller lenke:')
        if not ok or not value.strip():return
        p=self.p
        self.guard(lambda:self.run_task(lambda:details([workshop_id(value)]),lambda items:(self.import_items(p,items),self.show_results(items)),description='Workshop'))
    def ws_collection(self):
        value,ok=QInputDialog.getText(self,'Importer samling','Workshop-samlingens ID eller lenke:')
        if not ok or not value.strip():return
        p=self.p
        def preview(items):
            names='\n'.join(x['title'] for x in items[:20]); extra=f'\n… og {len(items)-20} til' if len(items)>20 else ''
            if QMessageBox.question(self,'Importer samling',f'Legge {len(items)} mods til {p["name"]}?\n\n'+names+extra,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.import_items(p,items)
        self.guard(lambda:self.run_task(lambda:collection(value),preview,description='Workshop-samling'))
    def ws_open_search(self):
        from urllib.parse import urlencode
        QDesktopServices.openUrl(QUrl('https://steamcommunity.com/workshop/browse/?'+urlencode({'appid':221100,'searchtext':self.ws_query.text()})))
    def ws_open_selected(self):self.guard(lambda:QDesktopServices.openUrl(QUrl(self.selected_item()['url'])))
    def ws_check(self):
        p=self.p; ids=[m['id'] for m in p['mods'] if m.get('id')]
        if not ids:return QMessageBox.information(self,'Workshop','Legg til Workshop-mods først.')
        def received(items):
            newer=0; unknown=0
            for d in items:
                for m in p['mods']:
                    if m.get('id')==d['id']:
                        m['remote_updated']=d['updated']; m['title']=d['title']
                        installed=m.get('installed_updated',0)
                        if installed and d['updated']>installed:newer+=1
                        if not installed:unknown+=1
            self.manager.save(); self.show_results(items); self.ws_status.setText(f'{newer} nyere versjoner • {unknown} uten bekreftet lokal versjon'); self.refresh_mods()
        self.guard(lambda:self.run_task(lambda:details(ids),received,description='Oppdateringssjekk'))
    def edit_selected_mod(self):
        self.editable(); i=self.mod_index(); old=self.p['mods'][i]
        if old.get('source')=='local':
            scope,ok=QInputDialog.getItem(self,'Lokal utviklermod','Lastes direkte fra '+old['path'],['Mod (-mod)','Servermod (-serverMod)','Begge (-mod + -serverMod)'],('client','server','both').index(mod_load_mode(old)),False)
            if ok:
                mode={'Mod (-mod)':'client','Servermod (-serverMod)':'server','Begge (-mod + -serverMod)':'both'}[scope]
                old.update(server=mode=='server',load_mode=mode); self.mod_save()
            return
        folder,ok=QInputDialog.getText(self,'Modmappe','Navn på modmappe ved neste installasjon:',text=old['folder'])
        if not ok:return
        scope,ok=QInputDialog.getItem(self,'Modtype','Følg modforfatterens anvisning:',['Mod (-mod)','Servermod (-serverMod)','Begge (-mod + -serverMod)'],('client','server','both').index(mod_load_mode(old)),False)
        if not ok:return
        mode={'Mod (-mod)':'client','Servermod (-serverMod)':'server','Begge (-mod + -serverMod)':'both'}[scope]
        candidate=dict(old,folder=folder.strip(),server=mode=='server',load_mode=mode)
        mods=list(self.p['mods']); mods[i]=candidate; validate(dict(self.p,mods=mods))
        if any(j!=i and m['folder'].casefold()==candidate['folder'].casefold() for j,m in enumerate(mods)):raise ValueError('Modmappen er allerede i bruk.')
        self.p['mods']=mods; self.mod_save()
        if old['folder']!=candidate['folder']:self.events.put('Ny modmappe lagret. Den gamle mappen slettes ikke automatisk. Installer modden på nytt før oppstart.')
    def refresh_mods(self):
        super().refresh_mods()
        self.mods.horizontalHeaderItem(1).setText('MOD / MAPPE')
        self.mods.horizontalHeaderItem(4).setText('STATUS / OPPDATERING')
        for i,m in enumerate(self.p['mods']):
            if m.get('title'):
                self.mods.item(i,1).setText(m['title']+'  /  '+m['folder'])
            if m.get('source')=='local':
                self.mods.item(i,2).setText('Lokal / utvikling')
                self.mods.item(i,1).setToolTip(m['path'])
                self.mods.item(i,4).setText(('Aktiv' if m.get('enabled',True) else 'Inaktiv')+' / direkte fra disk')
                for col in range(self.mods.columnCount()):self.mods.item(i,col).setToolTip(m['path'])
                continue
            installed=m.get('installed_updated',0); remote=m.get('remote_updated',0)
            if installed and remote>installed:
                self.mods.item(i,4).setText('Ny versjon tilgjengelig')
            elif m.get('installed_at'):
                self.mods.item(i,4).setText('Installert' if m.get('enabled',True) else 'Installert / inaktiv')
            elif m.get('id'):
                self.mods.item(i,4).setText(('Aktiv' if m.get('enabled',True) else 'Inaktiv')+' / ikke bekreftet installert')
        self.filter_mods()
    def download_mods(self):
        self.go(8); self.setup_tabs.setCurrentIndex(1); self.steam.start(self.p,'mods')
    def closeEvent(self,event):
        if self.tasks or (self.steam and self.steam.running()):QMessageBox.information(self,'Jobb pågår','Vent på jobben eller avbryt SteamCMD før programmet avsluttes.'); event.ignore(); return
        super().closeEvent(event)
