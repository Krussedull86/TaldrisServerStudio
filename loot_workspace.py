"""Embedded DZSA Loot Editor with a bounded QWebChannel desktop bridge."""
import copy,json,shutil,sys,time
from pathlib import Path
from PySide6.QtCore import QObject,Slot,QUrl,QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFileDialog,QMessageBox,QInputDialog,QLabel,QApplication
from desktop import button,label
from loot_engine import LootStore,parse_types,atomic
from config_documents import Document,digest,MAX_BYTES
from mission_loot import active_types
MAPS=[dict(id=k,name=n,mission=m) for k,n,m in [('chernarus','Chernarus','chernarusplus'),('livonia','Livonia','enoch'),('sakhal','Sakhal','sakhal'),('nasdara','Nasdara','nasdara')]]

def resources():return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))

class LootBridge(QObject):
    def __init__(self,workspace):super().__init__(workspace);self.workspace=workspace
    @Slot(str,str,result=str)
    def call(self,action,payload):
        try:
            if len(payload)>12*1024*1024:raise ValueError('Editor request is too large.')
            result=self.workspace.call(action,json.loads(payload))
            return json.dumps(result,ensure_ascii=False)
        except Exception as error:return json.dumps({'error':str(error)})

class LootWorkspace(QWidget):
    def __init__(self,studio):
        super().__init__();self.studio=studio;self.store=LootStore(studio.manager.home);self.dirty=False;self.view=None;self.doc=None;layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);row=QHBoxLayout();row.addWidget(button('Read active mission …',lambda:studio.guard(self.open_mission),'primary'));row.addWidget(button('Import types.xml …',lambda:studio.guard(self.open_xml)));row.addWidget(button('Save to mission …',lambda:studio.guard(self.request_mission_save)));row.addStretch();layout.addLayout(row);self.target=label('','muted');self.target.setWordWrap(True);layout.addWidget(self.target);self.placeholder=label('DZSA Loot Editor • CruzDoodelz & NoSignal\nOpen this page to load the integrated editor. Original DZSA Tools by NIXON.','muted');layout.addWidget(self.placeholder);self.restore_target();self.update_target()
    def showEvent(self,event):
        super().showEvent(event)
        if self.view is None:QTimer.singleShot(0,lambda:self.studio.guard(self.ensure_view))
    def ensure_view(self):
        if self.view is not None:return
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile,QWebEngineSettings,QWebEngineUrlRequestInterceptor
        from PySide6.QtWebChannel import QWebChannel
        root=(resources()/'loot_web').resolve();entry=QUrl.fromLocalFile(str(root/'index.html'))
        class LocalOnly(QWebEngineUrlRequestInterceptor):
            def interceptRequest(self,request):
                url=request.requestUrl();allowed=url.scheme()=='qrc' or (url.isLocalFile() and Path(url.toLocalFile()).resolve().is_relative_to(root));request.block(not allowed)
        class Page(QWebEnginePage):
            def acceptNavigationRequest(self,url,kind,main):return url==entry
            def javaScriptConsoleMessage(self,level,message,line,source):
                if level==QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:self.parent().studio.events.put('Loot editor: '+message)
        self.web_profile=QWebEngineProfile('CruzDoodelZLoot',self);self.web_profile.setPersistentStoragePath(str(Path(self.studio.manager.home)/'loot_browser'));self.web_profile.setCachePath(str(Path(self.studio.manager.home)/'loot_browser/cache'));self.interceptor=LocalOnly(self.web_profile);self.web_profile.setUrlRequestInterceptor(self.interceptor);self.view=QWebEngineView(self);self.web_page=Page(self.web_profile,self);self.view.setPage(self.web_page);self.web_page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,False);self.channel=QWebChannel(self.web_page);self.bridge=LootBridge(self);self.channel.registerObject('studio',self.bridge);self.web_page.setWebChannel(self.channel);self.layout().removeWidget(self.placeholder);self.placeholder.hide();self.layout().addWidget(self.view,1);self.view.setUrl(entry);QApplication.instance().aboutToQuit.connect(self.dispose)
    def dispose(self):
        if self.view is None:return
        import shiboken6
        self.view.stop();shiboken6.delete(self.web_page);shiboken6.delete(self.view);self.view=None;shiboken6.delete(self.web_profile)
    def update_target(self):
        target=(self.store.active or {}).get('target');selected=self.studio.p['name']
        if target:self.target.setText('Selected server: '+selected+' | Open project target: '+target['server_name']+' / '+target['relative']+' | Save project ≠ Save to mission. Mission changes normally take effect after server restart.')
        else:self.target.setText('Selected server: '+selected+' | Detached project. Import/export does not change server files. Use Read active mission for direct editing.')
    def restore_target(self):
        self.doc=None;target=(self.store.active or {}).get('target')
        if not target:return
        p=next((p for p in self.studio.manager.state['servers'] if p['id']==target['server_id']),None)
        if p:
            try:
                doc=Document(p,target['relative'],self.studio.manager.home)
                if digest(doc.original)==target['base']:self.doc=doc
            except (OSError,ValueError):pass
    def discard(self):
        if not self.dirty:return True
        return QMessageBox.question(self,'Unsaved loot edits','Discard unsaved table changes? Save project changes first if you want to keep them.',QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Cancel)==QMessageBox.Discard
    def reload(self):
        self.dirty=False;self.update_target()
        if self.view:self.view.reload()
    def open_xml(self):
        if not self.discard():return False
        path,_=QFileDialog.getOpenFileName(self,'Import DayZ types XML','','Types XML (*.xml)')
        if not path:return False
        p=Path(path)
        if p.stat().st_size>MAX_BYTES:raise ValueError('XML exceeds 8 MB.')
        self.store.create(p.read_text('utf-8-sig'),p.name);self.doc=None;self.reload();return True
    def open_mission(self):
        if not self.discard():return False
        p=self.studio.p;found=active_types(p)
        if not found['files']:raise ValueError('No types.xml or CE type files found in '+found['folder'])
        relative=found['files'][0]
        if len(found['files'])>1:
            relative,ok=QInputDialog.getItem(self,'Active mission • '+found['mission'],'Choose the CE types file',found['files'],0,False)
            if not ok:return False
        doc=Document(p,relative,self.studio.manager.home);target=dict(server_id=p['id'],server_name=p['name'],root=str(Path(p['root']).resolve()),config=p['config'],relative=relative,base=digest(doc.original),mission=found['mission']);self.store.create(doc.text,p['name']+' • '+Path(relative).name,target);self.doc=doc;self.reload();return True
    def request_mission_save(self):
        if not self.view:raise ValueError('Open the loot editor first.')
        self.view.page().runJavaScript('window.studioSaveMission && window.studioSaveMission()')
    def save_mission(self):
        pmeta=self.store.active;target=(pmeta or {}).get('target')
        if not target:raise ValueError('This is a detached project. Choose Read active mission first.')
        p=next((p for p in self.studio.manager.state['servers'] if p['id']==target['server_id']),None)
        if p is None:raise ValueError('The target server profile has been removed.')
        if str(Path(p['root']).resolve())!=target.get('root') or p['config']!=target.get('config'):raise ValueError('The target server root or CFG changed. Open the active mission again.')
        # Bind to disk CFG and original digest even after panel restarts/profile switches.
        found=active_types(p)
        if found['mission']!=target['mission'] or target['relative'] not in found['files']:raise ValueError('The active mission or CE files changed. Open the active mission again.')
        doc=Document(p,target['relative'],self.studio.manager.home)
        if digest(doc.original)!=target['base']:raise ValueError('The mission file changed on disk. Reopen it and compare before saving.')
        from mission_settings import check_config_edit
        check_config_edit(self.studio.manager,p,doc.relative);doc.text=self.store.xml()
        if QMessageBox.question(self,'Save to mission','Write edited loot to '+p['name']+'?\n'+str(doc.path)+'\n\nA backup is kept. The server must be stopped.',QMessageBox.Save|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Save:return False
        if getattr(self.studio.manager,'remote',False):self.studio.manager.save_document(doc)
        else:doc.save()
        self.store.commit(dict(pmeta,target=dict(target,base=digest(doc.text))));self.doc=doc;self.studio.events.put('Loot saved to mission: '+str(doc.path));self.update_target();return {'data':'Saved to mission with backup'}
    def call(self,action,payload):
        from release_info import VERSION
        if action=='state':return dict(self.store.state(),appVersion=VERSION,maps=MAPS,buildChannel='dev')
        if action=='dirty':self.dirty=True;return True
        if action=='save':
            result=self.store.save(payload);self.dirty=False;return result
        if action in ('undo','redo'):
            if not self.discard():return {'error':'Save or discard table changes first.'}
            self.dirty=False;return self.store.step(-1 if action=='undo' else 1)
        if action=='list':
            if payload=='versions':return [dict(self.store.active,rev=rev) for rev in reversed((self.store.active or {}).get('revisions',[]))]
            return self.store.list()
        if action=='open':return self.open_xml()
        if action=='mission_save':return self.save_mission()
        if action=='export':
            payload=payload or {};text=self.store.xml(payload.get('id'),payload.get('rev'));path,_=QFileDialog.getSaveFileName(self,'Export edited XML','types_edited.xml','XML (*.xml)')
            if path:
                dest=Path(path).resolve()
                # Server-root exports use the guarded mission writer instead.
                for p in self.studio.manager.state['servers']:
                    if p.get('root') and dest.is_relative_to(Path(p['root']).resolve()):raise ValueError('Use Save to mission for server files. Export to a separate folder.')
                atomic(dest,text);return {'path':path}
            return False
        if action=='validate':
            rows=parse_types(self.store.xml());return {'data':str(len(rows))+' items checked (syntax, duplicate names, numeric fields and flags).'}
        if action=='load':
            if not self.discard():return False
            self.store.load(payload['id'],int(payload['rev']));self.restore_target();self.reload();return True
        if action=='map':
            m=next((m for m in MAPS if m['id']==payload),None)
            if not m:raise ValueError('Unknown map.')
            if not self.discard():return False
            path=resources()/'loot_maps'/('dayzOffline.'+m['mission'])/'db/types.xml';self.store.create(path.read_text('utf-8-sig'),m['name']);self.doc=None;self.reload();return True
        if action in ('delete','deleteRevision'):
            if not self.discard():return False
            p=self.store.meta(payload['id']);rev=int(payload['rev'])
            if action=='deleteRevision' and (rev not in p['revisions'] or len(p['revisions'])<2):raise ValueError('Keep at least one saved revision.')
            if QMessageBox.question(self,'Saved loot project','Remove this saved project/revision? Original server files are preserved.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return False
            if action=='delete':
                trash=self.store.base/'removed';trash.mkdir(exist_ok=True);self.store.folder(p['id']).rename(trash/(p['id']+'-'+str(time.time_ns())))
                if self.store.active and self.store.active['id']==p['id']:self.store.active=None;(self.store.base/'active.json').unlink(missing_ok=True)
            else:
                (self.store.folder(p['id'])/f'revision-{rev}.json').unlink();p['revisions'].remove(rev)
                if p['rev']==rev:p['rev']=p['revisions'][-1]
                atomic(self.store.folder(p['id'])/'project.json',json.dumps(p))
                if self.store.active and self.store.active['id']==p['id']:self.store.commit(p)
            self.restore_target();self.reload();return True
        raise ValueError('Unsupported editor action: '+str(action))
