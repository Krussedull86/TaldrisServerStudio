"""Local client configuration belongs to the desktop, never the background service."""
import json
from pathlib import Path
import psutil
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView,QDialogButtonBox,QMessageBox
from desktop import button,label
from client_launch import steam_roots,find_game,client_mods,command,launch

class ClientDialog(QDialog):
    def __init__(self,studio):
        super().__init__(studio);self.studio=studio;self.profile=dict(studio.p);self.setWindowTitle('Koble DayZ til lokalt • '+self.profile['name']);self.resize(920,560);self.file=Path(studio.manager.home)/'local_client.json';self.roots=steam_roots()
        try:self.settings=json.loads(self.file.read_text('utf-8'))
        except (OSError,ValueError):self.settings={}
        if not isinstance(self.settings,dict):self.settings={}
        if not isinstance(self.settings.get('mods',{}),dict):self.settings['mods']={}
        self.overrides=dict(self.settings.get('mods',{}));layout=QVBoxLayout(self);layout.addWidget(label('Starter DayZ (Steam-app 221100) med BattlEye på denne PC-en. Steam må være innlogget. Lukk en eventuell åpen DayZ-klient først.','muted'));row=QHBoxLayout();self.game=QLineEdit(self.settings.get('game') or find_game(self.roots));self.game.setPlaceholderText('SteamLibrary/steamapps/common/DayZ');row.addWidget(self.game,1);row.addWidget(button('Velg DayZ-mappe …',self.browse));layout.addLayout(row);layout.addWidget(label('Server: '+self.profile['name']+' • 127.0.0.1:'+str(self.profile['port'])+' • spillport, uten Steam Query','muted'));layout.addWidget(label('Aktive mods av typen mod/begge lastes i profilens rekkefølge. Servermods utelates. Dobbeltklikk for å velge en annen lokal modmappe.','muted'));self.table=QTableWidget(0,2);self.table.setHorizontalHeaderLabels(['Klientmod','Lokal modmappe']);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);self.table.setColumnWidth(0,250);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.cellDoubleClicked.connect(self.browse_mod);layout.addWidget(self.table);layout.addWidget(button('Sjekk modmapper på nytt',self.refresh));buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('Start DayZ og koble til');buttons.button(QDialogButtonBox.Cancel).setText('Avbryt');buttons.accepted.connect(lambda:studio.guard(self.start));buttons.rejected.connect(self.reject);layout.addWidget(buttons);self.refresh()
    def browse(self):
        folder=QFileDialog.getExistingDirectory(self,'Velg DayZ-klientens spillmappe',self.game.text())
        if folder:self.game.setText(folder);self.refresh()
    def refresh(self):
        self.mods=client_mods(self.profile,self.game.text(),self.roots,self.overrides);self.table.setRowCount(len(self.mods))
        for row,mod in enumerate(self.mods):
            self.table.setItem(row,0,QTableWidgetItem(mod['title']));self.table.setItem(row,1,QTableWidgetItem(mod['path'] or 'MANGLER – dobbeltklikk og velg modmappe'))
    def browse_mod(self,row,column):
        mod=self.mods[row];folder=QFileDialog.getExistingDirectory(self,'Velg mappe med Addons: '+mod['title'],mod['path'])
        if folder:self.overrides[mod['identity']]=folder;self.refresh()
    def start(self):
        self.refresh();args=command(self.game.text(),self.profile,self.mods)
        for proc in psutil.process_iter(['name']):
            if str(proc.info.get('name','')).casefold() in ('dayz_x64.exe','dayzdiag_x64.exe','dayz_be.exe'):raise ValueError('DayZ kjører allerede. Lukk spillet slik at riktig modliste kan lastes ved ny oppstart.')
        self.file.write_text(json.dumps(dict(game=self.game.text(),mods=self.overrides),indent=2),encoding='utf-8')
        process=launch(args);self.studio.events.put('DayZ-klient startet • PID '+str(process.pid)+' • 127.0.0.1:'+str(self.profile['port'])+' • '+str(len(self.mods))+' klientmods. Dette bekrefter ikke tilkobling til serveren.');self.accept()

def connect_local(studio):ClientDialog(studio).exec()
