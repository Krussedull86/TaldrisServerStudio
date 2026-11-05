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
        self.page_names+=['RCon & players','Discord & service'];self.rcon_page();self.host_page()
        side=self.nav[0].parentWidget().layout()
        for index,title in [(11,'RCon & players'),(12,'Discord / service')]:
            b=button(title,lambda checked=False,n=index:self.go(n),'nav');b.setCheckable(True);side.insertWidget(side.count()-4,b);self.nav.append(b)
        self.setStyleSheet('QPushButton#nav {padding-top:7px;padding-bottom:7px;}');self.load_host_settings()
        self.stack.widget(10).layout().insertWidget(0,button('Install this application',lambda:self.guard(self.install_application),'primary'))
        for page in (7,8):self.stack.widget(page).layout().insertWidget(0,button('Import existing server from BAT / CMD …',lambda:self.guard(self.import_batch_file),'primary'))
        self.agent_version_label=label('Panel / agent …','muted');self.statusBar().addPermanentWidget(self.agent_version_label)
        self.stack.widget(10).layout().insertWidget(1,button('Update / repair background agent',lambda:self.guard(self.repair_background_agent)))
        self.server_controls.addWidget(button('Delete server …',lambda:self.guard(self.delete_server_profile),'danger'))
        self.statusBar().showMessage('Connected to background agent • Servers run independently of this window')
        from loot_workspace import LootWorkspace
        self.page_names.append('DZSA Loot Editor');layout=self.page();self.loot=LootWorkspace(self);layout.addWidget(self.loot);b=button('DZSA Loot Editor',lambda:self.go(13),'nav');b.setCheckable(True);side.insertWidget(side.count()-4,b);self.nav.append(b)
        transfer=QHBoxLayout();transfer.addWidget(button('Export profile …',lambda:self.guard(self.export_server_profile)));transfer.addWidget(button('Import profile …',lambda:self.guard(self.import_server_profile)));self.stack.widget(7).layout().insertLayout(0,transfer)
        self.stack.widget(0).layout().addWidget(button('Fix dependencies …',lambda:self.guard(self.fix_dependencies)))
        self.stage_label=label('Stage: Idle','eyebrow');self.terminal_detail.parentWidget().layout().insertWidget(0,self.stage_label)
        from PySide6.QtWidgets import QTabBar
        self.server_tabs=QTabBar();self.server_tabs.setExpanding(False);self.server_tabs.setUsesScrollButtons(True);self.server_tabs.setDocumentMode(True);self.server_tabs.setMinimumHeight(38)
        self.centralWidget().layout().itemAt(1).layout().insertWidget(1,self.server_tabs)
        self.file_context=label('File editor • backups are created before every saved edit','eyebrow');self.stack.widget(4).layout().insertWidget(0,self.file_context)
        self.server_tabs.currentChanged.connect(lambda index:self.selector.setCurrentIndex(index) if index>=0 else None)
        self.sync_server_tabs()
        from analytics_ui import PerformancePage,AnalyticsPage
        self.performance_page=PerformancePage(self);self.analytics_page=AnalyticsPage(self)
        for title,widget in [('Performance',self.performance_page),('Live analytics',self.analytics_page)]:
            index=self.stack.addWidget(widget);self.page_names.append(title);b=button(title,lambda checked=False,n=index:self.go(n),'nav');b.setCheckable(True);side.insertWidget(side.count()-4,b);self.nav.append(b)
        from community_ui import CommunityControls
        self.community=CommunityControls(self)

    def sync_server_tabs(self):
        self.server_tabs.blockSignals(True)
        profiles=self.manager.state['servers'];keys=[self.server_tabs.tabData(i) for i in range(self.server_tabs.count())]
        if keys!=[p['id'] for p in profiles]:
            while self.server_tabs.count():self.server_tabs.removeTab(0)
            for p in profiles:
                index=self.server_tabs.addTab(p['name']);self.server_tabs.setTabData(index,p['id'])
        for i,p in enumerate(profiles):
            self.server_tabs.setTabText(i,p['name']);self.server_tabs.setTabToolTip(i,p.get('root','') or 'Choose a server folder')
            if p['id']==self.p['id']:self.server_tabs.setCurrentIndex(i)
        self.server_tabs.blockSignals(False)
    def repair_background_agent(self):
        if getattr(self,'repair_in_progress',False):return
        from agent_repair import repair
        def done(message):self.manager.refresh();self.agent_upgrade_requested=False;self.events.put(message);self.update_message.setText(message)
        self.repair_in_progress=True;before=set(self.tasks)
        self.run_task(lambda:repair(self.manager.home,self.manager.client),done,description='Background agent')
        for task in self.tasks-before:task.finished.connect(lambda:setattr(self,'repair_in_progress',False))
    def delete_server_profile(self):
        self.manager.refresh();p=self.p
        if self.manager.running(p) or p['id'] in self.manager.busy:raise ValueError('Stop the server and wait for jobs to finish before deleting.')
        text='Remove server profile “'+p['name']+'” from the application?\n\nServer folder: '+(p['root'] or '(not selected)')+'\nServer files, mods, backups and world data are preserved. Unsaved editor/map changes for this profile are discarded. If this is the last profile, an empty profile is created.'
        if QMessageBox.question(self,'Delete server profile',text,QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        next_profile=self.manager.remove_profile(p);identity=p['id'];self.config_cache.pop(identity,None);self.deadlines.pop(identity,None)
        if self.center_server==identity:self.center.doc=None;self.center_server=None
        if hasattr(self.workbench,'cache'):self.workbench.cache.pop(identity,None)
        if self.workbench.server_id==identity:self.workbench.layers=[];self.workbench.server_id=None
        self.p=next_profile;self.load();self.go(0);self.events.put('Server profile deleted. Server files and world data are preserved.')
    def import_batch_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Import existing server','','Launch script (*.bat *.cmd)')
        if not path:return
        from batch_import_ui import BatchImportDialog
        dialog=BatchImportDialog(self,path)
        if dialog.exec() and dialog.result_profile:
            identity=dialog.result_profile['id'];self.config_cache.pop(identity,None)
            if self.center_server==identity:self.center.doc=None;self.center_server=None
            if hasattr(self.workbench,'cache'):self.workbench.cache.pop(identity,None)
            if self.workbench.server_id==identity:self.workbench.layers=[];self.workbench.server_id=None
            self.p=dialog.result_profile;self.load();self.go(7);self.events.put('Existing server profile imported from BAT. No server files were changed.')
    def check_import_target(self,identity):
        if not identity:return
        self.center.sync();docs=[self.config_cache.get(identity)]
        if self.center_server==identity:docs.append(self.center.doc)
        layers=self.workbench.layers if self.workbench.server_id==identity else getattr(self.workbench,'cache',{}).get(identity,[])
        if any(doc and doc.dirty for doc in docs) or any(layer['doc'].dirty for layer in layers):raise ValueError('Save or discard map and configuration changes for this profile before importing.')
    def load(self):
        super().load()
        if hasattr(self,'loot'):self.loot.update_target()
        if hasattr(self,'server_tabs'):self.sync_server_tabs()
        if hasattr(self,'file_context'):self.file_context.setText('File editor • '+self.p['name']+' • every save keeps a backup')
        if hasattr(self,'performance_page'):self.performance_page.load()
        if hasattr(self,'analytics_page'):self.analytics_page.load()
        if hasattr(self,'rcon_path'):self.rcon_path.setText(self.p.get('rcon_config',''))
    def overview(self):
        super().overview()
        hero_layout=self.start_btn.parentWidget().layout();actions=hero_layout.itemAt(hero_layout.count()-1).layout()
        actions.insertWidget(2,button('Restart …',lambda:self.guard(lambda:self.countdown('restart'))));actions.insertWidget(3,button('Graceful stop …',lambda:self.guard(lambda:self.countdown('stop'))))
        from PySide6.QtWidgets import QLabel
        for widget in self.stack.widget(0).findChildren(QLabel):
            if widget.text()=='Live data not connected':widget.setText('Last Steam query response')
    def backups_page(self):
        super().backups_page();page=self.stack.widget(5);page.layout().addWidget(button('Restore selected backup …',lambda:self.guard(self.restore_backup),'primary'))
        from PySide6.QtWidgets import QLabel
        for widget in page.findChildren(QLabel):
            if 'Restore is performed manually' in widget.text():widget.setText('Includes configuration, profiles, mpmissions and battleye. Restoring requires a stopped server and first creates a new backup. Archives may contain passwords and player data.')
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
        if path.exists():self.events.put('Keeping existing server config: '+str(path));return
        self.manager.wait_job(self.manager.enqueue('create_config',p))
    def bootstrap(self,after=None):
        self.save_setup();p=self.p;self.setup_status.setText('The agent is downloading SteamCMD from Valve …');job=self.manager.enqueue('bootstrap',p)
        def ready(exe):
            self.manager.refresh();self.setup_status.setText('SteamCMD is ready.')
            if after:after(p)
        self.run_task(lambda:self.manager.wait_job(job,timeout=90),ready,description='SteamCMD download')
    def steam_done(self,data):
        if hasattr(self,'stage_label'):self.stage_label.setText('Stage: '+('Done' if data['ok'] else 'Failed / cancelled'))
        self.events.put(data['message']);self.console_status.setText(data['message']);self.setup_status.setText(data['message']);self.terminal_detail.setText(data['message']);self.manager.refresh();self.refresh_mods()
        if data['ok'] and data['chained'] and data['profile'].get('start_after_install'):self.manager.start(data['profile'])
    def begin_maintenance(self,p,restart):
        self.manager.enqueue('maintenance',p,{'restart':restart});return True
    def maintenance_failed(self,p,msg):self.events.put(p['name']+': '+str(msg))
    def check_mods_automatic(self,p):return
    def operations_tick(self):
        if not getattr(self,'operations_ready',False):return
        p=self.p;runtime=self.manager.runtime.get(p['id'],{});record=runtime.get('launch',{})
        from release_info import VERSION,BUILD
        text=f"Panel {VERSION} / build {BUILD} • Agent {self.manager.raw.get('version', '?')} / build {self.manager.raw.get('build', '?')}\n"+'Background agent: '+('Windows service' if self.manager.raw.get('service') else 'standalone process (install the service to run after logout)')+'\n'+p['name']+' • '+('Process running' if runtime.get('running') else 'Stopped')+' • RAM '+str(runtime.get('ram_mb','—'))+' MB • CPU '+str(runtime.get('cpu_percent','—'))+' % • Free disk '+str(runtime.get('disk_free_gb','—'))+' GB\nMaintenance: '+p.get('maintenance_state','idle')
        self.runtime_tools.update_status(runtime.get('programs',[]))
        if p.get('mods_pending'):text+='\nMod update pending: '+', '.join(p.get('mods_pending_titles',[]))
        if p.get('mod_restart_note'):text+='\n'+p['mod_restart_note']
        health=runtime.get('health',{})
        if health.get('responding'):text+='\nSteam query responding • '+str(health.get('players',0))+'/'+str(health.get('max_players','?'))+' players • '+health.get('map','')
        elif not p.get('query_enabled',True):text+='\nLocal test • query check disabled • direct connection 127.0.0.1:'+str(p['port'])
        elif runtime.get('running'):text+='\nSteam query has not responded yet / no response available.'
        if record.get('restart_due'):text+='\nNext restart: '+time.strftime('%d.%m %H:%M',time.localtime(record['restart_due']))
        if p.get('shutdown_request'):text+='\nManual countdown: '+str(p['shutdown_request'].get('phase'))
        self.op_status.setText(text)
        if hasattr(self,'job_output'):
            jobs=self.manager.raw.get('jobs',[])[-12:];self.job_output.setPlainText('\n'.join(j['id'][:10]+' • '+j['action']+' • '+j['status']+(' • '+str(j.get('error') or j.get('result',''))[:400]) for j in jobs))
        import sys
        from release_info import VERSION,BUILD
        if getattr(sys,'frozen',False) and not getattr(self,'agent_upgrade_requested',False) and not self.manager.busy and version_key(VERSION,BUILD)>version_key(self.manager.raw.get('version'),self.manager.raw.get('build')):
            try:self.manager.client.call('upgrade',{'exe':sys.executable});self.agent_upgrade_requested=True;self.agent_upgrade_time=time.monotonic()
            except (OSError,ValueError):pass
        if getattr(sys,'frozen',False) and getattr(self,'agent_upgrade_requested',False) and not self.manager.raw.get('service') and time.monotonic()-getattr(self,'agent_upgrade_time',time.monotonic())>30 and version_key(VERSION,BUILD)>version_key(self.manager.raw.get('version'),self.manager.raw.get('build')) and not self.manager.busy and not self.tasks:self.repair_background_agent()
        pending=self.manager.state.get('updates',{}).get('pending_exe')
        if pending and pending!=getattr(self,'last_pending',None):
            import sys
            if Path(pending).resolve()!=Path(sys.executable).resolve():self.last_pending=pending;self.staged_exe=pending;QTimer.singleShot(500,lambda:self.guard(self.apply_update))
    def tick(self):
        try:
            super().tick();self.disconnected=False;
            from release_info import VERSION,BUILD
            if hasattr(self,'agent_version_label'):self.agent_version_label.setText(f'Panel {VERSION} b{BUILD} • Agent {self.manager.raw.get("version","?")} b{self.manager.raw.get("build","?")}')
            health=self.manager.runtime.get(self.p['id'],{}).get('health',{})
            if not self.p.get('query_enabled',True) and self.manager.running(self.p):self.server_status.setText('● LOCAL TEST / PROCESS RUNNING')
            if self.p.get('query_enabled',True) and health.get('responding') and self.manager.running(self.p):self.server_status.setText('● STEAM QUERY RESPONDING');self.metrics[3].setText(str(health.get('players',0)))
            for row,p in enumerate(self.manager.state['servers']):
                if p.get('query_enabled',True) and self.manager.runtime.get(p['id'],{}).get('health',{}).get('responding') and self.manager.running(p):self.all_servers.item(row,1).setText('Query svarer')
        except (OSError,ValueError) as error:
            if not self.disconnected:self.events.put('No connection to the background agent: '+str(error));self.disconnected=True
            self.statusBar().showMessage('The agent is unavailable. This does not stop DayZ processes.')
    def run_action(self,action,data=None):
        p=self.p;job=self.manager.enqueue(action,p,data);self.events.put('Job queued: '+action+' • '+job['id'])
        if action in {'backup','restore','clone','maintenance','steam','rollback_mods'}:
            self.rcon_output.setPlainText('The background agent runs this job. See the job list under Discord / service. You can close the application window.');return
        def ready(result):self.rcon_output.setPlainText(str(result))
        self.run_task(lambda:self.manager.wait_job(job,timeout=60),ready,description='Server action')
    def rcon_page(self):
        layout=self.page();f,c=card('RCON AND PLAYERS','Choose the active BattlEye configuration. RConPassword is read locally when connecting and is not sent to Discord.')
        row=QHBoxLayout();self.rcon_path=QLineEdit(self.p.get('rcon_config',''));self.rcon_path.setPlaceholderText('profiles/BattlEye/BEServer_x64.cfg');row.addWidget(self.rcon_path,1);row.addWidget(button('Choose file',self.choose_rcon));row.addWidget(button('Save RCon settings',self.action(self.save_rcon)));c.addLayout(row)
        row=QHBoxLayout()
        for title,action in [('Players','players'),('Bans','bans'),('Lock','lock'),('Unlock','unlock')]:row.addWidget(button(title,lambda checked=False,a=action:self.guard(lambda:self.run_action(a))))
        c.addLayout(row);row=QHBoxLayout();self.broadcast=QLineEdit();self.broadcast.setPlaceholderText('Message to all players');row.addWidget(self.broadcast,1);row.addWidget(button('Send message',lambda:self.guard(lambda:self.run_action('say',{'message':self.broadcast.text()}))));c.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('Restart with countdown',lambda:self.guard(lambda:self.countdown('restart'))));row.addWidget(button('Stop with countdown',lambda:self.guard(lambda:self.countdown('stop'))));row.addWidget(button('Cancel countdown',lambda:self.guard(lambda:self.run_action('cancel_restart'))));row.addWidget(button('Kick / ban',lambda:self.guard(self.player_action)));c.addLayout(row);layout.addWidget(f)
        self.rcon_output=QPlainTextEdit();self.rcon_output.setReadOnly(True);self.rcon_output.setPlaceholderText('Player list, RCon responses and job results');layout.addWidget(self.rcon_output,1)
        row=QHBoxLayout();row.addWidget(button('Restore backup',lambda:self.guard(self.restore_backup)));row.addWidget(button('Roll back Workshop mods',lambda:self.guard(self.rollback_mods)));row.addWidget(button('Clone to test server',lambda:self.guard(self.clone_server)));layout.addLayout(row)
    def choose_rcon(self):
        path,_=QFileDialog.getOpenFileName(self,'Choose active BattlEye configuration',self.p['root'],'CFG (*.cfg)')
        if path:
            relative=Path(path).resolve().relative_to(Path(self.p['root']).resolve());self.rcon_path.setText(relative.as_posix())
    def save_rcon(self):self.p['rcon_config']=self.rcon_path.text().strip();self.manager.save();self.events.put('RCon settings saved. The port must differ from the game and query ports.')
    def countdown(self,action):
        minutes,ok=QInputDialog.getInt(self,'Announced restart / stop','Minutes before shutdown:',10,1,1440)
        if ok:self.run_action(action,{'minutes':minutes})
    def player_action(self):
        action,ok=QInputDialog.getItem(self,'Player action','Action:',['kick','ban','unban'],0,False)
        if not ok:return
        player,ok=QInputDialog.getInt(self,'Player action','Player ID from the current player list / ban ID from the ban list:',0,0,100000)
        if not ok:return
        data={'ban':player} if action=='unban' else {'player':player}
        if action!='unban':
            reason,ok=QInputDialog.getText(self,'Reason','Reason:')
            if not ok:return
            data['reason']=reason
        if action=='ban':
            minutes,ok=QInputDialog.getInt(self,'Ban','Minutes (0 = permanent):',60,0,10000000)
            if not ok:return
            data['minutes']=minutes
        if QMessageBox.question(self,'Confirm player action',action+' ID '+str(player)+' on '+self.p['name']+'?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.run_action(action,data)
    def restore_backup(self):
        files=sorted(p.name for p in (self.manager.home/'backups'/self.p['id']).glob('*.zip'))
        if not files:raise ValueError('No backups for this server.')
        archive,ok=QInputDialog.getItem(self,'Restore backup','Archive:',files,0,False)
        if ok and QMessageBox.question(self,'Restore world','Restore '+archive+'? The server must be stopped. Current data will be backed up first.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.run_action('restore',{'archive':archive})
    def rollback_mods(self):
        if QMessageBox.question(self,'Roll back mods','Replace Workshop mods with the previous installation? Local mods are preserved. The server must be stopped.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.run_action('rollback_mods')
    def clone_server(self):
        root,ok=QInputDialog.getText(self,'Clone test server','New separate folder that does not exist, for example D:/DayZTest:')
        if ok:self.run_action('clone',{'root':root,'name':self.p['name']+' test'})
    def host_page(self):
        outer=self.page();scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();layout=QVBoxLayout(content);scroll.setWidget(content);outer.addWidget(scroll)
        f,c=card('BACKGROUND OPERATIONS','The agent keeps running when this window closes. Install the Windows service to keep it running after logout and start it automatically with Windows. DayZ processes are preserved during agent upgrades.')
        c.addWidget(button('Install / update Windows service',self.action(self.install_windows_service),'primary'));layout.addWidget(f)
        f,c=card('DISCORD','Dedicated Discord bot with slash commands, control panels and operations alerts. The token is stored securely on this machine.')
        form=QFormLayout();self.dc_enabled=QCheckBox('Enable Discord bot');form.addRow('',self.dc_enabled)
        self.dc_guild=QLineEdit();form.addRow('Discord server ID',self.dc_guild);self.dc_channel=QLineEdit();form.addRow('Operations channel ID',self.dc_channel);self.dc_owners=QLineEdit();form.addRow('Owner user IDs (comma-separated)',self.dc_owners)
        self.dc_token=QLineEdit();self.dc_token.setEchoMode(QLineEdit.Password);self.dc_token.setPlaceholderText('Leave empty to keep the existing token');form.addRow('Bot token',self.dc_token);c.addLayout(form)
        self.dc_roles=QPlainTextEdit();self.dc_roles.setPlaceholderText('{"read":["ROLE-ID"],"control":[],"moderate":[],"maintenance":[],"config":[]}');self.dc_roles.setMaximumHeight(110);c.addWidget(label('Global roles per permission (JSON). Owner IDs have full access.','muted'));c.addWidget(self.dc_roles)
        self.dc_server_roles=QPlainTextEdit();self.dc_server_roles.setPlaceholderText('{"SERVER-ID":{"read":["ROLE-ID"],"control":[]}}');self.dc_server_roles.setMaximumHeight(90);c.addWidget(label('Override roles per DayZ server ID (JSON, optional).','muted'));c.addWidget(self.dc_server_roles);c.addWidget(button('Save and connect Discord',self.action(self.save_discord),'primary'));layout.addWidget(f)
        self.job_output=QPlainTextEdit();self.job_output.setReadOnly(True);self.job_output.setMaximumHeight(140);layout.addWidget(self.job_output);layout.addStretch()
    def load_host_settings(self):
        settings=self.manager.client.call('discord_settings');self.dc_enabled.setChecked(settings.get('enabled',False));self.dc_guild.setText(str(settings.get('guild_id','')));self.dc_channel.setText(str(settings.get('channel_id','')));self.dc_owners.setText(','.join(map(str,settings.get('owners',[]))));self.dc_roles.setPlainText(json.dumps(settings.get('roles',{'read':[],'control':[],'moderate':[],'maintenance':[],'config':[]}),indent=2));self.dc_server_roles.setPlainText(json.dumps(settings.get('server_roles',{}),indent=2))
    def save_discord(self):
        data=dict(enabled=self.dc_enabled.isChecked(),guild_id=self.dc_guild.text().strip(),channel_id=self.dc_channel.text().strip(),owners=[value.strip() for value in self.dc_owners.text().split(',') if value.strip()],roles=json.loads(self.dc_roles.toPlainText() or '{}'),server_roles=json.loads(self.dc_server_roles.toPlainText() or '{}'))
        if self.dc_token.text():data['token']=self.dc_token.text();self.dc_token.clear()
        self.manager.client.call('discord_settings',data);self.events.put('Discord settings saved. Connection status appears in the event stream.')
    def install_windows_service(self):
        from windows_service import install_service
        self.run_task(lambda:install_service(self.manager.home),lambda result:(self.events.put(result),self.manager.refresh()),description='Windows service')
    def install_application(self):
        from self_install import install
        self.staged_exe=install(self.manager.home);self.events.put('The application is installed. Shortcuts have been created on the desktop and in the Start menu.');self.apply_update()
    def apply_update(self):
        dirty=bool(self.center.doc and self.center.doc.dirty) or any(layer['doc'].dirty for layer in self.workbench.layers) or (hasattr(self,'loot') and self.loot.dirty)
        if dirty:
            self.update_message.setText('The update is ready. Save or discard editor/map changes before installing.');return
        if self.manager.busy or self.steam.running() or self.tasks:
            self.update_message.setText('The update is ready. Waiting for active jobs …');QTimer.singleShot(1000,lambda:self.guard(self.apply_update));return
        try:super().apply_update()
        except (OSError,ValueError):
            self.update_message.setText('The update is ready. Waiting for the agent upgrade …');QTimer.singleShot(1000,lambda:self.guard(self.apply_update))
    def closeEvent(self,event):
        # Background jobs and DayZ continue; only panel-owned network tasks block close.
        if self.tasks:QMessageBox.information(self,'Panel job in progress','Wait for the panel job to finish. Server operations continue in the background.');event.ignore();return
        if not getattr(self,'update_handoff',False):
            dirty=bool(self.center.doc and self.center.doc.dirty) or any(layer['doc'].dirty for layer in self.workbench.layers) or (hasattr(self,'loot') and self.loot.dirty)
            if dirty and QMessageBox.question(self,'Unsaved changes','Exit and discard unsaved editor/map changes?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:event.ignore();return
        try:self.manager.save()
        except (OSError,ValueError):pass
        event.accept()

    def terminal_output(self,text):
        super().terminal_output(text)
        if hasattr(self,'stage_label'):
            from steam_status import phase
            self.stage_label.setText('Stage: '+phase(text))
    def export_server_profile(self):
        from profile_transfer import export_profile
        path,_=QFileDialog.getSaveFileName(self,'Export server profile',self.p['name']+'.cruz.json','Server profile (*.cruz.json *.taldris.json *.json)')
        if path:export_profile(self.p,path);self.events.put('Profile exported without credentials. Companion program commands are excluded.')
    def import_server_profile(self):
        from profile_transfer import read_profile
        path,_=QFileDialog.getOpenFileName(self,'Import server profile','','Server profile (*.json)')
        if not path:return
        fields=read_profile(path)
        if QMessageBox.question(self,'Import server profile','Create a new profile named '+fields['name']+'?\nReview file paths and ports before starting. No server files will be changed.',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        result=self.manager.client.call('import_profile',{'profile':fields});self.manager.refresh();self.p=next(p for p in self.manager.state['servers'] if p['id']==result['id']);self.load();self.go(7)
    def fix_dependencies(self):
        from dependencies import check_dependencies
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        rows=check_dependencies(self.p.get('root',''));box=QMessageBox(self);box.setWindowTitle('DayZ runtime dependencies');box.setText('\n'.join(('✓ ' if ok else '✕ ')+title+': '+detail for ok,title,detail,url in rows));dx=box.addButton('Microsoft DirectX',QMessageBox.ActionRole);vc=box.addButton('Microsoft Visual C++ x64',QMessageBox.ActionRole);box.addButton(QMessageBox.Close);box.exec()
        if box.clickedButton() is dx:QDesktopServices.openUrl(QUrl(rows[0][3]))
        elif box.clickedButton() is vc:QDesktopServices.openUrl(QUrl(rows[1][3]))
