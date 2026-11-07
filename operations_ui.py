"""Local hosting operations: schedules, maintenance, monitoring and recovery."""
from collections import deque
from datetime import datetime
from pathlib import Path
import time
import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox,QLineEdit,QComboBox,QScrollArea,QWidget,QVBoxLayout,QFormLayout,QSpinBox
from desktop import card,label,button
from integration import Task
from update_ui import ReleaseStudio
from server_schedule import next_restart,restart_times
from steam_services import details


class OperationsStudio(ReleaseStudio):
    def __init__(self,home=None):
        self.operations_ready=False
        super().__init__(home)
        self.operations_ready=True; self.op_seen=set(); self.op_checking=set(); self.op_next={}; self.op_crashes={}; self.op_retries={}
        self.op_timer=QTimer(self); self.op_timer.timeout.connect(self.operations_tick); self.op_timer.start(5000)
        for profile in self.manager.state['servers']:
            if not getattr(self.manager,'remote',False) and profile.get('maintenance_state') in ('backup','steam','deploy'):
                self.maintenance_failed(profile,'Previous maintenance was interrupted. Use Run maintenance now to try again.')
        self.load_operations()
    def automation_page(self):
        layout=self.page(); scroll=QScrollArea(); scroll.setWidgetResizable(True); content=QWidget(); inner=QVBoxLayout(content)
        f,c=card('MODS AND SERVER UPDATES','Workshop is checked while the server runs. Updates are installed after a scheduled shutdown or when the server is already stopped. Local development mods are never downloaded from Workshop.')
        self.auto=QCheckBox('Enable automatic Steam updates (Workshop mods)'); c.addWidget(self.auto)
        self.op_game=QCheckBox('Also update DayZ server files during maintenance'); c.addWidget(self.op_game)
        form=QFormLayout(); self.interval=QLineEdit('30'); form.addRow('Check interval, minutes',self.interval);self.mod_restart=QCheckBox('Announce a restart when a Workshop mod has an update');form.addRow('',self.mod_restart);self.mod_grace=QSpinBox();self.mod_grace.setRange(1,1440);self.mod_grace.setValue(15);form.addRow('Delay before mod restart, minutes',self.mod_grace); c.addLayout(form); inner.addWidget(f)
        f,c=card('DZSA LAUNCHER','Automatically check this server after start, scheduled restart and crash recovery. Uses steamQueryPort from serverDZ.cfg. Forward that UDP port in your router; Windows Firewall rules alone do not configure the router.')
        self.dzsa_auto=QCheckBox('Check automatically after every start / restart');c.addWidget(self.dzsa_auto)
        self.dzsa_ip=QLineEdit();self.dzsa_ip.setPlaceholderText('Public IPv4 address, without port');form=QFormLayout();form.addRow('Public server IP',self.dzsa_ip);c.addLayout(form)
        c.addWidget(button('Save DZSA settings',self.action(self.save_dzsa)));c.addWidget(button('Check now',self.action(lambda:self.run_action('dzsa_check'))));c.addWidget(button('Open official servercheck',self.action(self.open_dzsa)))
        self.dzsa_status=label('No check recorded.','muted');c.addWidget(self.dzsa_status);inner.addWidget(f)
        from runtime_tools_ui import RuntimeTools
        self.runtime_tools=RuntimeTools(self);inner.addWidget(self.runtime_tools)
        f,c=card('RESTART SCHEDULE','DayZ uses messages.xml for player warnings, saving and shutdown. Schedule changes apply from the next server start. Times follow the Windows local time zone.')
        self.op_schedule=QCheckBox('Enable scheduled restart'); c.addWidget(self.op_schedule)
        form=QFormLayout(); self.op_mode=QComboBox(); self.op_mode.addItems(['Fixed times','Interval since server start']); form.addRow('Plan',self.op_mode)
        self.op_times=QLineEdit(); self.op_times.setPlaceholderText('00:00, 06:00, 12:00, 18:00'); form.addRow('Times',self.op_times)
        self.op_minutes=QLineEdit('240'); form.addRow('Interval, minutes',self.op_minutes); c.addLayout(form)
        self.op_backup=QCheckBox('Back up before updates / scheduled restarts'); c.addWidget(self.op_backup)
        self.op_keep=QLineEdit('10'); form.addRow('Number of automatic backups to retain',self.op_keep)
        self.op_recover=QCheckBox('Restart after a crash (maximum 3 attempts per 15 minutes)'); c.addWidget(self.op_recover)
        c.addWidget(button('Save operations',self.action(self.save_operations),'primary')); inner.addWidget(f)
        inner.addWidget(button('Run maintenance now (server must be stopped)',self.action(self.manual_maintenance)))
        self.op_status=label('No operations events recorded.','muted'); inner.addWidget(self.op_status)
        inner.addWidget(label('The background agent performs maintenance and restarts without an open application window. Steam may require login or Steam Guard again. If an update fails, the server remains stopped and the error appears in the log. No automatic force-stop or wipe is performed.','muted'))
        inner.addStretch(); scroll.setWidget(content); layout.addWidget(scroll)
    def save_dzsa(self):
        from dzsa_check import validate_settings
        values=dict(dzsa_auto_check=self.dzsa_auto.isChecked(),dzsa_public_ip=self.dzsa_ip.text().strip());validate_settings(values)
        self.p.update(values);self.manager.save();self.events.put('DZSA settings saved.')
    def open_dzsa(self):
        import webbrowser
        from dzsa_check import endpoint
        webbrowser.open('https://dayzsalauncher.com/#/servercheck/'+endpoint(self.p))
    def manual_maintenance(self):
        if self.manager.running(self.p):raise ValueError('The server is running. Wait for the scheduled restart for a safe shutdown.')
        if not self.begin_maintenance(self.p,False):raise ValueError('A job is running. Wait for it to finish.')
    def save_automation(self):self.save_operations()
    def load(self):
        super().load()
        if hasattr(self,'op_schedule'):self.load_operations()
    def load_operations(self):
        p=self.p;self.dzsa_auto.setChecked(p.get('dzsa_auto_check',True));self.dzsa_ip.setText(p.get('dzsa_public_ip',''));self.mod_restart.setChecked(p.get('mod_restart_enabled',False));self.mod_grace.setValue(p.get('mod_grace_minutes',15));self.runtime_tools.load(p); self.op_game.setChecked(p.get('update_game',True)); self.op_schedule.setChecked(p.get('scheduled_restart',False)); self.op_mode.setCurrentIndex(0 if p.get('restart_mode','clock')=='clock' else 1)
        self.op_times.setText(p.get('restart_times','00:00, 06:00, 12:00, 18:00')); self.op_minutes.setText(str(p.get('restart_interval',240))); self.op_backup.setChecked(p.get('maintenance_backup',True)); self.op_keep.setText(str(p.get('backup_keep',10))); self.op_recover.setChecked(p.get('crash_recovery',False))
    def save_operations(self):
        p=self.p
        if p['id'] in self.manager.busy:raise ValueError('Wait for maintenance to finish.')
        candidate=dict(p,auto_update=self.auto.isChecked(),update_minutes=int(self.interval.text()),update_game=self.op_game.isChecked(),scheduled_restart=self.op_schedule.isChecked(),restart_mode='clock' if self.op_mode.currentIndex()==0 else 'interval',restart_times=self.op_times.text().strip(),restart_interval=int(self.op_minutes.text()),maintenance_backup=self.op_backup.isChecked(),backup_keep=int(self.op_keep.text()),crash_recovery=self.op_recover.isChecked(),mod_restart_enabled=self.mod_restart.isChecked(),mod_grace_minutes=self.mod_grace.value())
        candidate.update(self.runtime_tools.values())
        from runtime_tools import validate_runtime
        validate_runtime(candidate)
        if not 5<=candidate['update_minutes']<=10080:raise ValueError('Update check interval must be 5–10080 minutes.')
        if not 1<=candidate['backup_keep']<=100:raise ValueError('Retain 1–100 automatic backups.')
        restart_times(candidate['restart_times']); next_restart(candidate)
        p.update(candidate); self.manager.save(); self.events.put('Operations settings saved. The restart schedule applies from the next server start.'); self.op_next.pop(p['id'],None)
    def background(self,fn,done,failed):
        task=Task(fn,self); self.tasks.add(task)
        task.done.connect(lambda value:self.guard(lambda:done(value))); task.failed.connect(failed); task.finished.connect(lambda:self.tasks.discard(task)); task.finished.connect(task.deleteLater); task.start()
    def check_mods_automatic(self,p):
        ids=[m['id'] for m in p['mods'] if m.get('source')!='local' and m.get('enabled',True) and m.get('id')]
        if not ids:return
        key=p['id']; self.op_checking.add(key)
        def done(items):
            self.op_checking.discard(key); newer=[]
            for item in items:
                for m in p['mods']:
                    if m.get('id')==item['id']:
                        m['remote_updated']=item['updated']
                        if not m.get('installed_updated') or item['updated']>m['installed_updated']:newer.append(item['title'])
            if newer:
                p['mods_pending']=True
                self.events.put(p['name']+': update is waiting for maintenance: '+', '.join(newer))
            self.manager.save()
        def failed(msg):self.op_checking.discard(key); self.events.put(p['name']+': automatic Workshop check failed: '+msg)
        self.background(lambda:details(ids),done,failed)
    def maintenance_failed(self,p,msg):
        p['maintenance_state']='failed'; p['maintenance_error']=str(msg); self.manager.busy.discard(p['id']); self.manager.save(); self.events.put(p['name']+': MAINTENANCE STOPPED: '+str(msg))
    def begin_maintenance(self,p,restart):
        if self.steam.running() or p['id'] in self.manager.busy or self.manager.running(p):return False
        p.pop('_deployment_ok',None)
        p['maintenance_state']='backup'; p['maintenance_restart']=restart; self.manager.busy.add(p['id']); self.manager.save()
        def work():
            if p.get('maintenance_backup',True):
                self.manager.backup(p)
                # Only automatic backups recorded by this operation are rotated.
                files=sorted((self.manager.home/'backups'/p['id']).glob('*.zip'),key=lambda f:f.stat().st_mtime)
                if files:
                    auto=p.setdefault('automatic_backups',[]); auto.append(str(files[-1])); keep=int(p.get('backup_keep',10))
                    while len(auto)>keep:
                        old=Path(auto.pop(0))
                        if old.parent.resolve()==(self.manager.home/'backups'/p['id']).resolve():old.unlink(missing_ok=True)
            return True
        def ready(_):
            self.manager.busy.discard(p['id'])
            kind='all' if p.get('update_game',True) else 'mods'
            hasmods=any(m.get('id') and m.get('enabled',True) and m.get('source')!='local' for m in p['mods'])
            if p.get('auto_update') and (hasmods or kind=='all'):
                p['maintenance_state']='steam'; self.manager.save()
                try:self.steam.start(p,kind)
                except Exception as e:self.maintenance_failed(p,str(e))
            else:self.maintenance_ready(p)
        self.background(work,ready,lambda msg:self.maintenance_failed(p,msg)); return True
    def maintenance_ready(self,p):
        restart=p.pop('maintenance_restart',False); p['maintenance_state']='idle'; p.pop('maintenance_error',None); p['mods_pending']=False; self.manager.save()
        if restart:
            try:self.manager.start(p)
            except Exception as e:self.maintenance_failed(p,str(e))
    def steam_done(self,data):
        p=data['profile']
        if p.get('maintenance_state')=='steam' and not data['ok']:self.maintenance_failed(p,data['message'])
        super().steam_done(data)
        # Deployment runs in the base class worker. The tick waits for its busy flag to clear.
        if p.get('maintenance_state')=='steam' and data['ok']:p['maintenance_state']='deploy'; self.manager.save()
    def operations_tick(self):
        if not self.operations_ready or getattr(self,'update_handoff',False):return
        now=time.time()
        for p in self.manager.state['servers']:
            key=p['id']; record=self.manager.launches.get(key); running=self.manager.running(p)
            if running or not p.get('crash_recovery'):self.op_retries.pop(key,None)
            if record and record['state']=='exited':
                token=(key,record['started_wall'])
                if token not in self.op_seen:
                    self.op_seen.add(token); due=record.get('restart_due')
                    planned=due and abs(now-due)<300 and record.get('exit_code')==0 and not record.get('expected_stop')
                    if planned:
                        p['maintenance_state']='queued'; p['maintenance_restart']=True; self.manager.save()
                    elif p.get('crash_recovery') and not record.get('expected_stop'):
                        history=self.op_crashes.setdefault(key,deque());
                        while history and now-history[0]>900:history.popleft()
                        if len(history)<3:history.append(now); self.op_retries[key]=now+30; self.events.put(p['name']+': crash recovery in 30 seconds.')
                        else:self.events.put(p['name']+': crash recovery stopped after 3 attempts in 15 minutes.')
            if p.get('maintenance_state')=='queued' and not running:self.begin_maintenance(p,True)
            if p.get('maintenance_state')=='deploy' and key not in self.manager.busy:
                # The deployment worker marks success explicitly; a partial deployment must never restart.
                if p.pop('_deployment_ok',False):self.maintenance_ready(p)
                else:self.maintenance_failed(p,'Mod deployment was not confirmed. Check the logs and Workshop folder.')
            if key in self.op_retries and now>=self.op_retries[key] and not running and key not in self.manager.busy and p.get('maintenance_state','idle')=='idle':
                del self.op_retries[key]
                try:self.manager.start(p)
                except Exception as e:self.events.put(p['name']+': restart failed: '+str(e))
            if p.get('auto_update') and key not in self.op_checking and key not in self.manager.busy and now>=self.op_next.get(key,0):
                self.op_next[key]=now+max(5,int(p['update_minutes']))*60
                if running:self.check_mods_automatic(p)
                elif p.get('maintenance_state','idle')=='idle' and not self.steam.running():self.begin_maintenance(p,False)
        p=self.p; r=self.manager.launches.get(p['id']); parts=[]
        if r and self.manager.running(p):
            parts.append('PID '+str(r['pid'])+' • uptime '+str(int((now-r['started_wall'])/60))+' min')
            try:
                proc=psutil.Process(r['pid']); parts.append('RAM '+str(round(proc.memory_info().rss/1024**2))+' MB')
            except psutil.Error:pass
            if r.get('restart_due'):parts.append('Next restart approximately '+datetime.fromtimestamp(r['restart_due']).strftime('%d.%m %H:%M'))
        parts.append('Maintenance: '+p.get('maintenance_state','idle'))
        if p.get('mods_pending'):parts.append('Mod updates pending')
        if p.get('maintenance_error'):parts.append(p['maintenance_error'])
        self.op_status.setText('\n'.join(parts))
