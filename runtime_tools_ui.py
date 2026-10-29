"""Per-server companion EXEs and closed-log rotation controls."""
import copy,uuid
from pathlib import Path
from PySide6.QtCore import Qt,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,QCheckBox,QSpinBox,QLineEdit,QDialog,QDialogButtonBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QFileDialog,QComboBox,QMenu,QMessageBox)
from desktop import button,label
from runtime_tools import validate_runtime

class ProgramDialog(QDialog):
    def __init__(self,parent,program=None):
        super().__init__(parent);self.setWindowTitle('Tilleggsprogram');self.resize(760,420);self.program=copy.deepcopy(program or dict(id=uuid.uuid4().hex,name='',path='',args='',cwd='',enabled=True,on_start=True,on_restart=True,required=True,wait_seconds=2))
        layout=QVBoxLayout(self);form=QFormLayout();self.name=QLineEdit(self.program['name']);self.path=QLineEdit(self.program['path']);self.args=QLineEdit(self.program.get('args',''));self.cwd=QLineEdit(self.program.get('cwd',''));form.addRow('Navn',self.name)
        for title,edit,fn in [('EXE-fil',self.path,self.choose_exe),('Arbeidsmappe (tom = EXE-mappen)',self.cwd,self.choose_cwd)]:
            row=QHBoxLayout();row.addWidget(edit,1);row.addWidget(button('Bla gjennom …',fn));form.addRow(title,row)
        form.addRow('Argumenter',self.args);self.flags={}
        for key,title in [('enabled','Aktivert'),('on_start','Sjekk/start ved vanlig serverstart'),('on_restart','Sjekk/start ved restart og krasjgjenstart'),('required','Påkrevd – avbryt serverstart hvis programmet feiler')]:
            value=QCheckBox(title);value.setChecked(self.program.get(key,True));form.addRow('',value);self.flags[key]=value
        self.wait=QSpinBox();self.wait.setRange(0,120);self.wait.setValue(self.program.get('wait_seconds',2));form.addRow('Vent etter start, sekunder',self.wait);layout.addLayout(form);layout.addWidget(label('Kjørende prosesser gjenbrukes når full filsti og eventuelle argumenter stemmer. Tilleggsprogrammer stoppes ikke automatisk sammen med DayZ. Ved tjenestedrift vises ikke programvinduer på skrivebordet.','muted'))
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('Legg til / lagre');buttons.button(QDialogButtonBox.Cancel).setText('Avbryt');buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def choose_exe(self):
        path,_=QFileDialog.getOpenFileName(self,'Velg program',self.path.text(),'Windows-program (*.exe)')
        if path:self.path.setText(path);self.name.setText(self.name.text() or Path(path).stem)
    def choose_cwd(self):
        path=QFileDialog.getExistingDirectory(self,'Arbeidsmappe',self.cwd.text())
        if path:self.cwd.setText(path)
    def values(self):
        result=dict(self.program,name=self.name.text().strip() or Path(self.path.text()).stem,path=self.path.text().strip(),args=self.args.text().strip(),cwd=self.cwd.text().strip(),wait_seconds=self.wait.value(),**{k:v.isChecked() for k,v in self.flags.items()});validate_runtime({'programs':[result]});return result

class RuntimeTools(QWidget):
    def __init__(self,studio):
        super().__init__();self.studio=studio;self.programs=[];self.profile_id=None;self.statuses=[];layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);tabs=QTabWidget();layout.addWidget(tabs)
        programs=QWidget();pl=QVBoxLayout(programs);self.profile_picker=QComboBox();self.profile_picker.currentIndexChanged.connect(lambda i:studio.guard(lambda:self.choose_profile(i)));pl.addWidget(label('Serverprofil for EXE-listen','muted'));pl.addWidget(self.profile_picker);pl.addWidget(label('Sjekk EXE-programmer før DayZ starter. Velg hvilke som gjelder ved start og restart. Lagre driftsoppsettet etter endringer.','muted'));row=QHBoxLayout()
        for title,fn in [('Legg til EXE …',self.add),('Rediger …',self.edit),('Fjern fra listen',self.remove),('Sjekk kjørende programmer',self.check)]:row.addWidget(button(title,lambda checked=False,f=fn:studio.guard(f)))
        pl.addLayout(row);self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['Bruk','Program','EXE-fil','Når','Status / PID']);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch);self.table.setColumnWidth(0,70);self.table.setColumnWidth(1,160);self.table.setColumnWidth(3,160);self.table.setColumnWidth(4,170);self.table.setMinimumHeight(210);self.table.itemChanged.connect(self.checkbox_changed);self.table.setContextMenuPolicy(Qt.CustomContextMenu);self.table.customContextMenuRequested.connect(self.context_menu);self.table.doubleClicked.connect(lambda:studio.guard(self.edit));pl.addWidget(self.table);tabs.addTab(programs,'EXE-programmer')
        logs=QWidget();ll=QVBoxLayout(logs);self.enabled=QCheckBox('Arkiver avsluttede RPT / LOG / ADM før serverstart og restart');ll.addWidget(self.enabled);form=QFormLayout();self.days=QSpinBox();self.days.setRange(1,3650);self.count=QSpinBox();self.count.setRange(1,1000);self.mb=QSpinBox();self.mb.setRange(10,102400);form.addRow('Behold arkiver i dager',self.days);form.addRow('Maks antall arkiver',self.count);form.addRow('Maks samlet arkivplass, MB',self.mb);ll.addLayout(form)
        ll.addWidget(label('Bare avsluttede logger i profiles-mappens toppnivå arkiveres. Aktive logger roteres ikke. Siste arkiv beholdes alltid, også hvis én økt overstiger plassgrensen.','muted'));row=QHBoxLayout();row.addWidget(button('Arkiver logger nå (stoppet server)',lambda:studio.guard(self.rotate)));row.addWidget(button('Åpne loggarkiv',self.open_archives));row.addStretch();ll.addLayout(row);tabs.addTab(logs,'Loggrotasjon');self.message=label('Endringer gjelder valgt server.','muted');layout.addWidget(self.message)
    def load(self,p):
        self.profile_picker.blockSignals(True);self.profile_picker.clear();
        for profile in self.studio.manager.state['servers']:self.profile_picker.addItem(profile['name'],profile['id'])
        self.profile_picker.setCurrentIndex(self.profile_picker.findData(p['id']));self.profile_picker.blockSignals(False)
        self.profile_id=p['id'];self.programs=copy.deepcopy(p.get('programs',[]));self.enabled.setChecked(p.get('log_rotation_enabled',False));self.days.setValue(p.get('log_keep_days',14));self.count.setValue(p.get('log_keep_archives',20));self.mb.setValue(p.get('log_max_mb',1024));self.statuses=[];self.render()
    def values(self):
        for i,p in enumerate(self.programs):p['enabled']=self.table.item(i,0).checkState()==Qt.Checked
        result=dict(programs=copy.deepcopy(self.programs),log_rotation_enabled=self.enabled.isChecked(),log_keep_days=self.days.value(),log_keep_archives=self.count.value(),log_max_mb=self.mb.value());validate_runtime(result);return result
    def render(self):
        self.table.blockSignals(True);statuses={s['id']:s for s in self.statuses};self.table.setRowCount(len(self.programs))
        for row,p in enumerate(self.programs):
            enabled=QTableWidgetItem();enabled.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable);enabled.setCheckState(Qt.Checked if p.get('enabled',True) else Qt.Unchecked);self.table.setItem(row,0,enabled)
            status=statuses.get(p['id'],{});text={'running':'Kjører','stopped':'Ikke funnet','unknown':'Ukjent / tilgang'}.get(status.get('status'),'Ikke sjekket');text+=(' • '+', '.join(map(str,status['pids']))) if status.get('pids') else ''
            for col,value in enumerate([p.get('name'),p['path'],('Start ' if p.get('on_start',True) else '')+('Restart' if p.get('on_restart',True) else ''),text],1):self.table.setItem(row,col,QTableWidgetItem(str(value)))
        self.table.blockSignals(False)
    def checkbox_changed(self,item):
        if item.column()==0 and item.row()<len(self.programs):
            self.programs[item.row()]['enabled']=item.checkState()==Qt.Checked
            self.studio.guard(self.persist_programs)
    def sync_checks(self):
        for row,p in enumerate(self.programs):p['enabled']=self.table.item(row,0).checkState()==Qt.Checked
    def add(self):
        self.sync_checks();dialog=ProgramDialog(self)
        if dialog.exec():self.programs.append(dialog.values());self.persist_programs();self.render()
    def edit(self):
        row=self.table.currentRow()
        if row<0:raise ValueError('Velg et program først.')
        self.sync_checks();dialog=ProgramDialog(self,self.programs[row])
        if dialog.exec():self.programs[row]=dialog.values();self.persist_programs();self.render()
    def remove(self):
        row=self.table.currentRow()
        if row>=0:self.sync_checks();self.programs.pop(row);self.persist_programs();self.render()
    def update_status(self,statuses):
        if self.profile_id!=self.studio.p['id']:return
        self.statuses=statuses
        # Do not rebuild checkboxes/selection or overwrite unsaved definitions.
        mapping={s['id']:s for s in statuses}
        for row,p in enumerate(self.programs):
            status=mapping.get(p['id'],{});text={'running':'Kjører','stopped':'Ikke funnet','unknown':'Ukjent / tilgang'}.get(status.get('status'),'Ikke sjekket');text+=(' • '+', '.join(map(str,status['pids']))) if status.get('pids') else '';self.table.item(row,4).setText(text)
    def check(self):
        if not getattr(self.studio.manager,'remote',False):
            from companion_programs import CompanionPrograms
            self.update_status(CompanionPrograms().statuses(self.programs));return
        profile=self.studio.p['id'];job=self.studio.manager.enqueue('program_status',self.studio.p)
        def ready(result):
            if self.studio.p['id']==profile:self.update_status(result);self.message.setText('Status gjelder sist lagrede EXE-liste.')
        self.studio.run_task(lambda:self.studio.manager.wait_job(job),ready,description='EXE-status')
    def rotate(self):
        if not getattr(self.studio.manager,'remote',False):raise ValueError('Loggrotasjon utføres av bakgrunnsagenten i Windows-programmet.')
        profile=self.studio.p['id'];job=self.studio.manager.enqueue('rotate_logs',self.studio.p)
        def ready(result):
            if self.studio.p['id']==profile:self.message.setText(str(result['archived'])+' logger arkivert. '+str(result['skipped'])+' beholdt/ikke tilgjengelig.')
        self.studio.run_task(lambda:self.studio.manager.wait_job(job,timeout=600),ready,description='Loggrotasjon')
    def open_archives(self):
        from log_rotation import archive_folder
        folder=archive_folder(self.studio.manager.home,self.studio.p);folder.mkdir(parents=True,exist_ok=True);QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def persist_programs(self):
        validate_runtime({'programs':self.programs})
        self.studio.p['programs']=copy.deepcopy(self.programs);self.studio.manager.save()
        self.message.setText('EXE-listen er lagret for '+self.studio.p['name']+'.')
    def choose_profile(self,index):
        identity=self.profile_picker.itemData(index)
        if not identity or identity==self.profile_id:return
        self.studio.save_operations()
        target=next(i for i,p in enumerate(self.studio.manager.state['servers']) if p['id']==identity)
        self.studio.selector.setCurrentIndex(target)
    def context_menu(self,position):
        row=self.table.rowAt(position.y())
        if row<0:return
        self.table.selectRow(row);menu=QMenu(self)
        for title,action in [('Start','start'),('Restart','restart'),('Stopp','stop')]:
            menu.addAction(title,lambda checked=False,a=action:self.studio.guard(lambda:self.control_program(a)))
        menu.addSeparator();menu.addAction('Rediger …',lambda:self.studio.guard(self.edit));menu.exec(self.table.viewport().mapToGlobal(position))
    def control_program(self,action):
        row=self.table.currentRow()
        if row<0:raise ValueError('Velg et program først.')
        self.sync_checks();self.persist_programs();program=self.programs[row]
        if action in ('stop','restart'):
            text='Dette avslutter '+program['name']+' og kan påvirke andre serverprofiler som bruker samme prosess. Fortsette?'
            if QMessageBox.question(self,'Tilleggsprogram',text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        if not getattr(self.studio.manager,'remote',False):raise ValueError('Programstyring krever bakgrunnsagenten.')
        profile=self.profile_id;job=self.studio.manager.enqueue('program_'+action,self.studio.p,{'program_id':program['id']})
        def ready(result):
            if self.profile_id==profile:self.message.setText(program['name']+': '+str(result['status']));self.check()
        self.studio.run_task(lambda:self.studio.manager.wait_job(job,timeout=180),ready,description='EXE '+action)
