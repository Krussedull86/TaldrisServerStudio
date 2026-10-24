from pathlib import Path
from PySide6.QtCore import Qt,QThread,Signal
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QCheckBox,QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QFileDialog,QMessageBox)
from local_mods import scan_mods

class Scan(QThread):
    result=Signal(object); failed=Signal(str)
    def __init__(self,path,recursive,parent):super().__init__(parent); self.path=path; self.recursive=recursive
    def run(self):
        try:self.result.emit(scan_mods(self.path,self.recursive))
        except Exception as e:self.failed.emit(str(e))

class LocalModDialog(QDialog):
    def __init__(self,initial='',parent=None):
        super().__init__(parent); self.setWindowTitle('Importer lokale @mods'); self.resize(1040,650); self.rows=[]; self.worker=None; self.selected_rows=[]
        l=QVBoxLayout(self); l.setSpacing(14); title=QLabel('LOKALE MODS / UTVIKLING'); title.setObjectName('eyebrow'); l.addWidget(title)
        intro=QLabel('Velg for eksempel DayZ/!Workshop, servermappen eller din egen byggmappe. Bare modmapper som begynner med @ vises.'); intro.setWordWrap(True); l.addWidget(intro)
        row=QHBoxLayout(); self.directory=QLineEdit(initial); self.directory.setPlaceholderText('Mappe som inneholder @mods …'); row.addWidget(self.directory); browse=QPushButton('Bla gjennom …'); browse.clicked.connect(self.browse); row.addWidget(browse); self.scan_button=QPushButton('Finn @mods'); self.scan_button.clicked.connect(self.scan); row.addWidget(self.scan_button); l.addLayout(row)
        row=QHBoxLayout(); self.recursive=QCheckBox('Søk også i undermapper'); row.addWidget(self.recursive); row.addStretch(); row.addWidget(QLabel('Lastes som:')); self.scope=QComboBox(); self.scope.addItems(['Mod (-mod)','Servermod (-serverMod)','Begge (-mod + -serverMod)']); row.addWidget(self.scope); l.addLayout(row)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(['VELG','MODMAPPE','LOKAL STI','INNHOLD']); self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeToContents); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setAlternatingRowColors(True); l.addWidget(self.table,1)
        self.status=QLabel('Ingen skanning utført.'); self.status.setWordWrap(True); l.addWidget(self.status)
        note=QLabel('Utviklermodus: last direkte fra lokal mappe. Ingen kopiering av PBO-filer og ingen Workshop-oppdatering av disse moddene. Mapper uten pakket PBO kan importeres, men settes inaktive til du har bygget og aktivert dem.'); note.setWordWrap(True); note.setObjectName('muted'); l.addWidget(note)
        row=QHBoxLayout()
        for text,state in [('Velg alle',True),('Velg ingen',False)]:
            b=QPushButton(text); b.clicked.connect(lambda checked=False,s=state:self.check_all(s)); row.addWidget(b)
        row.addStretch(); cancel=QPushButton('Avbryt'); cancel.clicked.connect(self.reject); row.addWidget(cancel); self.import_button=QPushButton('Importer valgte'); self.import_button.setObjectName('primary'); self.import_button.clicked.connect(self.import_selected); row.addWidget(self.import_button); l.addLayout(row)
    def browse(self):
        path=QFileDialog.getExistingDirectory(self,'Velg mappe med @mods',self.directory.text())
        if path:self.directory.setText(path); self.scan()
    def scan(self):
        if self.worker and self.worker.isRunning():return
        self.scan_button.setEnabled(False); self.import_button.setEnabled(False); self.rows=[]; self.table.setRowCount(0); self.status.setText('Leter etter @mapper …')
        self.worker=Scan(self.directory.text(),self.recursive.isChecked(),self); self.worker.result.connect(self.loaded); self.worker.failed.connect(self.error); self.worker.finished.connect(self.finished_scan); self.worker.start()
    def finished_scan(self):self.scan_button.setEnabled(True); self.import_button.setEnabled(True)
    def error(self,msg):self.status.setText(msg)
    def loaded(self,result):
        self.rows=result['mods']; self.table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            item=QTableWidgetItem(); item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable); item.setCheckState(Qt.Checked if row['ready'] else Qt.Unchecked); self.table.setItem(i,0,item)
            for j,text in enumerate([row['name'],row['path'],row['status']],1):self.table.setItem(i,j,QTableWidgetItem(text))
        msg=f"Fant {len(self.rows)} @mapper • {sum(m['ready'] for m in self.rows)} med pakket PBO."
        if result['warnings']:msg+=' '+str(len(result['warnings']))+' mapper kunne ikke leses.'
        self.status.setText(msg); self.status.setToolTip('\n'.join(result['warnings']))
    def check_all(self,state):
        for i in range(self.table.rowCount()):self.table.item(i,0).setCheckState(Qt.Checked if state else Qt.Unchecked)
    def import_selected(self):
        if self.worker and self.worker.isRunning():return
        self.selected_rows=[row for i,row in enumerate(self.rows) if self.table.item(i,0).checkState()==Qt.Checked]
        if not self.selected_rows:QMessageBox.information(self,'Lokale mods','Velg minst én modmappe.'); return
        self.accept()
    def reject(self):
        if self.worker and self.worker.isRunning():self.status.setText('Vent til skanningen er ferdig før du lukker.'); return
        super().reject()
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():event.ignore(); return
        super().closeEvent(event)
