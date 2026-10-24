from pathlib import Path
from PySide6.QtCore import QTimer,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLineEdit,QComboBox,QCheckBox,QHBoxLayout,QPlainTextEdit
from desktop import label,button,card
from integration import IntegratedStudio,Task
from release_info import VERSION,BUILD,REPOSITORY
from program_updates import check,download,repository,stage_install
from panel_handoff import launch_handoff
from process_registry import save_processes
from network_tls import network_message

class ReleaseStudio(IntegratedStudio):
    def __init__(self,home=None):
        super().__init__(home); self.setWindowTitle(f'Taldris Server Studio • {VERSION} / bygg {BUILD}'); self.latest_update=None; self.update_running=False; self.update_handoff=False; self.staged_exe=None
        self.update_settings=self.manager.state.setdefault('updates',dict(repository=REPOSITORY,channel='stable',auto_check=True))
        if not self.update_settings.get('repository') and REPOSITORY:self.update_settings['repository']=REPOSITORY
        self.page_names.append('Programoppdatering'); l=self.page(); f,c=card('DEV / STABLE',f'Installert: {VERSION} • bygg {BUILD}. Oppdatering av kontrollpanelet holdes adskilt fra DayZ og mods.')
        self.update_repo=QLineEdit(self.update_settings.get('repository','')); self.update_repo.setPlaceholderText('GitHub-repo: eier/navn — ikke koblet til ennå'); c.addWidget(self.update_repo)
        self.update_channel=QComboBox(); self.update_channel.addItems(['stable','dev']); self.update_channel.setCurrentText(self.update_settings.get('channel','stable')); c.addWidget(self.update_channel)
        self.update_auto=QCheckBox('Sjekk automatisk ved programstart'); self.update_auto.setChecked(self.update_settings.get('auto_check',True)); c.addWidget(self.update_auto)
        row=QHBoxLayout(); row.addWidget(button('Lagre og sjekk',self.action(self.save_and_check),'primary')); self.update_download=button('Installer programoppdatering',self.action(lambda:self.download_update(True))); self.update_download.setEnabled(False); row.addWidget(self.update_download); row.addWidget(button('Åpne nedlastingsmappe',self.open_update_folder)); c.addLayout(row); l.addWidget(f)
        self.update_message=label('Ikke koblet til GitHub ennå.' if not self.update_repo.text() else 'Klar til å sjekke valgt kanal.','eyebrow'); l.addWidget(self.update_message)
        note=label('Dev får nye testutgaver etter push. Stable publiseres bare manuelt fra en bestemt testet dev-utgave. Nedlastingen kontrolleres med SHA-256. Ved manuell sjekk installeres en nyere utgave automatisk. Kontrollpanelet starter på nytt og kobler til samme DayZ-prosess; serveren fortsetter. SteamCMD og backup må være ferdig før panelbyttet.','muted'); l.addWidget(note); l.addStretch()
        side=self.nav[0].parentWidget().layout(); b=button('↻   Programoppdatering',lambda:self.go(10),'nav'); b.setCheckable(True); side.insertWidget(side.count()-4,b); self.nav.append(b)
        if self.update_settings.get('auto_check') and self.update_settings.get('repository'):QTimer.singleShot(2000,self.check_updates)
    def save_and_check(self):
        if self.update_running:raise ValueError('Vent til pågående oppdateringsjobb er ferdig.')
        repo=repository(self.update_repo.text()); self.update_settings.update(repository=repo,channel=self.update_channel.currentText(),auto_check=self.update_auto.isChecked()); self.manager.save(); self.latest_update=None; self.update_download.setEnabled(False); self.check_updates(install=True)
    def check_updates(self,install=False):
        if self.update_running:return
        self.update_running=True; self.update_message.setText('Sjekker GitHub …'); self.update_download.setEnabled(False)
        repo=self.update_settings['repository']; channel=self.update_settings['channel']; task=Task(lambda:check(repo,channel),self); self.tasks.add(task)
        def received(info):
            self.update_running=False; self.latest_update=info; self.update_download.setEnabled(True)
            message=f"{channel}: {info['version']} • bygg {info['build']}"+(' — ny utgave tilgjengelig' if info['newer'] else ' — ingen nyere utgave')
            self.update_message.setText(message)
            if info['newer']:self.events.put(message); self.statusBar().showMessage(message+' • Åpne Programoppdatering')
            if info['newer'] and install:self.download_update(True)
        def failed(msg):self.update_running=False; self.update_message.setText(msg)
        task.done.connect(received); task.failed.connect(lambda msg:failed(network_message(msg))); task.finished.connect(lambda:self.tasks.discard(task)); task.finished.connect(task.deleteLater); task.start()
    def download_update(self,install=False):
        if not self.latest_update:raise ValueError('Sjekk etter en utgave først.')
        if self.update_running:return
        self.update_running=True; self.update_download.setEnabled(False); self.update_message.setText('Laster ned og kontrollerer Windows-pakken …')
        update=dict(self.latest_update)
        def work():
            path=download(update,self.manager.home/'program_updates')
            return stage_install(update,path,self.manager.home) if install else path
        task=Task(work,self); self.tasks.add(task)
        def received(path):
            self.update_running=False; self.update_download.setEnabled(True)
            self.update_message.setText('✓ Oppdatering er kontrollert og klargjort: '+Path(path).parent.name)
            if install:
                self.staged_exe=path
                QTimer.singleShot(200,lambda:self.guard(self.apply_update))
        def failed(msg):self.update_running=False; self.update_download.setEnabled(True); self.update_message.setText(msg)
        task.done.connect(received); task.failed.connect(lambda msg:failed(network_message(msg))); task.finished.connect(lambda:self.tasks.discard(task)); task.finished.connect(task.deleteLater); task.start()
    def apply_update(self):
        if not self.staged_exe:return
        if self.manager.busy or self.steam.running() or self.tasks:
            self.update_message.setText('Oppdateringen er klar. Venter til nettverksjobber, SteamCMD og backup er ferdig …')
            QTimer.singleShot(1000,lambda:self.guard(self.apply_update)); return
        save_processes(self.manager); self.manager.save()
        launch_handoff(self.staged_exe,self.manager.home)
        self.update_handoff=True; self.timer.stop()
        if hasattr(self,'op_timer'):self.op_timer.stop()
        self.close()
    def closeEvent(self,event):
        if getattr(self,'update_handoff',False):
            save_processes(self.manager); self.manager.save(); event.accept(); return
        super().closeEvent(event)
    def open_update_folder(self):
        path=self.manager.home/'program_updates'; path.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
