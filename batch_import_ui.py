"""Review and correct a static BAT import before adding/replacing one profile."""
import copy,subprocess
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QComboBox,QLineEdit,QPushButton,QPlainTextEdit,QTableWidget,QTableWidgetItem,QHeaderView,QCheckBox,QDialogButtonBox,QMessageBox,QFileDialog)
from batch_import import read_batch,tokenize,fingerprint
from launch_options import validate_extra

class BatchImportDialog(QDialog):
    def __init__(self,studio,path):
        super().__init__(studio);self.studio=studio;self.result_profile=None;self.report=read_batch(path);self.loading=False
        if not self.report['candidates']:raise ValueError('No supported DayZServer_x64.exe launch was found in the file.\n'+'\n'.join(self.report['warnings'][:15]))
        self.setWindowTitle('Import server from BAT / CMD');self.resize(1000,960)
        layout=QVBoxLayout(self);self.source=QLineEdit(str(path));self.source.setReadOnly(True);layout.addWidget(self.source)
        form=QFormLayout();self.command_choice=QComboBox()
        for candidate in self.report['candidates']:self.command_choice.addItem(f"Line {candidate['line']} • {candidate['profile']['name']}")
        form.addRow('Server launch from file',self.command_choice);self.destination=QComboBox();self.destination.addItem('Create new server profile',None)
        self.targets={}
        for p in studio.manager.state['servers']:
            self.targets[p['id']]=copy.deepcopy(p);self.destination.addItem('Update existing: '+p['name'],p['id'])
        form.addRow('Import into',self.destination);self.fields={}
        for key,title in [('name','Profile name'),('root','Server folder'),('config','Configuration, relative to server folder'),('profiles','Profiles, relative to server folder'),('port','Game port'),('extra_args','Extra launch options')]:
            edit=QLineEdit();self.fields[key]=edit
            if key=='root':
                row=QHBoxLayout();row.addWidget(edit);browse=QPushButton('Browse …');browse.clicked.connect(self.browse_root);row.addWidget(browse);form.addRow(title,row)
            else:form.addRow(title,edit)
        self.local=QCheckBox('Local test — do not require Steam Query');form.addRow('',self.local)
        self.firewall=QCheckBox('Create a firewall rule when the server is started later');self.firewall.setChecked(True);form.addRow('',self.firewall);layout.addLayout(form)
        self.mods=QTableWidget(0,4);self.mods.setHorizontalHeaderLabels(['Use','Local mod path (editable)','Load mode','Status']);self.mods.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);self.mods.verticalHeader().setDefaultSectionSize(48);self.mods.setMinimumHeight(190);self.mods.setColumnWidth(0,55);self.mods.setColumnWidth(2,130);self.mods.setColumnWidth(3,150);layout.addWidget(self.mods,1)
        self.notes=QPlainTextEdit();self.notes.setReadOnly(True);self.notes.setMaximumHeight(120);layout.addWidget(self.notes)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('Import profile');buttons.button(QDialogButtonBox.Cancel).setText('Cancel');buttons.accepted.connect(self.commit);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.command_choice.currentIndexChanged.connect(self.populate);self.mods.itemChanged.connect(self.inspect);self.fields['root'].editingFinished.connect(self.inspect);self.fields['config'].editingFinished.connect(self.inspect);self.populate(0)
    def browse_root(self):
        path=QFileDialog.getExistingDirectory(self,'Existing server folder',self.fields['root'].text())
        if path:self.fields['root'].setText(path);self.inspect()
    def populate(self,index):
        self.loading=True;candidate=self.report['candidates'][index];p=candidate['profile']
        for key,edit in self.fields.items():edit.setText(subprocess.list2cmdline(p['extra_args']) if key=='extra_args' else str(p[key]))
        self.mods.setRowCount(len(p['mods']))
        for row,m in enumerate(p['mods']):
            enabled=QTableWidgetItem();enabled.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);enabled.setCheckState(Qt.Checked);self.mods.setItem(row,0,enabled);self.mods.setItem(row,1,QTableWidgetItem(m['path']));mode=QComboBox();mode.addItem('mod','client');mode.addItem('serverMod','server');mode.addItem('both','both');mode.setCurrentIndex(mode.findData(m['load_mode']));self.mods.setCellWidget(row,2,mode);self.mods.setItem(row,3,QTableWidgetItem())
        from windows_firewall import server_ports
        try:server_ports(p);self.local.setChecked(False)
        except (OSError,ValueError):self.local.setChecked(True)
        self.loading=False;self.inspect()
    def inspect(self,*args):
        if self.loading:return
        self.loading=True
        root=Path(self.fields['root'].text());notes=['The BAT file is not executed. Importing creates no server files, downloads no mods and does not start the server. All mods are registered as local sources.']
        notes+=self.report['warnings']+self.report['candidates'][self.command_choice.currentIndex()]['warnings']
        if not (root/'DayZServer_x64.exe').is_file():notes.append('DayZServer_x64.exe is missing — correct the server folder.')
        if not (root/self.fields['config'].text()).is_file():notes.append('The configuration file was not found — correct the path.')
        for row in range(self.mods.rowCount()):
            path=Path(self.mods.item(row,1).text());status='Found' if path.is_dir() else 'Missing'
            if path.is_dir() and not any(child.is_dir() and child.name.casefold()=='addons' and next(child.glob('*.pbo'),None) is not None for child in path.iterdir()):status='No PBO found'
            item=self.mods.item(row,3);item.setFlags(Qt.ItemIsEnabled);item.setText(status)
        self.notes.setPlainText('\n'.join(notes));self.loading=False
    def reviewed(self):
        from core import validate_mod
        data={key:edit.text().strip() for key,edit in self.fields.items()};data['port']=int(data['port']);data['extra_args']=validate_extra([v for v,_ in tokenize(data['extra_args'])]);data.update(query_enabled=not self.local.isChecked(),auto_firewall=self.firewall.isChecked(),mods=[])
        seen={}
        for row in range(self.mods.rowCount()):
            path=Path(self.mods.item(row,1).text().strip());mode=self.mods.cellWidget(row,2).currentData();m=dict(folder=path.name,id='',source='local',path=str(path),load_mode=mode,server=mode=='server',enabled=self.mods.item(row,0).checkState()==Qt.Checked);validate_mod(m)
            identity=str(path.resolve()).casefold()
            if identity in seen:raise ValueError('The same mod path appears more than once. Remove the duplicate from the BAT file before importing.')
            seen[identity]=True;data['mods'].append(m)
        return data
    def commit(self):
        try:
            data=self.reviewed();target=self.destination.currentData();old=self.targets.get(target)
            if hasattr(self.studio,'check_import_target'):self.studio.check_import_target(target)
            if QMessageBox.question(self,'Confirm import','Update profile '+old['name']+' with the displayed fields and mod list? Server files are preserved.' if old else 'Create a new profile with the displayed settings? The server will not be started.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            if getattr(self.studio.manager,'remote',False):self.result_profile=self.studio.manager.import_batch(data,target,fingerprint(old) if old else None)
            else:
                from batch_import import apply_profile
                self.result_profile=apply_profile(self.studio.manager,data,target,fingerprint(old) if old else None)
            self.accept()
        except Exception as error:QMessageBox.warning(self,'Import',str(error))
