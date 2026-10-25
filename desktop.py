"""Taldris Server Studio — native Qt desktop interface."""
import sys, os, json, queue, time, shutil, uuid
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QPixmap, QDesktopServices, QFont
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,QStackedWidget,QComboBox,QLineEdit,QPlainTextEdit,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QFileDialog,QMessageBox,QInputDialog,QCheckBox,QFormLayout,QScrollArea,QGraphicsView,QGraphicsScene,QGraphicsItem,QSplitter)
from core import Manager, validate, local_path, command, mod_load_mode
from server_diagnostics import describe,current_logs

STYLE='''
QWidget { background:#0c111b; color:#e4ebf7; font-family:"Segoe UI"; font-size:13px; }
QFrame#sidebar { background:#101725; border-right:1px solid #222e41; }
QFrame#card { background:#141e2e; border:1px solid #263449; border-radius:15px; }
QFrame#card QLabel { background:transparent; }
QLabel {background:transparent;}
QLabel#muted { color:#8b9bb4; } QLabel#eyebrow {color:#65dfc5;font-size:11px;font-weight:700;}
QLabel#title {font-size:29px;font-weight:700;} QLabel#metric {font-size:30px;font-weight:700;}
QLabel#brand {font-size:22px;font-weight:800;color:#65dfc5;}
QPushButton { background:#1b293d; border:1px solid #304158;border-radius:9px;padding:10px 16px;font-weight:600; }
QPushButton:hover {background:#293d56;border-color:#66809e;} QPushButton:disabled {color:#55657d;background:#141e2c;}
QPushButton#primary {background:#66e1c2;color:#09251f;border:0;} QPushButton#primary:hover {background:#9cf1dc;}
QPushButton#danger {color:#ffacac;background:#38242e;border-color:#60404b;}
QPushButton#nav {text-align:left;background:transparent;border:0;color:#94a5c0;padding:14px 16px;}
QPushButton#nav:checked {background:#1e343b;color:#7ceacc;border-left:3px solid #70e3c5;}
QLineEdit,QComboBox,QPlainTextEdit {background:#101a29;border:1px solid #2c3c53;border-radius:8px;padding:10px;selection-background-color:#267969;}
QLineEdit:focus,QPlainTextEdit:focus {border-color:#6adbbf;}
QTableWidget {background:#111a29;alternate-background-color:#152133;border:1px solid #28364c;border-radius:10px;gridline-color:#223048;selection-background-color:#244a4a;}
QHeaderView::section {background:#19263a;color:#94a8c5;padding:12px;border:0;font-weight:600;}
QTableWidget::item {padding:8px;} QScrollArea {border:0;}
QScrollBar:vertical {background:#101725;width:9px;} QScrollBar::handle:vertical {background:#34465f;border-radius:4px;min-height:25px;}
QStatusBar {color:#8d9eb9;border-top:1px solid #263449;}
QCheckBox {spacing:10px;padding:8px;} QToolTip {background:#23344d;color:white;border:1px solid #476080;}
'''
def label(text,style=None):
    w=QLabel(text); w.setWordWrap(True)
    if style:w.setObjectName(style)
    return w

def button(text,fn,kind=None):
    b=QPushButton(text); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(fn)
    if kind:b.setObjectName(kind)
    return b

def card(title,desc=None):
    f=QFrame(); f.setObjectName('card'); l=QVBoxLayout(f); l.setContentsMargins(22,20,22,20); l.setSpacing(12); l.addWidget(label(title,'eyebrow'))
    if desc:l.addWidget(label(desc,'muted'))
    return f,l

class MapView(QGraphicsView):
    def __init__(self,owner):
        super().__init__(); self.owner=owner; self.setScene(QGraphicsScene(self)); self.setRenderHint(QPainter.Antialiasing); self.setDragMode(QGraphicsView.ScrollHandDrag); self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.setBackgroundBrush(QColor('#101a26')); self.setMinimumHeight(340)
    def wheelEvent(self,e):
        scale=self.transform().m11(); factor=1.2 if e.angleDelta().y()>0 else 1/1.2
        if .08<scale*factor<30:self.scale(factor,factor)
    def mouseDoubleClickEvent(self,e):
        p=self.mapToScene(e.position().toPoint())
        if 0<=p.x()<=1000 and 0<=p.y()<=1000:self.owner.add_marker(p.x()/1000,p.y()/1000)
    def render_map(self):
        s=self.scene(); s.clear(); p=self.owner.p; path=p.get('map_image',''); image=QPixmap(path) if path else QPixmap()
        if not image.isNull():s.addPixmap(image.scaled(1000,1000,Qt.IgnoreAspectRatio,Qt.SmoothTransformation))
        else:
            s.addRect(0,0,1000,1000,QPen(QColor('#33475b')),QBrush(QColor('#12212c')))
            t=s.addText('LEGG TIL DITT KARTBILDE',QFont('Segoe UI',18)); t.setDefaultTextColor(QColor('#507084')); t.setPos(285,470)
        for i in range(11):
            k=i*100; pen=QPen(QColor(120,171,188,45)); s.addLine(k,0,k,1000,pen); s.addLine(0,k,1000,k,pen)
        for m in p['markers']:
            x=m['x']/p['map_size']*1000; y=(1-m['z']/p['map_size'])*1000
            s.addEllipse(x-6,y-6,12,12,QPen(QColor('#b2ffe9')),QBrush(QColor('#61e2bb')))
            t=s.addText(m['name'],QFont('Segoe UI',11)); t.setDefaultTextColor(QColor('#e6fff8')); t.setPos(x+10,y-17); t.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        s.setSceneRect(QRectF(-20,-20,1040,1040)); self.reset_view()
    def reset_view(self):self.fitInView(self.sceneRect(),Qt.KeepAspectRatio)

class Studio(QMainWindow):
    def __init__(self,home=None):
        super().__init__(); self.setWindowTitle('Taldris Server Studio • 0.5'); self.resize(1440,940); self.setMinimumSize(1120,780)
        self.events=queue.Queue(); self.manager=getattr(self,'manager_class',Manager)(home or Path(os.getenv('LOCALAPPDATA',Path.home()))/'TaldrisServerStudio',self.events.put)
        self.p=self.manager.state['servers'][0]; self.deadlines={}; self.log_signature=None; self.page_names=['Oversikt','Kart og markører','Modbibliotek','Logger','Konfigurasjon','Sikkerhetskopier','Automatisering','Innstillinger']
        shell=QWidget(); self.setCentralWidget(shell); outer=QHBoxLayout(shell); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        sidebar=QFrame(); sidebar.setObjectName('sidebar'); sidebar.setFixedWidth(248); left=QVBoxLayout(sidebar); left.setContentsMargins(18,28,18,22); left.setSpacing(9)
        left.addWidget(label('◈  TALDRIS','brand')); left.addWidget(label('SERVER STUDIO','muted')); left.addSpacing(28); left.addWidget(label('ARBEIDSOMRÅDE','eyebrow'))
        self.nav=[]
        for i,(name,icon) in enumerate(zip(self.page_names,['◫','⌖','▦','≡','⚙','◇','◷','☷'])):
            b=button(icon+'   '+name,lambda checked=False,n=i:self.go(n),'nav'); b.setCheckable(True); left.addWidget(b); self.nav.append(b)
        left.addStretch(); left.addWidget(label('LOKAL VERT','eyebrow')); left.addWidget(label('Windows / DayZ Dedicated\nDine filer. Din server.','muted')); outer.addWidget(sidebar)
        main=QVBoxLayout(); main.setContentsMargins(28,25,28,20); main.setSpacing(20); outer.addLayout(main,1)
        header=QHBoxLayout(); headings=QVBoxLayout(); headings.addWidget(label('SERVER WORKSPACE','eyebrow')); self.heading=label('Oversikt','title'); headings.addWidget(self.heading); header.addLayout(headings); header.addStretch()
        self.selector=QComboBox(); self.selector.setMinimumWidth(245); self.selector.currentIndexChanged.connect(self.select); header.addWidget(self.selector); header.addWidget(button('+ Ny server',self.new_server)); main.addLayout(header)
        self.stack=QStackedWidget(); main.addWidget(self.stack,1)
        self.overview(); self.map_page(); self.mods_page(); self.logs_page(); self.config_page(); self.backups_page(); self.automation_page(); self.settings_page()
        self.statusBar().showMessage('Lokal administrasjon • Ingen eksterne tjenester tilkoblet')
        self.load(); self.go(0); self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(1500); self.tick()
    def guard(self,fn):
        try:return fn()
        except Exception as e:QMessageBox.warning(self,'Taldris',str(e))
    def action(self,fn):return lambda:self.guard(fn)
    def page(self):
        w=QWidget(); layout=QVBoxLayout(w); layout.setContentsMargins(0,0,0,0); layout.setSpacing(18); self.stack.addWidget(w); return layout
    def go(self,n):
        self.stack.setCurrentIndex(n); self.heading.setText(self.page_names[n])
        for i,b in enumerate(self.nav):b.setChecked(i==n)
        if n==5:self.refresh_backups()
        if n==1:QTimer.singleShot(0,self.map.reset_view)
    def update_server(self,p=None):self.manager.job(p or self.p,self.manager.update)
    def overview(self):
        l=self.page(); hero,h=card('SERVERKONTROLL'); self.server_title=label('Din DayZ-server','title'); h.addWidget(self.server_title)
        self.server_status=label('STOPPET','eyebrow'); h.addWidget(self.server_status); self.launch_detail=label('Ingen serveroppstart er registrert i denne økten.','muted'); h.addWidget(self.launch_detail); h.addWidget(label('Start, følg og vedlikehold serveren fra ett sted.','muted'))
        actions=QHBoxLayout(); self.start_btn=button('▶  Start server',self.action(lambda:self.manager.start(self.p)),'primary'); self.stop_btn=button('■  Tvungen stopp',self.stop,'danger')
        actions.addWidget(self.start_btn); actions.addWidget(self.stop_btn); actions.addWidget(button('Vis oppstartslogg',self.action(self.show_launch_log))); actions.addWidget(button('↗  Koble til lokalt',lambda:QDesktopServices.openUrl(QUrl('steam://connect/127.0.0.1:'+str(self.p['port']))))); actions.addStretch(); h.addLayout(actions); l.addWidget(hero)
        metrics=QHBoxLayout(); self.metrics=[]
        for title,foot in [('AKTIVE MODS','Valgt lastrekkefølge'),('KARTMARKØRER','Dine egne steder'),('SPILLPORT','Lokal serverprofil'),('SPILLERE','Live data ikke tilkoblet')]:
            f,c=card(title); value=label('—','metric'); c.addWidget(value); c.addWidget(label(foot,'muted')); metrics.addWidget(f); self.metrics.append(value)
        l.addLayout(metrics)
        self.all_servers=QTableWidget(0,5); self.all_servers.setHorizontalHeaderLabels(['Server','Status','Spillport','Steam query','Mappe']); self.all_servers.setEditTriggers(QAbstractItemView.NoEditTriggers); self.all_servers.setSelectionBehavior(QAbstractItemView.SelectRows); self.all_servers.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.all_servers.setMinimumHeight(145); self.all_servers.setMaximumHeight(170); self.all_servers.cellDoubleClicked.connect(lambda row,column:self.selector.setCurrentIndex(row)); l.addWidget(self.all_servers)
        row=QHBoxLayout(); quick,q=card('VEDLIKEHOLD','Oppdatering og backup krever at serveren er stoppet.')
        q.addWidget(button('↓  Oppdater server og Workshop',self.action(lambda:self.update_server())))
        q.addWidget(button('◇  Opprett sikkerhetskopi',self.action(lambda:self.manager.job(self.p,self.manager.backup))))
        q.addWidget(button('⚙  Åpne serveroppsett',lambda:self.go(7))); q.addStretch(); row.addWidget(quick,1)
        activity,a=card('HENDELSESSTRØM'); self.activity=QPlainTextEdit(); self.activity.setReadOnly(True); self.activity.setMaximumBlockCount(1000); self.activity.setPlaceholderText('Her vises oppstart, oppdateringer, backup og feilmeldinger.'); a.addWidget(self.activity); row.addWidget(activity,2); l.addLayout(row,1)
        l.addWidget(label('Dobbeltklikk på en server i tabellen for å velge den. Flere servere kan kjøre samtidig. Kontroller RPT for å bekrefte at DayZ er klar.','muted'))
    def map_page(self):
        l=self.page(); bar=QHBoxLayout(); bar.addWidget(label('Et arbeidskart for steder, baser og soner.','muted')); bar.addStretch(); bar.addWidget(button('Legg til kartbilde',self.map_file)); bar.addWidget(button('Tilpass visning',lambda:self.map.reset_view())); l.addLayout(bar)
        split=QSplitter(); self.map=MapView(self); split.addWidget(self.map); panel=QWidget(); panel.setMinimumWidth(250); pl=QVBoxLayout(panel); pl.addWidget(label('STEDER PÅ KARTET','eyebrow'))
        pl.addWidget(label('Scroll for zoom. Dra for å flytte. Dobbeltklikk for ny markør.','muted')); self.marker_list=QTableWidget(0,2); self.marker_list.setHorizontalHeaderLabels(['Sted','X / Z']); self.marker_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.marker_list.setSelectionBehavior(QAbstractItemView.SelectRows); self.marker_list.setEditTriggers(QAbstractItemView.NoEditTriggers); pl.addWidget(self.marker_list)
        pl.addWidget(button('Fjern valgt markør',self.remove_marker)); pl.addWidget(button('Eksporter JSON',self.export_markers)); split.addWidget(panel); split.setSizes([800,280]); l.addWidget(split,1)
        l.addWidget(label('PLANLEGGINGSKART • Ingen live spillerposisjoner. Eget kvadratisk kartbilde, nord opp.','muted'))
    def map_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Velg kartbilde','','Bilder (*.png *.jpg *.jpeg *.webp)')
        if path:
            image=QPixmap(path)
            if image.isNull():return QMessageBox.warning(self,'Kart','Kunne ikke lese bildet.')
            if image.width()!=image.height():return QMessageBox.warning(self,'Kart','Bruk et kvadratisk kartbilde for riktige koordinater.')
            self.p['map_image']=path; self.manager.save(); self.refresh_map()
    def add_marker(self,x,y):
        name,ok=QInputDialog.getText(self,'Ny markør','Navn på sted / base / sone:')
        if ok and name.strip():self.p['markers'].append(dict(name=name.strip(),x=round(x*self.p['map_size'],1),z=round((1-y)*self.p['map_size'],1))); self.manager.save(); self.refresh_map()
    def remove_marker(self):
        i=self.marker_list.currentRow()
        if i>=0:self.p['markers'].pop(i); self.manager.save(); self.refresh_map()
    def export_markers(self):
        p,_=QFileDialog.getSaveFileName(self,'Eksporter markører','markers.json','JSON (*.json)')
        if p:self.guard(lambda:Path(p).write_text(json.dumps(self.p['markers'],indent=2,ensure_ascii=False),'utf-8'))
    def refresh_map(self):
        self.map.render_map(); self.marker_list.setRowCount(len(self.p['markers']))
        for i,m in enumerate(self.p['markers']):
            for j,t in enumerate([m['name'],f"{m['x']:.0f} / {m['z']:.0f}"]):self.marker_list.setItem(i,j,QTableWidgetItem(t))
    def mods_page(self):
        l=self.page(); row=QHBoxLayout(); self.mod_search=QLineEdit(); self.mod_search.setPlaceholderText('Søk etter modnavn eller Workshop-ID …'); self.mod_search.textChanged.connect(self.filter_mods); row.addWidget(self.mod_search); row.addWidget(button('+ Legg til mod',self.action(self.mod_add),'primary')); l.addLayout(row)
        self.mods=QTableWidget(0,5); self.mods.setHorizontalHeaderLabels(['LASTEREKKEFØLGE','MODMAPPE','WORKSHOP-ID','LASTING','STATUS']); self.mods.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.mods.setAlternatingRowColors(True); self.mods.setSelectionBehavior(QAbstractItemView.SelectRows); self.mods.setSelectionMode(QAbstractItemView.SingleSelection); self.mods.setEditTriggers(QAbstractItemView.NoEditTriggers); self.mods.verticalHeader().hide(); l.addWidget(self.mods,1)
        row=QHBoxLayout()
        for name,fn in [('↑ Opp',lambda:self.mod_move(-1)),('↓ Ned',lambda:self.mod_move(1)),('Aktiver / deaktiver',self.mod_toggle),('Fjern',self.mod_remove),('Installer nedlastede mods',lambda:self.manager.job(self.p,self.manager.deploy))]:row.addWidget(button(name,self.action(fn)))
        l.addLayout(row); l.addWidget(label('Mods lastes i denne rekkefølgen. Kontroller avhengigheter på Workshop. CF må stå før mods som trenger CF.','muted'))
    def editable(self):
        if self.manager.running(self.p) or self.p['id'] in self.manager.busy:raise ValueError('Stopp serveren og vent til jobber er ferdige først.')
    def mod_add(self):
        self.editable(); name,ok=QInputDialog.getText(self,'Legg til mod','Modmappe, for eksempel @CF:')
        if not ok or not name.strip():return
        wid,ok=QInputDialog.getText(self,'Workshop','Workshop-ID, tom for lokale mods:')
        if not ok:return
        scope,ok=QInputDialog.getItem(self,'Lasting','Modtype:',['Mod (-mod)','Servermod (-serverMod)','Begge (-mod + -serverMod)'],0,False)
        if not ok:return
        mode={'Mod (-mod)':'client','Servermod (-serverMod)':'server','Begge (-mod + -serverMod)':'both'}[scope]
        m=dict(folder=name.strip(),id=wid.strip(),enabled=True,server=mode=='server',load_mode=mode); validate(dict(self.p,mods=self.p['mods']+[m]))
        if any(x['folder'].casefold()==m['folder'].casefold() for x in self.p['mods']):raise ValueError('Modmappen finnes allerede.')
        self.p['mods'].append(m); self.mod_save()
    def mod_index(self):
        i=self.mods.currentRow()
        if i<0:raise ValueError('Velg en mod først.')
        return i
    def mod_move(self,d):
        self.editable(); i=self.mod_index(); j=i+d
        if 0<=j<len(self.p['mods']):self.p['mods'][i],self.p['mods'][j]=self.p['mods'][j],self.p['mods'][i]; self.mod_save(); self.mods.selectRow(j)
    def mod_toggle(self):
        self.editable(); m=self.p['mods'][self.mod_index()]; m['enabled']=not m['enabled']; self.mod_save()
    def mod_remove(self):self.editable(); self.p['mods'].pop(self.mod_index()); self.mod_save()
    def mod_save(self):self.manager.save(); self.refresh_mods()
    def refresh_mods(self):
        self.mods.setRowCount(len(self.p['mods']))
        for i,m in enumerate(self.p['mods']):
            for j,t in enumerate([f'{i+1:02d}',m['folder'],m['id'] or 'Lokal mod',{'client':'Mod','server':'Servermod','both':'Begge'}[mod_load_mode(m)],'● Aktiv' if m['enabled'] else 'Inaktiv']):self.mods.setItem(i,j,QTableWidgetItem(t))
            self.mods.item(i,4).setForeground(QColor('#6ae1bd' if m['enabled'] else '#8192aa'))
        self.filter_mods()
    def filter_mods(self):
        text=self.mod_search.text().casefold()
        for i in range(self.mods.rowCount()):self.mods.setRowHidden(i,not any(text in self.mods.item(i,j).text().casefold() for j in [1,2]))
    def logs_page(self):
        l=self.page(); row=QHBoxLayout(); row.addWidget(button('Åpne loggfil',self.open_log)); row.addWidget(button('Nyeste RPT',self.action(self.latest_log))); self.log_path=QLineEdit(); self.log_path.setReadOnly(True); self.log_path.setPlaceholderText('Ingen logg valgt'); row.addWidget(self.log_path,1); l.addLayout(row)
        self.log_text=QPlainTextEdit(); self.log_text.setReadOnly(True); self.log_text.setFont(QFont('Consolas',11)); self.log_text.setPlaceholderText('Velg en DayZ-logg. De siste 100 KB oppdateres automatisk.'); l.addWidget(self.log_text,1)
    def open_log(self):
        p,_=QFileDialog.getOpenFileName(self,'Åpne logg','','Logger (*.RPT *.rpt *.log *.ADM);;Alle filer (*)')
        if p:self.log_path.setText(p); self.log_signature=None
    def latest_log(self):
        validate(self.p); files=list(local_path(self.p['root'],self.p['profiles']).glob('*.RPT'))
        if not files:raise ValueError('Ingen RPT i profilmappen.')
        self.log_path.setText(str(max(files,key=lambda f:f.stat().st_mtime))); self.log_signature=None
    def config_page(self):
        l=self.page(); row=QHBoxLayout(); row.addWidget(button('Les fra disk',self.action(self.read_config))); row.addWidget(button('Lagre med backup',self.action(self.save_config),'primary')); row.addWidget(button('Steam query-port',self.action(self.edit_query_port))); row.addWidget(button('Bohemia: konfigurasjon',lambda:QDesktopServices.openUrl(QUrl('https://community.bistudio.com/wiki/DayZ:Server_Configuration')))); row.addStretch(); l.addLayout(row)
        self.editor=QPlainTextEdit(); self.editor.setFont(QFont('Consolas',12)); self.editor.setPlaceholderText('Velg servermappe i Innstillinger for å redigere serverkonfigurasjonen.'); l.addWidget(self.editor,1); l.addWidget(label('Eksisterende konfigurasjon sikkerhetskopieres før lagring. Krever omstart for å tre i kraft.','muted'))
    def edit_query_port(self):
        from windows_firewall import set_query_port
        port,ok=QInputDialog.getInt(self,'Steam query-port','UDP-port for Steam-serverlisten. Lagre konfigurasjonen etterpå.',int(self.p['port'])+3,1,65535)
        if ok:self.editor.setPlainText(set_query_port(self.editor.toPlainText(),port))
    def read_config(self):
        self.editor.clear(); self.config_source=None
        if self.p['root']:
            path=local_path(self.p['root'],self.p['config']); self.config_source=path.read_text('utf-8') if path.exists() else None
            self.editor.setPlainText(self.config_source or 'hostname = "Taldris DayZ";\nmaxPlayers = 40;\nverifySignatures = 2;\nforceSameBuild = 1;\nclass Missions { class DayZ { template = "dayzOffline.chernarusplus"; }; };\n')
    def save_config(self):
        self.editable(); validate(self.p); path=local_path(self.p['root'],self.p['config']); current=path.read_text('utf-8') if path.exists() else None
        if current!=self.config_source:raise ValueError('Filen er endret eksternt. Les fra disk først.')
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():shutil.copy2(path,path.with_name(path.name+'.'+uuid.uuid4().hex[:8]+'.bak'))
        path.write_text(self.editor.toPlainText(),'utf-8'); self.read_config(); self.events.put('Konfigurasjon lagret.')
    def backups_page(self):
        l=self.page(); f,c=card('SIKKERHETSNETT','Sikre serverdata før du endrer oppsett eller mods. Serveren må være stoppet.'); row=QHBoxLayout(); row.addWidget(button('◇  Opprett backup',self.action(lambda:self.manager.job(self.p,self.manager.backup)),'primary')); row.addWidget(button('Åpne backupmappe',self.open_backups)); row.addWidget(button('Oppdater liste',self.refresh_backups)); row.addStretch(); c.addLayout(row); l.addWidget(f)
        self.backups=QTableWidget(0,3); self.backups.setHorizontalHeaderLabels(['ARKIV','STØRRELSE','OPPRETTET']); self.backups.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.backups.setEditTriggers(QAbstractItemView.NoEditTriggers); l.addWidget(self.backups,1)
        l.addWidget(label('Inkluderer konfigurasjon, profiles, mpmissions og battleye. Gjenoppretting gjøres manuelt mens serveren er stoppet. Arkiver kan inneholde passord og spillerdata.','muted'))
    def open_backups(self):
        p=self.manager.home/'backups'/self.p['id']; p.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
    def refresh_backups(self):
        files=sorted((self.manager.home/'backups'/self.p['id']).glob('*.zip'),reverse=True); self.backups.setRowCount(len(files))
        for i,p in enumerate(files):
            for j,t in enumerate([p.name,f'{p.stat().st_size/1024/1024:.2f} MB',time.strftime('%d.%m.%Y %H:%M',time.localtime(p.stat().st_mtime))]):self.backups.setItem(i,j,QTableWidgetItem(t))
    def automation_page(self):
        l=self.page(); f,c=card('AUTOMATISK VEDLIKEHOLD','Oppdater serverfiler og last ned aktive Workshop-mods med jevne mellomrom.'); self.auto=QCheckBox('Aktiver automatiske SteamCMD-jobber mens serveren er stoppet'); c.addWidget(self.auto); self.interval=QLineEdit(); self.interval.setPlaceholderText('60'); c.addWidget(label('Intervall i minutter (minst 5)','muted')); c.addWidget(self.interval); c.addWidget(button('Lagre automatisering',self.action(self.save_automation),'primary')); l.addWidget(f)
        f,c=card('DRIFTSREGLER'); c.addWidget(label('• Panelet må være åpent.\n• Aktive serverprosesser stoppes ikke automatisk.\n• Steam Guard sendes i SteamCMD-konsollen.\n• Workshop-mods installeres etter bekreftet nedlasting.\n• Serveren startes ikke automatisk etter oppdatering.','muted')); l.addWidget(f); l.addStretch()
    def save_automation(self):
        self.editable(); n=int(self.interval.text())
        if n<5:raise ValueError('Minst 5 minutter.')
        self.p.update(auto_update=self.auto.isChecked(),update_minutes=n); self.manager.save(); self.deadlines.pop(self.p['id'],None); self.events.put('Automatisering lagret.')
    def settings_page(self):
        l=self.page(); scroll=QScrollArea(); scroll.setWidgetResizable(True); content=QWidget(); form=QFormLayout(content); form.setSpacing(15); self.fields={}
        for key,title in [('name','Profilnavn'),('root','DayZ-servermappe'),('steamcmd','SteamCMD-program'),('steam_user','Steam-brukernavn'),('workshop','Workshop content/221100'),('config','Konfigurasjon, relativ sti'),('profiles','Profiles, relativ sti'),('port','Spillport'),('map_size','Kartstørrelse i meter')]:
            row=QWidget(); r=QHBoxLayout(row); r.setContentsMargins(0,0,0,0); v=QLineEdit(); self.fields[key]=v; r.addWidget(v)
            if key in ['root','steamcmd','workshop']:r.addWidget(button('Velg …',lambda checked=False,k=key:self.browse(k)))
            form.addRow(title,row)
        self.firewall_auto=QCheckBox('Opprett Windows-brannmurregler automatisk ved serverstart'); form.addRow('',self.firewall_auto)
        self.local_test=QCheckBox('Lokal test – start uten krav om Steam Query');form.addRow('',self.local_test)
        form.addRow('',label('Hopper over krav om query-port og query-overvåking. Koble direkte til spillporten. Dette sperrer ikke nettverkstilgang.','muted'))
        form.addRow('',button('Lagre serveroppsett',self.action(self.save_settings),'primary')); scroll.setWidget(content); l.addWidget(scroll,1)
        l.addWidget(label('Steam-passord lagres ikke av panelet. Lokal test påvirker bare krav og overvåking av Steam Query.','muted'))
    def browse(self,k):
        p=QFileDialog.getOpenFileName(self,'Velg SteamCMD','','Program (*.exe)')[0] if k=='steamcmd' else QFileDialog.getExistingDirectory(self,'Velg mappe')
        if p:self.fields[k].setText(p)
    def save_settings(self):
        self.editable(); candidate=dict(self.p)
        for k,v in self.fields.items():candidate[k]=v.text().strip()
        for k in ['port','map_size']:candidate[k]=int(candidate[k])
        candidate['auto_firewall']=self.firewall_auto.isChecked();candidate['query_enabled']=not self.local_test.isChecked()
        validate(candidate); self.p.update(candidate); self.manager.save(); self.load(); self.events.put('Serveroppsett lagret.')
    def load(self):
        self.selector.blockSignals(True); self.selector.clear(); self.selector.addItems([p['name'] for p in self.manager.state['servers']]); self.selector.setCurrentIndex(self.manager.state['servers'].index(self.p)); self.selector.blockSignals(False)
        for k,v in self.fields.items():v.setText(str(self.p[k]))
        self.firewall_auto.setChecked(self.p.get('auto_firewall',True));self.local_test.setChecked(not self.p.get('query_enabled',True))
        self.auto.setChecked(self.p['auto_update']); self.interval.setText(str(self.p['update_minutes'])); self.server_title.setText(self.p['name']); self.refresh_mods(); self.refresh_map(); self.guard(self.read_config); self.refresh_backups(); self.tick()
    def select(self,i):
        if i<0:return
        self.p=self.manager.state['servers'][i]; self.load()
    def new_server(self):self.p=self.manager.add(); self.load(); self.go(7)
    def stop(self):
        if QMessageBox.question(self,'Tvungen stopp','Dette kan miste ulagrede spilldata. Bruk DayZ sin graceful shutdown når mulig. Terminere prosessen?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.guard(lambda:self.manager.force_stop(self.p))
    def show_launch_log(self):
        record=self.manager.launches.get(self.p['id'])
        if not record:raise ValueError('Start serveren først for å finne logg fra akkurat denne oppstarten.')
        paths=current_logs(record)
        if not paths:raise ValueError('Ingen ny RPT/feillogg fra denne oppstarten ennå. Se det separate servervinduet eller åpne loggmappen: '+record['profiles'])
        path=next((p for p in paths if p.suffix.lower()=='.rpt'),paths[0]); self.log_path.setText(str(path)); self.log_signature=None; self.go(3)
    def tick(self):
        exits=self.manager.poll_processes()
        for event in exits:
            if event['profile_id']==self.p['id'] and event['logs']:
                self.log_path.setText(next((p for p in event['logs'] if p.lower().endswith('.rpt')),event['logs'][0])); self.log_signature=None
        while not self.events.empty():self.activity.appendPlainText(time.strftime('%H:%M:%S')+'   '+self.events.get())
        record=self.manager.launches.get(self.p['id']); self.launch_detail.setText(describe(record)+'\n'+record['exe'] if record else 'Ingen serveroppstart er registrert i denne økten.')
        running=self.manager.running(self.p); busy=self.p['id'] in self.manager.busy; self.server_status.setText('◌  JOBB PÅGÅR' if busy else '●  PROSESS KJØRER' if running else '○  STOPPET / IKKE ADMINISTRERT')
        self.start_btn.setEnabled(not running and not busy); self.stop_btn.setEnabled(running)
        for w,t in zip(self.metrics,[str(sum(m['enabled'] for m in self.p['mods'])),str(len(self.p['markers'])),str(self.p['port']),'—']):w.setText(t)
        self.all_servers.setRowCount(len(self.manager.state['servers']))
        for row,p in enumerate(self.manager.state['servers']):
            status='Jobb pågår' if p['id'] in self.manager.busy else 'Prosess kjører' if self.manager.running(p) else 'Stoppet'
            query='Ikke satt'
            try:
                from windows_firewall import mask_config
                import re
                text=mask_config(local_path(p['root'],p['config']).read_text('utf-8-sig')); values=re.findall(r'\bsteamQueryPort\s*=\s*(\d+)\s*;',text,re.I)
                if len(values)==1:query=values[0]
                if not p.get('query_enabled',True):query='Lokal test / ingen sjekk'
            except (OSError,ValueError):pass
            for col,value in enumerate([p['name'],status,str(p['port']),query,p['root']]):self.all_servers.setItem(row,col,QTableWidgetItem(value))
        for p in self.manager.state['servers']:
            if p['auto_update'] and not getattr(self,'operations_ready',False):
                due=self.deadlines.setdefault(p['id'],time.monotonic()+p['update_minutes']*60)
                if time.monotonic()>=due:
                    self.deadlines[p['id']]=time.monotonic()+p['update_minutes']*60
                    if not self.manager.running(p) and p['id'] not in self.manager.busy:
                        try:self.update_server(p)
                        except Exception as e:self.events.put(str(e))
            else:self.deadlines.pop(p['id'],None)
        path=Path(self.log_path.text())
        try:
            if path.is_file():
                st=path.stat(); sig=(str(path),st.st_size,st.st_mtime_ns)
                if sig!=self.log_signature:
                    with path.open('rb') as f:f.seek(max(0,st.st_size-100000)); text=f.read().decode('utf-8',errors='replace')
                    self.log_text.setPlainText(text); self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum()); self.log_signature=sig
        except OSError:pass
    def closeEvent(self,event):
        if self.manager.busy:QMessageBox.information(self,'Jobb pågår','Vent til oppdatering eller backup er ferdig.'); event.ignore(); return
        if any(self.manager.running(p) for p in self.manager.state['servers']):
            if QMessageBox.question(self,'Avslutte panelet?','Serverprosessene fortsetter. Panelet kobler seg til bekreftede serverprosesser igjen ved neste oppstart. Automatisering krever at panelet kjører. Avslutte?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:event.ignore(); return
        from process_registry import save_processes
        save_processes(self.manager); self.manager.save(); event.accept()

if __name__=='__main__':
    app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(STYLE); window=Studio(); window.show(); sys.exit(app.exec())
