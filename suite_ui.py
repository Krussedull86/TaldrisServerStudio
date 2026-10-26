"""Complete desktop workspace; the headless agent owns every server process."""
import json,time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPlainTextEdit,QComboBox,QCheckBox,QInputDialog,QFileDialog,QMessageBox,QScrollArea)
from desktop import label,button,card
from operations_ui import OperationsStudio
from agent_client import RemoteManager,RemoteSteamSession,version_key
from editors_ui import ConfigCenter
from map_workbench import MapWorkbench


class SuiteStudio(OperationsStudio):
    manager_class=RemoteManager
    def __init__(self,home=None):
        self.config_cache={};self.center_server=None;self.disconnected=False
        super().__init__(home)
        # Replace the temporary local Steam wrapper before any job is started.
        self.steam.deleteLater();self.steam=RemoteSteamSession(self.manager,self);self.steam.output.connect(self.terminal_output);self.steam.completed.connect(self.steam_done);self.steam.active.connect(self.steam_active);self.steam.progress.connect(self.set_progress);self.steam.detail.connect(self.terminal_detail.setText)
        self.op_timer.stop();self.op_timer.timeout.disconnect();self.op_timer.timeout.connect(self.operations_tick);self.op_timer.start(3000)
        self.page_names+=['RCon og spillere','Discord og tjeneste'];self.rcon_page();self.host_page()
        side=self.nav[0].parentWidget().layout()
        for index,title in [(11,'RCon og spillere'),(12,'Discord / tjeneste')]:
            b=button(title,lambda checked=False,n=index:self.go(n),'nav');b.setCheckable(True);side.insertWidget(side.count()-4,b);self.nav.append(b)
        self.setStyleSheet('QPushButton#nav {padding-top:7px;padding-bottom:7px;}');self.load_host_settings()
        self.stack.widget(10).layout().insertWidget(0,button('Installer programmet på denne PC-en',lambda:self.guard(self.install_application),'primary'))
        for page in (7,8):self.stack.widget(page).layout().insertWidget(0,button('Importer eksisterende server fra BAT / CMD …',lambda:self.guard(self.import_batch_file),'primary'))
        self.statusBar().showMessage('Tilkoblet bakgrunnsagent • Serverne styres uavhengig av programvinduet')
    def import_batch_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Importer eksisterende server','','Startskript (*.bat *.cmd)')
        if not path:return
        from batch_import_ui import BatchImportDialog
        dialog=BatchImportDialog(self,path)
        if dialog.exec() and dialog.result_profile:
            identity=dialog.result_profile['id'];self.config_cache.pop(identity,None)
            if self.center_server==identity:self.center.doc=None;self.center_server=None
            if hasattr(self.workbench,'cache'):self.workbench.cache.pop(identity,None)
            if self.workbench.server_id==identity:self.workbench.layers=[];self.workbench.server_id=None
            self.p=dialog.result_profile;self.load();self.go(7);self.events.put('Eksisterende serverprofil importert fra BAT. Ingen serverfiler er endret.')
    def check_import_target(self,identity):
        if not identity:return
        self.center.sync();docs=[self.config_cache.get(identity)]
        if self.center_server==identity:docs.append(self.center.doc)
        layers=self.workbench.layers if self.workbench.server_id==identity else getattr(self.workbench,'cache',{}).get(identity,[])
        if any(doc and doc.dirty for doc in docs) or any(layer['doc'].dirty for layer in layers):raise ValueError('Lagre eller forkast kart- og konfigurasjonsendringer for denne profilen før import.')
    def load(self):
        super().load()
        if hasattr(self,'rcon_path'):self.rcon_path.setText(self.p.get('rcon_config',''))
    def overview(self):
        super().overview()
        hero_layout=self.start_btn.parentWidget().layout();actions=hero_layout.itemAt(hero_layout.count()-1).layout()
        actions.insertWidget(2,button('Restart …',lambda:self.guard(lambda:self.countdown('restart'))));actions.insertWidget(3,button('Trygg stopp …',lambda:self.guard(lambda:self.countdown('stop'))))
        from PySide6.QtWidgets import QLabel
        for widget in self.stack.widget(0).findChildren(QLabel):
            if widget.text()=='Live data ikke tilkoblet':widget.setText('Siste svar fra Steam query')
    def backups_page(self):
        super().backups_page();page=self.stack.widget(5);page.layout().addWidget(button('Gjenopprett valgt backup …',lambda:self.guard(self.restore_backup),'primary'))
        from PySide6.QtWidgets import QLabel
        for widget in page.findChildren(QLabel):
            if 'Gjenoppretting gjøres manuelt' in widget.text():widget.setText('Inkluderer konfigurasjon, profiles, mpmissions og battleye. Gjenoppretting krever stoppet server og tar ny backup først. Arkiver kan inneholde passord og spillerdata.')
    def map_page(self):
        layout=self.page();self.workbench=MapWorkbench(self);self.map=self.workbench.view;layout.addWidget(self.workbench)
    def refresh_map(self):self.workbench.reload_server()
    def config_page(self):
        layout=self.page();self.center=ConfigCenter(self);self.editor=self.center.raw;layout.addWidget(self.center)
    def read_config(self):
        if not hasattr(self,'center'):return
        if self.center_server and self.center.doc:self.center.sync();self.config_cache[self.center_server]=self.center.doc
        if self.center_server!=self.p['id']:
            self.center_server=self.p['id'];self.center.doc=self.config_cache.get(self.p['id']);self.center.loading=True;self.center.raw.setPlainText(self.center.doc.text if self.center.doc else '');self.center.loading=False
        self.center.discover()
        if self.center.doc:self.center.rebuild()
        elif self.p['root'] and (Path(self.p['root'])/self.p['config']).is_file():self.center.open_path(self.p['config'])
    def editable_document(self,doc):
        from mission_settings import check_config_edit
        check_config_edit(self.manager,doc.profile,doc.relative)
    def save_config(self):self.center.save()
    def create_config_for(self,p):
        path=Path(p['root'])/p['config']
        if path.exists():self.events.put('Beholder eksisterende serverkonfigurasjon: '+str(path));return
        self.manager.wait_job(self.manager.enqueue('create_config',p))
    def bootstrap(self,after=None):
        self.save_setup();p=self.p;self.setup_status.setText('Agenten henter SteamCMD fra Valve …');job=self.manager.enqueue('bootstrap',p)
        def ready(exe):
            self.manager.refresh();self.setup_status.setText('SteamCMD er klar.')
            if after:after(p)
        self.run_task(lambda:self.manager.wait_job(job,timeout=90),ready,description='SteamCMD-nedlasting')
    def steam_done(self,data):
        self.events.put(data['message']);self.console_status.setText(data['message']);self.setup_status.setText(data['message']);self.terminal_detail.setText(data['message']);self.manager.refresh();self.refresh_mods()
        if data['ok'] and data['chained'] and data['profile'].get('start_after_install'):self.manager.start(data['profile'])
    def begin_maintenance(self,p,restart):
        self.manager.enqueue('maintenance',p,{'restart':restart});return True
    def maintenance_failed(self,p,msg):self.events.put(p['name']+': '+str(msg))
    def check_mods_automatic(self,p):return
    def operations_tick(self):
        if not getattr(self,'operations_ready',False):return
        p=self.p;runtime=self.manager.runtime.get(p['id'],{});record=runtime.get('launch',{})
        text='Bakgrunnsagent: '+('Windows-tjeneste' if self.manager.raw.get('service') else 'egen prosess (installer tjeneste for drift etter avlogging)')+'\n'+p['name']+' • '+('Prosess kjører' if runtime.get('running') else 'Stoppet')+' • RAM '+str(runtime.get('ram_mb','—'))+' MB • CPU '+str(runtime.get('cpu_percent','—'))+' % • Ledig disk '+str(runtime.get('disk_free_gb','—'))+' GB\nVedlikehold: '+p.get('maintenance_state','idle')
        health=runtime.get('health',{})
        if health.get('responding'):text+='\nSteam query svarer • '+str(health.get('players',0))+'/'+str(health.get('max_players','?'))+' spillere • '+health.get('map','')
        elif not p.get('query_enabled',True):text+='\nLokal test • query-sjekk av • direkte tilkobling 127.0.0.1:'+str(p['port'])
        elif runtime.get('running'):text+='\nSteam query har ikke svart ennå / svar mangler.'
        if record.get('restart_due'):text+='\nNeste restart: '+time.strftime('%d.%m %H:%M',time.localtime(record['restart_due']))
        if p.get('shutdown_request'):text+='\nManuell nedtelling: '+str(p['shutdown_request'].get('phase'))
        self.op_status.setText(text)
        if hasattr(self,'job_output'):
            jobs=self.manager.raw.get('jobs',[])[-12:];self.job_output.setPlainText('\n'.join(j['id'][:10]+' • '+j['action']+' • '+j['status']+(' • '+str(j.get('error') or j.get('result',''))[:400]) for j in jobs))
        import sys
        from release_info import VERSION,BUILD
        if getattr(sys,'frozen',False) and not getattr(self,'agent_upgrade_requested',False) and not self.manager.busy and version_key(VERSION,BUILD)>version_key(self.manager.raw.get('version'),self.manager.raw.get('build')):
            try:self.manager.client.call('upgrade',{'exe':sys.executable});self.agent_upgrade_requested=True
            except (OSError,ValueError):pass
        pending=self.manager.state.get('updates',{}).get('pending_exe')
        if pending and pending!=getattr(self,'last_pending',None):
            import sys
            if Path(pending).resolve()!=Path(sys.executable).resolve():self.last_pending=pending;self.staged_exe=pending;QTimer.singleShot(500,lambda:self.guard(self.apply_update))
    def tick(self):
        try:
            super().tick();self.disconnected=False;health=self.manager.runtime.get(self.p['id'],{}).get('health',{})
            if not self.p.get('query_enabled',True) and self.manager.running(self.p):self.server_status.setText('● LOKAL TEST / PROSESS KJØRER')
            if self.p.get('query_enabled',True) and health.get('responding') and self.manager.running(self.p):self.server_status.setText('● STEAM QUERY SVARER');self.metrics[3].setText(str(health.get('players',0)))
            for row,p in enumerate(self.manager.state['servers']):
                if p.get('query_enabled',True) and self.manager.runtime.get(p['id'],{}).get('health',{}).get('responding') and self.manager.running(p):self.all_servers.item(row,1).setText('Query svarer')
        except (OSError,ValueError) as error:
            if not self.disconnected:self.events.put('Ingen kontakt med bakgrunnsagenten: '+str(error));self.disconnected=True
            self.statusBar().showMessage('Agenten er ikke tilgjengelig. DayZ-prosessene stoppes ikke av dette.')
    def run_action(self,action,data=None):
        p=self.p;job=self.manager.enqueue(action,p,data);self.events.put('Jobb lagt i kø: '+action+' • '+job['id'])
        if action in {'backup','restore','clone','maintenance','steam','rollback_mods'}:
            self.rcon_output.setPlainText('Jobben utføres av bakgrunnsagenten. Se jobblisten i Discord / tjeneste. Programvinduet kan lukkes.');return
        def ready(result):self.rcon_output.setPlainText(str(result))
        self.run_task(lambda:self.manager.wait_job(job,timeout=60),ready,description='Serverhandling')
    def rcon_page(self):
        layout=self.page();f,c=card('RCON OG SPILLERE','Velg den aktive BattlEye-konfigurasjonen. RConPassword leses lokalt ved tilkobling og sendes ikke til Discord.')
        row=QHBoxLayout();self.rcon_path=QLineEdit(self.p.get('rcon_config',''));self.rcon_path.setPlaceholderText('profiles/BattlEye/BEServer_x64.cfg');row.addWidget(self.rcon_path,1);row.addWidget(button('Velg fil',self.choose_rcon));row.addWidget(button('Lagre RCon-oppsett',self.action(self.save_rcon)));c.addLayout(row)
        row=QHBoxLayout()
        for title,action in [('Spillere','players'),('Utestengelser','bans'),('Lås','lock'),('Lås opp','unlock')]:row.addWidget(button(title,lambda checked=False,a=action:self.guard(lambda:self.run_action(a))))
        c.addLayout(row);row=QHBoxLayout();self.broadcast=QLineEdit();self.broadcast.setPlaceholderText('Melding til alle spillere');row.addWidget(self.broadcast,1);row.addWidget(button('Send melding',lambda:self.guard(lambda:self.run_action('say',{'message':self.broadcast.text()}))));c.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('Restart med nedtelling',lambda:self.guard(lambda:self.countdown('restart'))));row.addWidget(button('Stopp med nedtelling',lambda:self.guard(lambda:self.countdown('stop'))));row.addWidget(button('Avbryt nedtelling',lambda:self.guard(lambda:self.run_action('cancel_restart'))));row.addWidget(button('Kick / ban',lambda:self.guard(self.player_action)));c.addLayout(row);layout.addWidget(f)
        self.rcon_output=QPlainTextEdit();self.rcon_output.setReadOnly(True);self.rcon_output.setPlaceholderText('Spillerliste, RCon-svar og jobbresultater');layout.addWidget(self.rcon_output,1)
        row=QHBoxLayout();row.addWidget(button('Gjenopprett backup',lambda:self.guard(self.restore_backup)));row.addWidget(button('Tilbakerull Workshop-mods',lambda:self.guard(self.rollback_mods)));row.addWidget(button('Klon til testserver',lambda:self.guard(self.clone_server)));layout.addLayout(row)
    def choose_rcon(self):
        path,_=QFileDialog.getOpenFileName(self,'Velg aktiv BattlEye-konfigurasjon',self.p['root'],'CFG (*.cfg)')
        if path:
            relative=Path(path).resolve().relative_to(Path(self.p['root']).resolve());self.rcon_path.setText(relative.as_posix())
    def save_rcon(self):self.p['rcon_config']=self.rcon_path.text().strip();self.manager.save();self.events.put('RCon-oppsett lagret. Porten må være ulik spill- og query-portene.')
    def countdown(self,action):
        minutes,ok=QInputDialog.getInt(self,'Varslet restart / stopp','Minutter før avslutning:',10,1,1440)
        if ok:self.run_action(action,{'minutes':minutes})
    def player_action(self):
        action,ok=QInputDialog.getItem(self,'Spillerhandling','Handling:',['kick','ban','unban'],0,False)
        if not ok:return
        player,ok=QInputDialog.getInt(self,'Spillerhandling','Spiller-ID fra fersk spillerliste / ban-ID fra utestengelser:',0,0,100000)
        if not ok:return
        data={'ban':player} if action=='unban' else {'player':player}
        if action!='unban':
            reason,ok=QInputDialog.getText(self,'Begrunnelse','Begrunnelse:')
            if not ok:return
            data['reason']=reason
        if action=='ban':
            minutes,ok=QInputDialog.getInt(self,'Utestengelse','Minutter (0 = permanent):',60,0,10000000)
            if not ok:return
            data['minutes']=minutes
        if QMessageBox.question(self,'Bekreft spillerhandling',action+' ID '+str(player)+' på '+self.p['name']+'?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.run_action(action,data)
    def restore_backup(self):
        files=sorted(p.name for p in (self.manager.home/'backups'/self.p['id']).glob('*.zip'))
        if not files:raise ValueError('Ingen backup for denne serveren.')
        archive,ok=QInputDialog.getItem(self,'Gjenopprett backup','Arkiv:',files,0,False)
        if ok and QMessageBox.question(self,'Gjenopprett verden','Gjenopprette '+archive+'? Serveren må være stoppet. Nåværende data sikkerhetskopieres først.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.run_action('restore',{'archive':archive})
    def rollback_mods(self):
        if QMessageBox.question(self,'Tilbakerull mods','Bytte Workshop-mods med forrige installasjon? Lokale mods beholdes. Serveren må være stoppet.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.run_action('rollback_mods')
    def clone_server(self):
        root,ok=QInputDialog.getText(self,'Klon testserver','Ny separat mappe som ikke finnes, for eksempel D:/DayZTest:')
        if ok:self.run_action('clone',{'root':root,'name':self.p['name']+' test'})
    def host_page(self):
        outer=self.page();scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();layout=QVBoxLayout(content);scroll.setWidget(content);outer.addWidget(scroll)
        f,c=card('BAKGRUNNSDRIFT','Agenten fortsetter når vinduet lukkes. Installer Windows-tjenesten for drift etter avlogging og automatisk oppstart med Windows. DayZ-prosessene beholdes ved agentbytte.')
        c.addWidget(button('Installer / oppdater Windows-tjeneste',self.action(self.install_windows_service),'primary'));layout.addWidget(f)
        f,c=card('DISCORD','Egen Discord-bot med slash-kommandoer, kontrollpaneler og driftsvarsler. Token lagres beskyttet på maskinen.')
        form=QFormLayout();self.dc_enabled=QCheckBox('Aktiver Discord-bot');form.addRow('',self.dc_enabled)
        self.dc_guild=QLineEdit();form.addRow('Discord server-ID',self.dc_guild);self.dc_channel=QLineEdit();form.addRow('Driftskanal-ID',self.dc_channel);self.dc_owners=QLineEdit();form.addRow('Eiernes bruker-ID-er (komma)',self.dc_owners)
        self.dc_token=QLineEdit();self.dc_token.setEchoMode(QLineEdit.Password);self.dc_token.setPlaceholderText('Tomt felt beholder eksisterende token');form.addRow('Bot-token',self.dc_token);c.addLayout(form)
        self.dc_roles=QPlainTextEdit();self.dc_roles.setPlaceholderText('{"read":["ROLLE-ID"],"control":[],"moderate":[],"maintenance":[],"config":[]}');self.dc_roles.setMaximumHeight(110);c.addWidget(label('Globale roller per rettighet (JSON). Eier-ID gir full tilgang.','muted'));c.addWidget(self.dc_roles)
        self.dc_server_roles=QPlainTextEdit();self.dc_server_roles.setPlaceholderText('{"SERVER-ID":{"read":["ROLLE-ID"],"control":[]}}');self.dc_server_roles.setMaximumHeight(90);c.addWidget(label('Overstyr roller per DayZ-server-ID (JSON, valgfritt).','muted'));c.addWidget(self.dc_server_roles);c.addWidget(button('Lagre og koble Discord',self.action(self.save_discord),'primary'));layout.addWidget(f)
        self.job_output=QPlainTextEdit();self.job_output.setReadOnly(True);self.job_output.setMaximumHeight(140);layout.addWidget(self.job_output);layout.addStretch()
    def load_host_settings(self):
        settings=self.manager.client.call('discord_settings');self.dc_enabled.setChecked(settings.get('enabled',False));self.dc_guild.setText(str(settings.get('guild_id','')));self.dc_channel.setText(str(settings.get('channel_id','')));self.dc_owners.setText(','.join(map(str,settings.get('owners',[]))));self.dc_roles.setPlainText(json.dumps(settings.get('roles',{'read':[],'control':[],'moderate':[],'maintenance':[],'config':[]}),indent=2));self.dc_server_roles.setPlainText(json.dumps(settings.get('server_roles',{}),indent=2))
    def save_discord(self):
        data=dict(enabled=self.dc_enabled.isChecked(),guild_id=self.dc_guild.text().strip(),channel_id=self.dc_channel.text().strip(),owners=[value.strip() for value in self.dc_owners.text().split(',') if value.strip()],roles=json.loads(self.dc_roles.toPlainText() or '{}'),server_roles=json.loads(self.dc_server_roles.toPlainText() or '{}'))
        if self.dc_token.text():data['token']=self.dc_token.text();self.dc_token.clear()
        self.manager.client.call('discord_settings',data);self.events.put('Discord-oppsett lagret. Tilkoblingsstatus vises i hendelsesstrømmen.')
    def install_windows_service(self):
        from windows_service import install_service
        self.run_task(lambda:install_service(self.manager.home),lambda result:(self.events.put(result),self.manager.refresh()),description='Windows-tjeneste')
    def install_application(self):
        from self_install import install
        self.staged_exe=install(self.manager.home);self.events.put('Programmet er installert. Snarveier er opprettet på skrivebordet og i Start-menyen.');self.apply_update()
    def apply_update(self):
        dirty=bool(self.center.doc and self.center.doc.dirty) or any(layer['doc'].dirty for layer in self.workbench.layers)
        if dirty:
            self.update_message.setText('Oppdateringen er klar. Lagre eller forkast editor-/kartendringer før du installerer.');return
        if self.manager.busy or self.steam.running() or self.tasks:
            self.update_message.setText('Oppdateringen er klar. Venter på aktive jobber …');QTimer.singleShot(1000,lambda:self.guard(self.apply_update));return
        try:super().apply_update()
        except (OSError,ValueError):
            self.update_message.setText('Oppdateringen er klar. Venter på agentbyttet …');QTimer.singleShot(1000,lambda:self.guard(self.apply_update))
    def closeEvent(self,event):
        # Background jobs and DayZ continue; only panel-owned network tasks block close.
        if self.tasks:QMessageBox.information(self,'Paneljobb pågår','Vent til paneljobben er ferdig. Serverdriften skjer i bakgrunnen.');event.ignore();return
        if not getattr(self,'update_handoff',False):
            dirty=bool(self.center.doc and self.center.doc.dirty) or any(layer['doc'].dirty for layer in self.workbench.layers)
            if dirty and QMessageBox.question(self,'Ulagrede endringer','Avslutte og forkaste ulagrede editor-/kartendringer?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:event.ignore();return
        try:self.manager.save()
        except (OSError,ValueError):pass
        event.accept()
