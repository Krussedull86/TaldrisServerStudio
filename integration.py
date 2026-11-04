"""Integrated SteamCMD and Steam Workshop workflow for native desktop UI."""
from release_info import VERSION
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
        if self.running():raise ValueError('A SteamCMD job is already running. Wait for it or cancel it first.')
        if os.name!='nt':raise ValueError('SteamCMD installation and DayZ execution require Windows in this version.')
        validate(profile)
        if self.manager.running(profile) or profile['id'] in self.manager.busy:raise ValueError('Stop the server and wait for all jobs to finish.')
        # One process per installation, even across profiles. Never update a live shared root.
        for p in self.manager.state['servers']:
            if p['id']!=profile['id'] and (self.manager.running(p) or p['id'] in self.manager.busy) and Path(p['root']).resolve()==Path(profile['root']).resolve():raise ValueError('Another active profile is using the same server folder.')
        exe=Path(profile['steamcmd'])
        if not exe.is_file():raise ValueError('Download SteamCMD first in Get Started / Install wizard.')
        if kind not in ['login','server','mods','all']:raise ValueError('Unknown Steam job type.')
        self.ids=list(dict.fromkeys(ids if ids is not None else [m['id'] for m in profile['mods'] if m.get('enabled',True) and m.get('id')])) if kind in ('all','mods') else []
        if kind=='mods' and not self.ids:raise ValueError('Add at least one active Workshop mod first.')
        args=steam_arguments(profile,kind,self.ids)
        from steam_runtime import SteamEvidence
        self.evidence=SteamEvidence()
        self.profile=profile; self.kind=kind; self.chained=chained; self.raw=''; self.secrets=[]; self.was_cancelled=False; self.last_output=time.monotonic(); self.started_at=self.last_output; self.last_stage='Starting SteamCMD'; self.manager.busy.add(profile['id'])
        self.process.setProgram(str(exe.resolve())); self.process.setArguments(args); self.process.setWorkingDirectory(str(exe.resolve().parent)); self.active.emit(True); self.progress.emit(-1); self.raw='Starting SteamCMD.\nPlan: login → '+('DayZ Server 223350 → ' if kind in ('server','all') else '')+(str(len(self.ids))+' Workshop mods → ' if self.ids else '')+'quit.\nWaiting for messages from Steam …\n'; self.output.emit(self.sanitized()); self.detail.emit('Starting SteamCMD — no download has been confirmed yet.'); self.process.start(); self.watch.start()
    def sanitized(self):
        text=plain_terminal(self.raw[-240000:])
        for value in self.secrets:
            if value:text=text.replace(value,'[skjult]')
        return plain_terminal(text)
    def read(self):
        data=bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace')
        if not data:return
        self.raw+=data
        self.evidence.feed(data)
        # Keep output bounded. Passwords are never written to disk by this app.
        if len(self.raw)>1000000:self.raw=self.raw[-800000:]
        self.last_output=time.monotonic(); self.output.emit(self.sanitized())
        text=self.sanitized(); previous_stage=self.last_stage; self.last_stage=stage(text); self.detail.emit(self.last_stage)
        percent=progress_percent(plain_terminal(data))
        if percent is not None:self.progress.emit(percent)
        elif previous_stage!=self.last_stage:self.progress.emit(-1)
    def send_secret(self,value):
        if not self.running():raise ValueError('Start a SteamCMD job first.')
        if any(c in value for c in ['\n','\r','\x00']):raise ValueError('Send one line at a time.')
        self.secrets.append(value); self.process.write((value+'\n').encode()); self.output.emit(self.sanitized())
    def cancel(self):
        if self.running():self.was_cancelled=True; self.process.kill()
    def error(self,error):
        if error==QProcess.FailedToStart:self.complete(False,'SteamCMD failed to start: '+self.process.errorString())
    def finish(self,code,status):
        self.read()
        if self.profile is None:return
        ok,msg=result_summary(self.evidence.text(),self.kind,self.ids,code,(Path(self.profile['root'])/'DayZServer_x64.exe').is_file())
        if status!=QProcess.NormalExit:ok=False
        if self.was_cancelled:ok=False; msg='SteamCMD job was cancelled. No automatic install or server start is performed.'
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
        text=f'{self.last_stage} • elapsed {elapsed // 60:02d}:{elapsed % 60:02d} • last message {idle} s ago'
        if idle>=30:text+=' • No new messages; download is not confirmed.'
        self.detail.emit(text)

class IntegratedStudio(Studio):
    def __init__(self,home=None):
        self.tasks=set(); self.steam=None; self.workshop_results=[]; self.lookup_seq=0
        super().__init__(home); self.setWindowTitle('CruzDoodelZ Server Studio • '+VERSION)
        self.steam=SteamSession(self.manager,self); self.steam.output.connect(self.terminal_output); self.steam.completed.connect(self.steam_done); self.steam.active.connect(self.steam_active); self.steam.progress.connect(self.set_progress); self.steam.detail.connect(lambda text:self.terminal_detail.setText(text))
        self.page_names+=['Get started','Steam Workshop']; self.setup_page(); self.workshop_page()
        side=self.nav[0].parentWidget().layout()
        for index,title,icon in [(8,'Get started','▶'),(9,'Steam Workshop','▦')]:
            b=button(icon+'   '+title,lambda checked=False,n=index:self.go(n),'nav'); b.setCheckable(True); side.insertWidget(4+(index-8),b); self.nav.append(b)
        # Native controls remain usable at 1080p with ten destinations.
        self.setStyleSheet('QPushButton#nav {padding-top:10px;padding-bottom:10px;}')
        self.load_setup(); self.install_action_buttons(); self.install_local_controls(); self.go(8 if not self.p['root'] else 0)
    def run_task(self,fn,done,profile=None,description='Network job'):
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
        if self.manager.running(p) or p['id'] in self.manager.busy:raise ValueError('Stop the server and wait for the job to finish.')
        for other in self.manager.state['servers']:
            if other['id']!=p['id'] and (self.manager.running(other) or other['id'] in self.manager.busy) and Path(other['root']).resolve()==Path(p['root']).resolve():raise ValueError('Another active profile is using the same server folder.')
    def load(self):
        super().load()
        if hasattr(self,'setup_name'):self.load_setup()
    def install_local_controls(self):
        from PySide6.QtWidgets import QHBoxLayout
        row=QHBoxLayout(); row.addWidget(button('▣  Browse local @mods',self.action(self.browse_local_mods),'primary'))
        row.addWidget(button('Open selected mod folder',self.action(self.open_local_mod)))
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
            self.events.put(f'{len(added)} local mods added; {skipped} existing mods skipped. PBO files load directly from the development folders.')
    def open_local_mod(self):
        from core import mod_path
        path=mod_path(self.p,self.p['mods'][self.mod_index()])
        if not path.is_dir():raise ValueError('Mod folder does not exist: '+str(path))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    def install_action_buttons(self):
        # Add a path into the installer from the existing dashboard.
        self.statusBar().showMessage('Steam integration ready • Anonymous or account is chosen under Get Started')
    def setup_page(self):
        layout=self.page(); tabs=QTabWidget(); layout.addWidget(tabs,1)
        install=QWidget(); form_outer=QVBoxLayout(install); form_outer.setContentsMargins(16,16,16,16)
        f,c=card('FROM EMPTY FOLDER TO DAYZ SERVER','1. Choose folders & login  →  2. Download SteamCMD  →  3. Install server  →  4. Start'); form=QFormLayout(); c.addLayout(form)
        self.setup_name=QLineEdit(); self.setup_root=QLineEdit(); self.setup_steam=QLineEdit(); self.setup_user=QLineEdit(); self.setup_user.setPlaceholderText('Only needed when Steam requires an account')
        for title,w,kind in [('Server name',self.setup_name,None),('Server folder',self.setup_root,'root'),('SteamCMD folder',self.setup_steam,'steam')]:
            row=QWidget(); r=QHBoxLayout(row); r.setContentsMargins(0,0,0,0); r.addWidget(w)
            if kind:r.addWidget(button('Browse…',lambda checked=False,k=kind:self.setup_browse(k)))
            form.addRow(title,row)
        self.login=QComboBox(); self.login.addItems(['Anonymous','Steam account']); self.login.currentIndexChanged.connect(lambda i:self.setup_user.setEnabled(i==1)); form.addRow('Login',self.login); form.addRow('Steam username',self.setup_user)
        self.player_slots=QLineEdit('40'); form.addRow('Player slots',self.player_slots)
        self.mission=QComboBox(); self.mission.setEditable(True); self.mission.addItems(['dayzOffline.chernarusplus','dayzOffline.enoch','dayzOffline.sakhal','dayzOffline.nasdara']); mission_row=QHBoxLayout();mission_row.addWidget(self.mission,1);mission_row.addWidget(button('Save mission to CFG',self.action(self.save_mission_choice),'primary'));form.addRow('Mission / map',mission_row)
        self.start_after=QCheckBox('Start the server after a successful install'); self.start_after.setChecked(True); c.addWidget(self.start_after)
        self.setup_status=label('Choose folders to begin.','eyebrow'); c.addWidget(self.setup_status)
        buttons=QHBoxLayout();buttons.addWidget(button('Save setup',self.action(self.save_setup_and_map))); buttons.addWidget(button('↓ Download SteamCMD',self.action(self.bootstrap))); buttons.addWidget(button('Test login',self.action(self.login_test))); buttons.addWidget(button('Install & prepare',self.action(self.install_server),'primary')); c.addLayout(buttons)
        form_outer.addWidget(f); form_outer.addWidget(label('Anonymous is the default. Steam decides access: DayZ Server and especially Workshop often require a Steam account that owns DayZ. Password / Steam Guard is entered only in the SteamCMD Console tab — never stored in the profile.','muted')); form_outer.addStretch(); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(install); tabs.addTab(scroll,'Install wizard')
        console=QWidget(); cl=QVBoxLayout(console); self.console_status=label('No SteamCMD job running.','eyebrow'); cl.addWidget(self.console_status); self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(0); self.progress.setFormat('Download / verification: %p%'); self.progress.setToolTip('Movement without a percentage only indicates a running process. A download is confirmed only when Steam reports it.'); cl.addWidget(self.progress)
        self.terminal_detail=label('No download has been confirmed.','muted'); cl.addWidget(self.terminal_detail)
        self.terminal=QPlainTextEdit(); self.terminal.setReadOnly(True); self.terminal.setFont(QFont('Consolas',10)); self.terminal.setPlaceholderText('Live SteamCMD output appears here during downloads and login.'); cl.addWidget(self.terminal,1)
        self.secret=QLineEdit(); self.secret.setEchoMode(QLineEdit.Password); self.secret.setPlaceholderText('Password or Steam Guard code when Steam requests it …'); self.secret.returnPressed.connect(self.send_secret); self.secret.setEnabled(False)
        row=QHBoxLayout(); row.addWidget(self.secret,1); row.addWidget(button('Send to SteamCMD',self.send_secret)); row.addWidget(button('Cancel job',self.cancel_steam,'danger')); cl.addLayout(row)
        controls=QHBoxLayout(); self.follow_terminal=QCheckBox('Follow latest output'); self.follow_terminal.setChecked(True); controls.addWidget(self.follow_terminal); controls.addStretch(); controls.addWidget(button('Open SteamCMD log folder',self.open_steam_logs)); cl.addLayout(controls)
        cl.addWidget(label('Input is hidden and is never saved to the profile or activity log by this app. SteamCMD may keep login data in its own folder.','muted')); tabs.addTab(console,'SteamCMD console'); self.setup_tabs=tabs
        tools=QHBoxLayout(); tools.addWidget(button('Create config without download',self.action(self.create_config))); tools.addWidget(button('DirectX (Microsoft)',lambda:QDesktopServices.openUrl(QUrl(DIRECTX_PAGE)))); tools.addWidget(button('Start existing server',self.action(lambda:self.manager.start(self.p)),'primary')); tools.addStretch(); layout.addLayout(tools)
    def setup_browse(self,kind):
        p=QFileDialog.getExistingDirectory(self,'Choose folder')
        if p:(self.setup_root if kind=='root' else self.setup_steam).setText(p)
    def load_setup(self):
        p=self.p; self.setup_name.setText(p['name']); self.setup_root.setText(p['root'] or str(self.manager.home/'servers'/p['id'][:8])); self.setup_steam.setText(str(Path(p['steamcmd']).parent) if p['steamcmd'] else str(self.manager.home/'SteamCMD'))
        self.login.setCurrentIndex(1 if p.get('login_mode')=='account' else 0); self.setup_user.setText(p['steam_user']); self.setup_user.setEnabled(self.login.currentIndex()==1); self.player_slots.setText(str(p.get('max_players',40))); self.refresh_mission_choices()
    def refresh_mission_choices(self):
        from mission_settings import choices
        items,current=choices(self.p);self.mission.clear();self.mission.addItems(items);self.mission.setCurrentText(current)
    def save_mission_choice(self):
        from mission_settings import save_mission
        from config_documents import Document,digest
        if Path(self.setup_root.text()).resolve()!=Path(self.p['root']).resolve():raise ValueError('Save the server settings first if the server folder has changed.')
        mission=self.mission.currentText().strip();doc=Document(self.p,self.p['config'],self.manager.home)
        if hasattr(self,'center'):
            self.center.sync()
            if self.center.doc and self.center.doc.path==doc.path and self.center.doc.dirty:raise ValueError('Save or discard unsaved changes in the configuration editor first.')
        if getattr(self.manager,'remote',False):result=self.manager.client.call('mission_save',{'server':self.p['id'],'mission':mission,'base':digest(doc.original)});self.manager.refresh()
        else:result=save_mission(self.manager,self.p,mission,digest(doc.original))
        if hasattr(self,'center') and self.center.doc and self.center.doc.path==doc.path:self.center.doc=None;self.config_cache.pop(self.p['id'],None)
        self.load();self.setup_status.setText('Map selection saved to CFG with backup: '+mission+(' • The mission folder does not exist yet.' if not result['folder_exists'] else ''));self.events.put('Map selection saved: '+mission)
    def save_setup_and_map(self):
        mission=self.mission.currentText().strip();self.save_setup()
        if (Path(self.p['root'])/self.p['config']).is_file():self.mission.setCurrentText(mission);self.save_mission_choice()
        else:self.setup_status.setText('Settings saved. The map selection will be used when the configuration is created.')
    def save_setup(self):
        self.editable(); p=dict(self.p); p.update(name=self.setup_name.text().strip(),root=self.setup_root.text().strip(),steamcmd=str(Path(self.setup_steam.text().strip())/'steamcmd.exe'),steam_user=self.setup_user.text().strip(),login_mode='anonymous' if self.login.currentIndex()==0 else 'account',max_players=int(self.player_slots.text()),mission=self.mission.currentText().strip())
        if not p['name']:raise ValueError('Enter a server name.')
        if not self.setup_steam.text().strip():raise ValueError('Choose a SteamCMD folder.')
        if not 1<=p['max_players']<=127:raise ValueError('Choose 1–127 player slots.')
        if p['login_mode']=='account' and not p['steam_user']:raise ValueError('Enter a Steam username.')
        validate(p); p['workshop']=str(Path(p['steamcmd']).parent/'steamapps'/'workshop'/'content'/'221100'); self.p.update(p); self.manager.save(); self.load()
    def bootstrap(self,after=None):
        if self.steam.running():raise ValueError('Wait for the SteamCMD job to finish.')
        self.save_setup(); p=self.p; directory=Path(p['steamcmd']).parent; self.setup_status.setText('Downloading SteamCMD from Valve…')
        def ready(exe):
            p['steamcmd']=exe; self.manager.save(); self.events.put('SteamCMD downloaded or found.'); self.setup_status.setText('✓ SteamCMD is ready for first run.')
            if after:after(p)
        self.run_task(lambda:install_steamcmd(directory,self.events.put),ready,p,'SteamCMD download')
    def login_test(self):
        self.save_setup(); self.go(8); self.setup_tabs.setCurrentIndex(1); self.steam.start(self.p,'login')
    def install_server(self):
        self.save_setup(); p=self.p; p['start_after_install']=self.start_after.isChecked(); self.manager.save()
        def launch(target):self.go(8); self.setup_tabs.setCurrentIndex(1); self.steam.start(target,'all',chained=True)
        if not Path(p['steamcmd']).is_file():self.bootstrap(launch)
        else:launch(p)
    def create_config_for(self,p):
        path=Path(p['root'])/p['config']
        if path.exists():self.events.put('Keeping existing server config: '+str(path)); return
        provision(p,p['name'],p.get('max_players',40),p.get('mission','dayzOffline.chernarusplus')); self.events.put('Server configuration created.')
    def create_config(self):
        self.save_setup(); self.create_config_for(self.p); self.read_config(); self.setup_status.setText('✓ Configuration is ready.')
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
        self.console_status.setText('● STEAMCMD RUNNING — watch the log below' if active else '○ STEAMCMD IDLE'); self.secret.setEnabled(active)
    def set_progress(self,n):
        self.progress.setRange(0,0 if n<0 else 100)
        if n>=0:self.progress.setValue(n)
    def send_secret(self):
        value=self.secret.text(); self.secret.clear()
        if value:self.guard(lambda:self.steam.send_secret(value))
    def cancel_steam(self):
        if self.steam.running() and QMessageBox.question(self,'Cancel SteamCMD?','Cancel the download? Incomplete files will remain and can be re-downloaded.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.steam.cancel()
    def update_server(self,p=None):
        # The base class calls this from the GUI timer, never from a worker.
        if self.steam is None:return
        p=p or self.p; self.go(8); self.setup_tabs.setCurrentIndex(1); self.steam.start(p,'all')
    def steam_done(self,data):
        p=data['profile']; self.events.put(data['message']); self.console_status.setText(('✓ ' if data['ok'] else '✕ ')+data['message']); self.setup_status.setText(data['message']); self.terminal_detail.setText(data['message'])
        if not data['ok']:return
        if data['kind']=='login':
            self.events.put('Login accepted for this SteamCMD session. This does not guarantee download rights.'); return
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
                self.events.put('Download confirmed, but mod folders were not found. Server was not started. Set the Workshop folder in Settings.'); return
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
            self.manager.save(); self.events.put('Preparation complete for '+p['name']); self.refresh_backups()
            if self.p is p:self.read_config(); self.refresh_mods()
            if data['chained'] and p.get('start_after_install'):
                self.manager.start(p); self.events.put('Server process created. The application monitors startup; see the server window and RPT for status.'); self.go(0)
        self.run_task(deploy_and_finish,ready,p,'Preparation')
    def workshop_page(self):
        l=self.page(); row=QHBoxLayout(); self.ws_query=QLineEdit(); self.ws_query.setPlaceholderText('Search DayZ Steam Workshop…'); self.ws_query.returnPressed.connect(self.ws_search)
        self.ws_search_button=button('Search',self.ws_search,'primary'); self.ws_page=1
        row.addWidget(self.ws_query,1); row.addWidget(self.ws_search_button); row.addWidget(button('Previous',lambda:self.ws_search(-1))); row.addWidget(button('Next',lambda:self.ws_search(1))); l.addLayout(row)
        row=QHBoxLayout(); row.addWidget(button('+ Add via ID / link',self.ws_by_id)); row.addWidget(button('Import Workshop collection',self.ws_collection)); row.addWidget(button('Check mod updates',self.ws_check)); row.addWidget(button('Open Workshop website',self.ws_open_search)); l.addLayout(row)
        self.ws_status=label('Search for mods or paste a Workshop link. No API key required.','eyebrow'); l.addWidget(self.ws_status)
        self.ws_table=QTableWidget(0,4); self.ws_table.setHorizontalHeaderLabels(['MOD','WORKSHOP ID','SIZE','UPDATED']); self.ws_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch); self.ws_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents); self.ws_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.ws_table.setSelectionMode(QAbstractItemView.SingleSelection); self.ws_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.ws_table.itemSelectionChanged.connect(self.ws_selection); self.ws_table.doubleClicked.connect(lambda _:self.ws_add_selected()); l.addWidget(self.ws_table,1)
        self.ws_description=QPlainTextEdit(); self.ws_description.setReadOnly(True); self.ws_description.setMaximumHeight(115); self.ws_description.setPlaceholderText('Select a mod for its description and details.'); l.addWidget(self.ws_description)
        row=QHBoxLayout(); row.addWidget(button('Add selected mod to server',self.ws_add_selected,'primary')); row.addWidget(button('Open selected Workshop page',self.ws_open_selected)); row.addWidget(button('↓ Download and deploy enabled mods',self.action(self.download_mods))); l.addLayout(row)
        l.addWidget(label('Search and metadata come directly from Steam. Downloads use SteamCMD. Check dependencies and load order on the mod page. Collection import follows collection order.','muted'))
        # Add one-click download to the existing mod library too.
        self.stack.widget(2).layout().addWidget(button('Edit selected mod / client, server or both',self.action(self.edit_selected_mod)))
        self.stack.widget(2).layout().addWidget(button('↓ Download and deploy enabled Workshop mods',self.action(self.download_mods),'primary'))
    def ws_search(self,delta=0):
        if not self.ws_search_button.isEnabled():return
        self.ws_page=max(1,self.ws_page+delta) if delta else 1; page=self.ws_page; text=self.ws_query.text().strip(); self.ws_search_button.setEnabled(False); self.ws_status.setText(f'Searching Steam … page {page}')
        def loaded(items):self.ws_search_button.setEnabled(True); self.show_results(items); self.ws_status.setText(f'{len(items)} DayZ mods • page {page}')
        t=Task(lambda:search(text,page),self); self.tasks.add(t); t.done.connect(loaded)
        def failed(msg):self.ws_search_button.setEnabled(True); self.ws_status.setText(msg)
        t.failed.connect(failed); t.finished.connect(lambda:self.tasks.discard(t)); t.finished.connect(t.deleteLater); t.start()
    def show_results(self,items):
        self.workshop_results=items; self.ws_table.setRowCount(len(items))
        for i,m in enumerate(items):
            for j,v in enumerate([m['title'],m['id'],f"{m['size']/1024/1024:.1f} MB",time.strftime('%d.%m.%Y',time.localtime(m['updated'])) if m['updated'] else 'Unknown']):self.ws_table.setItem(i,j,QTableWidgetItem(v))
        if items:self.ws_table.selectRow(0)
    def ws_selection(self):
        i=self.ws_table.currentRow()
        if 0<=i<len(self.workshop_results):self.ws_description.setPlainText(self.workshop_results[i]['description'][:12000])
    def selected_item(self):
        i=self.ws_table.currentRow()
        if not 0<=i<len(self.workshop_results):raise ValueError('Select a Workshop mod first.')
        return self.workshop_results[i]
    def import_items(self,p,items):
        self.editable_profile(p); added=0
        for m in items:
            if m['file_type']!=0:raise ValueError('Use collection import for Workshop collections.')
            old=next((x for x in p['mods'] if x.get('id')==m['id']),None)
            if old:old.update(title=m['title'],remote_updated=m['updated']); continue
            p['mods'].append(dict(folder='@'+m['id'],id=m['id'],enabled=True,server=False,title=m['title'],remote_updated=m['updated'])); added+=1
        self.manager.save()
        if p is self.p:self.refresh_mods()
        self.events.put(f'{added} mods added to '+p['name']); self.ws_status.setText(f'{added} mods added. Download and deploy them to use them.')
    def ws_add_selected(self):self.guard(lambda:self.import_items(self.p,[self.selected_item()]))
    def ws_by_id(self):
        value,ok=QInputDialog.getText(self,'Fetch Workshop mod','Workshop ID or link:')
        if not ok or not value.strip():return
        p=self.p
        self.guard(lambda:self.run_task(lambda:details([workshop_id(value)]),lambda items:(self.import_items(p,items),self.show_results(items)),description='Workshop'))
    def ws_collection(self):
        value,ok=QInputDialog.getText(self,'Import collection','Workshop collection ID or link:')
        if not ok or not value.strip():return
        p=self.p
        def preview(items):
            names='\n'.join(x['title'] for x in items[:20]); extra=f'\n… and {len(items) - 20} more' if len(items)>20 else ''
            if QMessageBox.question(self,'Import collection',f"Add {len(items)} mods to {p['name']}?\n\n"+names+extra,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.import_items(p,items)
        self.guard(lambda:self.run_task(lambda:collection(value),preview,description='Workshop collection'))
    def ws_open_search(self):
        from urllib.parse import urlencode
        QDesktopServices.openUrl(QUrl('https://steamcommunity.com/workshop/browse/?'+urlencode({'appid':221100,'searchtext':self.ws_query.text()})))
    def ws_open_selected(self):self.guard(lambda:QDesktopServices.openUrl(QUrl(self.selected_item()['url'])))
    def ws_check(self):
        p=self.p; ids=[m['id'] for m in p['mods'] if m.get('id')]
        if not ids:return QMessageBox.information(self,'Workshop','Add Workshop mods first.')
        def received(items):
            newer=0; unknown=0
            for d in items:
                for m in p['mods']:
                    if m.get('id')==d['id']:
                        m['remote_updated']=d['updated']; m['title']=d['title']
                        installed=m.get('installed_updated',0)
                        if installed and d['updated']>installed:newer+=1
                        if not installed:unknown+=1
            self.manager.save(); self.show_results(items); self.ws_status.setText(f'{newer} newer versions • {unknown} without a verified local version'); self.refresh_mods()
        self.guard(lambda:self.run_task(lambda:details(ids),received,description='Update check'))
    def edit_selected_mod(self):
        self.editable(); i=self.mod_index(); old=self.p['mods'][i]
        if old.get('source')=='local':
            scope,ok=QInputDialog.getItem(self,'Local development mod','Loads directly from '+old['path'],['Mod (-mod)','Servermod (-serverMod)','Both (-mod + -serverMod)'],('client','server','both').index(mod_load_mode(old)),False)
            if ok:
                mode={'Mod (-mod)':'client','Servermod (-serverMod)':'server','Both (-mod + -serverMod)':'both'}[scope]
                old.update(server=mode=='server',load_mode=mode); self.mod_save()
            return
        folder,ok=QInputDialog.getText(self,'Mod folder','Mod folder name for next install:',text=old['folder'])
        if not ok:return
        scope,ok=QInputDialog.getItem(self,'Load mode',"Follow the mod author's instructions:",['Mod (-mod)','Servermod (-serverMod)','Both (-mod + -serverMod)'],('client','server','both').index(mod_load_mode(old)),False)
        if not ok:return
        mode={'Mod (-mod)':'client','Servermod (-serverMod)':'server','Both (-mod + -serverMod)':'both'}[scope]
        candidate=dict(old,folder=folder.strip(),server=mode=='server',load_mode=mode)
        mods=list(self.p['mods']); mods[i]=candidate; validate(dict(self.p,mods=mods))
        if any(j!=i and m['folder'].casefold()==candidate['folder'].casefold() for j,m in enumerate(mods)):raise ValueError('That mod folder is already in use.')
        self.p['mods']=mods; self.mod_save()
        if old['folder']!=candidate['folder']:self.events.put('New mod folder saved. The old folder is not deleted automatically. Reinstall the mod before starting.')
    def refresh_mods(self):
        super().refresh_mods()
        self.mods.horizontalHeaderItem(1).setText('MOD / FOLDER')
        self.mods.horizontalHeaderItem(4).setText('STATUS / UPDATE')
        for i,m in enumerate(self.p['mods']):
            if m.get('title'):
                self.mods.item(i,1).setText(m['title']+'  /  '+m['folder'])
            if m.get('source')=='local':
                self.mods.item(i,2).setText('Local / development')
                self.mods.item(i,1).setToolTip(m['path'])
                self.mods.item(i,4).setText(('Enabled' if m.get('enabled',True) else 'Inactive')+' / directly from disk')
                for col in range(self.mods.columnCount()):self.mods.item(i,col).setToolTip(m['path'])
                continue
            installed=m.get('installed_updated',0); remote=m.get('remote_updated',0)
            if installed and remote>installed:
                self.mods.item(i,4).setText('New version available')
            elif m.get('installed_at'):
                self.mods.item(i,4).setText('Installed' if m.get('enabled',True) else 'Installed / disabled')
            elif m.get('id'):
                self.mods.item(i,4).setText(('Enabled' if m.get('enabled',True) else 'Inactive')+' / installation not confirmed')
        self.filter_mods()
    def download_mods(self):
        self.go(8); self.setup_tabs.setCurrentIndex(1); self.steam.start(self.p,'mods')
    def closeEvent(self,event):
        if self.tasks or (self.steam and self.steam.running()):QMessageBox.information(self,'Job in progress','Wait for the job or cancel SteamCMD before exiting.'); event.ignore(); return
        super().closeEvent(event)
