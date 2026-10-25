"""Visual configuration tree + full types table backed by real server files."""
import json,re
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QLineEdit,QPushButton,QTabWidget,QPlainTextEdit,QTreeWidget,QTreeWidgetItem,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QFileDialog,QMessageBox,QInputDialog,QDialog,QStyledItemDelegate,QMenu)
from desktop import button,label
from config_documents import Document,catalog,parse_xml,xml_text,cfg_fields,cfg_set,BOOL_NAMES,SCHEMA,TYPE_COLUMNS,type_rows,edit_type,merge_types


class ValueDelegate(QStyledItemDelegate):
    def createEditor(self,parent,option,index):
        kind=index.data(Qt.UserRole)
        if kind=='password':
            editor=QLineEdit(parent);editor.setEchoMode(QLineEdit.Password);return editor
        if kind in ('category','usage','value','tag'):
            editor=QComboBox(parent);editor.setEditable(True);editor.addItems({'category':['weapons','tools','containers','clothes','food','explosives','books'],'usage':['Military','Police','Medic','Firefighter','Industrial','Farm','Coast','Town','Village','Hunting'],'value':['Tier1','Tier2','Tier3','Tier4'],'tag':['floor','shelves','ground']}[kind]);return editor
        return super().createEditor(parent,option,index)
    def setEditorData(self,editor,index):
        if isinstance(editor,QComboBox):editor.setCurrentText(index.data() or '')
        elif isinstance(editor,QLineEdit) and index.data(Qt.UserRole)=='password':editor.setText('')
        else:super().setEditorData(editor,index)
    def setModelData(self,editor,model,index):
        if isinstance(editor,QComboBox):model.setData(index,editor.currentText())
        elif isinstance(editor,QLineEdit) and index.data(Qt.UserRole)=='password':
            if editor.text():model.setData(index,editor.text())
        else:super().setModelData(editor,model,index)


class ConfigCenter(QWidget):
    def __init__(self,studio):
        super().__init__();self.studio=studio;self.doc=None;self.loading=False;self.bindings={};self.json_data=None;self.xml=None;self.undo_stack=[];self.redo_stack=[];self.xml_nodes_map={}
        layout=QVBoxLayout(self);row=QHBoxLayout();self.files=QComboBox();self.files.setMinimumWidth(300);row.addWidget(self.files,1);row.addWidget(button('Finn serverfiler',self.discover));row.addWidget(button('Åpne',lambda:self.safe(self.open_selected)));row.addWidget(button('Historikk',lambda:self.safe(self.history)));row.addWidget(button('Kontroller og lagre',lambda:self.safe(self.save),'primary'));layout.addLayout(row)
        self.info=label('Velg en serverfil. Endringer gjelder først etter lagring.','muted');layout.addWidget(self.info)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        structured=QWidget();sl=QVBoxLayout(structured);sr=QHBoxLayout();self.filter=QLineEdit();self.filter.setPlaceholderText('Filtrer innstillinger …');sr.addWidget(self.filter);sr.addWidget(button('Angre',lambda:self.safe(self.undo)));sr.addWidget(button('Gjør om',lambda:self.safe(self.redo)));sr.addWidget(button('+ CFG-innstilling',lambda:self.safe(self.add_cfg)));sl.addLayout(sr)
        self.tree=QTreeWidget();self.tree.setHeaderLabels(['Innstilling / struktur','Verdi']);self.tree.setStyleSheet('QTreeView::item { height: 28px; }');self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents);sl.addWidget(self.tree);self.tabs.addTab(structured,'Visuell editor')
        tw=QWidget();tl=QVBoxLayout(tw);tr=QHBoxLayout();self.type_filter=QLineEdit();self.type_filter.setPlaceholderText('Søk klasse, kategori, tier eller usage …');tr.addWidget(self.type_filter);tr.addWidget(button('Importer types',lambda:self.safe(self.import_types)));tr.addWidget(button('Masseendre',lambda:self.safe(self.bulk)));tl.addLayout(tr)
        self.types=QTableWidget(0,len(TYPE_COLUMNS));self.types.setHorizontalHeaderLabels(TYPE_COLUMNS);self.types.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive);self.types.setSelectionBehavior(QAbstractItemView.SelectRows);self.types.setSelectionMode(QAbstractItemView.ExtendedSelection);tl.addWidget(self.types);tl.addWidget(label('Flagg, attachments og ukjente felt redigeres i Visuell editor. Semikolon skiller flere usage/value/tag-navn.','muted'));self.tabs.addTab(tw,'Types / loot')
        self.raw=QPlainTextEdit();self.tabs.addTab(self.raw,'Rå tekst');self.diff=QPlainTextEdit();self.diff.setReadOnly(True);self.tabs.addTab(self.diff,'Endringer')
        self.raw.textChanged.connect(self.raw_changed);self.tree.setItemDelegate(ValueDelegate(self.tree));self.types.setItemDelegate(ValueDelegate(self.types));self.tree.setContextMenuPolicy(Qt.CustomContextMenu);self.tree.customContextMenuRequested.connect(self.xml_menu);self.tree.itemChanged.connect(self.tree_changed);self.types.cellChanged.connect(self.type_changed);self.tabs.currentChanged.connect(self.tab_changed);self.filter.textChanged.connect(self.filter_tree);self.type_filter.textChanged.connect(self.filter_types)
    def safe(self,fn):return self.studio.guard(fn)
    def discover(self):
        def work():
            current=self.files.currentText();self.files.clear();self.files.addItems(catalog(self.studio.p));self.files.setCurrentText(current)
        self.safe(work)
    def sync(self):
        if self.doc:self.doc.text=self.raw.toPlainText()
    def open_selected(self):
        self.sync()
        if self.doc and self.doc.dirty and QMessageBox.question(self,'Ulagret fil','Forkaste ulagrede endringer?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        self.open_path(self.files.currentText())
    def open_path(self,relative):
        if not relative:raise ValueError('Velg en konfigurasjonsfil først.')
        self.doc=Document(self.studio.p,relative,self.studio.manager.home);self.undo_stack=[];self.redo_stack=[];self.loading=True;self.raw.setPlainText(self.doc.text);self.loading=False;self.rebuild()
        self.info.setText(self.studio.p['name']+' • '+relative+' • Lagres med backup. Krever normalt restart.')
    def raw_changed(self):
        if not self.loading:self.sync()
    def set_text(self,text):
        if self.doc and text!=self.raw.toPlainText():self.undo_stack.append(self.raw.toPlainText());self.redo_stack=[]
        self.loading=True;self.raw.setPlainText(text);self.loading=False;self.sync()
    def tab_changed(self,index):
        if self.doc:self.safe(self.rebuild)
    def rebuild(self):
        if not self.doc:return
        self.sync();self.loading=True;self.tree.clear();self.bindings={};self.xml_nodes_map={};self.types.setRowCount(0);self.diff.setPlainText(self.doc.diff())
        try:
            if self.doc.suffix=='.json':
                self.json_data=json.loads(self.doc.text);self.json_nodes(self.tree.invisibleRootItem(),self.json_data,[])
            elif self.doc.suffix=='.xml':
                self.xml=parse_xml(self.doc.text);self.xml_nodes(self.tree.invisibleRootItem(),self.xml)
                if self.xml.tag=='types':
                    rows=type_rows(self.doc.text);self.types.setRowCount(len(rows))
                    for i,row in enumerate(rows):
                        for j,key in enumerate(TYPE_COLUMNS):
                            item=QTableWidgetItem(row.get(key,''));item.setData(Qt.UserRole,key);self.types.setItem(i,j,item)
            elif self.doc.suffix=='.cfg':
                for i,field in enumerate(cfg_fields(self.doc.text)):
                    raw=field['value'];value=raw
                    if field['kind'] in ('string','password') and field.get('style')!='line':
                        try:value=json.loads(raw)
                        except ValueError:pass
                    self.leaf(self.tree.invisibleRootItem(),field['key']+' — '+field['label'],value,('cfg',i,('line:' if field.get('style')=='line' else '')+field['kind']),field['kind']=='bool',field['kind']=='password')
            else:self.leaf(self.tree.invisibleRootItem(),'Tekstfil','Bruk fanen Rå tekst',None)
            self.tree.expandToDepth(1)
        finally:self.loading=False
        self.filter_tree();self.filter_types()
    def leaf(self,parent,name,value,binding=None,boolean=False,password=False):
        item=QTreeWidgetItem(parent,[str(name),'••••••••' if password and value else 'null' if value is None else str(value)])
        if password:item.setData(1,Qt.UserRole,'password')
        if binding:
            self.bindings[id(item)]=binding
            item.setFlags((item.flags()|Qt.ItemIsEditable)&~Qt.ItemIsUserCheckable)
            if boolean:
                item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(1,Qt.Checked if value in (True,1,'1','true') else Qt.Unchecked);item.setText(1,'')
            if password:item.setToolTip(1,'Dobbeltklikk og skriv nytt passord. Behold maskeringen for uendret verdi.')
        return item
    def json_nodes(self,parent,value,path):
        if isinstance(value,(dict,list)):
            for key,child in (value.items() if isinstance(value,dict) else enumerate(value)):
                if isinstance(child,(dict,list)):
                    node=self.leaf(parent,str(key),'Objekt' if isinstance(child,dict) else 'Liste');self.json_nodes(node,child,path+[key])
                else:self.leaf(parent,key,child,('json',path+[key],type(child).__name__),isinstance(child,bool),'password' in str(key).lower() or 'token' in str(key).lower())
        else:self.leaf(parent,'Verdi',value,('json',[],type(value).__name__),isinstance(value,bool))
    def xml_nodes(self,parent,node):
        if not isinstance(node.tag,str):return
        item=self.leaf(parent,node.tag+(' ['+node.get('name','')+']' if node.get('name') else ''),'')
        self.xml_nodes_map[id(item)]=node
        for key,value in node.attrib.items():self.leaf(item,'@'+key,value,('xml_attr',node,key),key.casefold() in BOOL_NAMES)
        if not len(node) or (node.text or '').strip():self.leaf(item,'Tekst',(node.text or '').strip(),('xml_text',node,None),node.tag.casefold() in BOOL_NAMES)
        for child in node:self.xml_nodes(item,child)
    def tree_changed(self,item,column):
        if self.loading or column!=1:return
        binding=self.bindings.get(id(item))
        if not binding:return
        def work():
            kind,target,field=binding;value=item.text(1)
            if value=='••••••••':return
            boolean=bool(item.flags()&Qt.ItemIsUserCheckable)
            if boolean:value=item.checkState(1)==Qt.Checked
            if kind=='cfg':
                value=('1' if value else '0') if boolean else json.dumps(value,ensure_ascii=False) if field in ('string','password') else value
                self.set_text(cfg_set(self.doc.text,target,value))
            elif kind.startswith('xml'):
                value=('1' if value else '0') if boolean else value
                if kind=='xml_attr':target.set(field,value)
                else:target.text=value
                self.set_text(xml_text(self.xml))
            else:
                value=value if boolean else int(value) if field=='int' else float(value) if field=='float' else None if field=='NoneType' and value=='null' else value
                data=self.json_data
                if target:
                    for key in target[:-1]:data=data[key]
                    data[target[-1]]=value
                else:self.json_data=value
                self.set_text(json.dumps(self.json_data,indent=2,ensure_ascii=False)+'\n')
        self.safe(work)
    def type_changed(self,row,col):
        if self.loading or not self.doc:return
        self.safe(lambda:self.set_text(edit_type(self.doc.text,row,TYPE_COLUMNS[col],self.types.item(row,col).text())))
    def filter_tree(self):
        needle=self.filter.text().casefold()
        def visit(item):
            own=needle in (item.text(0)+' '+item.text(1)).casefold();children=[visit(item.child(i)) for i in range(item.childCount())];visible=own or any(children);item.setHidden(not visible);return visible
        for i in range(self.tree.topLevelItemCount()):visit(self.tree.topLevelItem(i))
    def filter_types(self):
        needle=self.type_filter.text().casefold()
        for row in range(self.types.rowCount()):self.types.setRowHidden(row,not any(needle in (self.types.item(row,col).text() if self.types.item(row,col) else '').casefold() for col in range(self.types.columnCount())))
    def undo(self):
        if not self.undo_stack:return
        previous=self.undo_stack.pop();self.redo_stack.append(self.raw.toPlainText());self.loading=True;self.raw.setPlainText(previous);self.loading=False;self.sync();self.rebuild()
    def redo(self):
        if not self.redo_stack:return
        text=self.redo_stack.pop();self.undo_stack.append(self.raw.toPlainText());self.loading=True;self.raw.setPlainText(text);self.loading=False;self.sync();self.rebuild()
    def xml_menu(self,pos):
        item=self.tree.itemAt(pos);node=self.xml_nodes_map.get(id(item))
        if node is None:return
        menu=QMenu(self);add=menu.addAction('Nytt barneelement');attribute=menu.addAction('Nytt attributt');duplicate=menu.addAction('Dupliser element');remove=menu.addAction('Slett element');choice=menu.exec(self.tree.viewport().mapToGlobal(pos))
        def work():
            import copy,xml.etree.ElementTree as ET
            parent=next((p for p in self.xml.iter() if node in list(p)),None)
            if choice in (add,attribute):
                name,ok=QInputDialog.getText(self,'Nytt XML-felt','Navn:')
                if not ok:return
                if not re.fullmatch(r'[A-Za-z_][\w.-]*',name):raise ValueError('Ugyldig XML-navn.')
                value,ok=QInputDialog.getText(self,'Verdi','Verdi (kan være tom):')
                if not ok:return
                if choice==attribute:node.set(name,value)
                else:ET.SubElement(node,name).text=value
            elif choice==duplicate:
                if parent is None:raise ValueError('Rotnoden kan ikke dupliseres.')
                parent.append(copy.deepcopy(node))
            elif choice==remove:
                if parent is None:raise ValueError('Rotnoden kan ikke slettes.')
                parent.remove(node)
            else:return
            self.set_text(xml_text(self.xml));self.rebuild()
        self.safe(work)
    def add_cfg(self):
        if not self.doc or self.doc.suffix!='.cfg':raise ValueError('Åpne en CFG-fil først.')
        key,ok=QInputDialog.getItem(self,'Ny innstilling','Innstilling:',list(SCHEMA),0,True)
        if not ok:return
        if not re.fullmatch(r'[A-Za-z_]\w*',key):raise ValueError('Ugyldig innstillingsnavn.')
        if any(f['key']==key for f in cfg_fields(self.doc.text)):raise ValueError('Innstillingen finnes allerede.')
        kind=SCHEMA.get(key,('', 'raw'))[1];value='""' if kind in ('string','password') else '0';self.set_text(key+' = '+value+';\n'+self.doc.text);self.rebuild()
    def import_types(self):
        if not self.doc or self.doc.suffix!='.xml':raise ValueError('Åpne types-filen først.')
        path,_=QFileDialog.getOpenFileName(self,'Importer types','','XML (*.xml)')
        if not path:return
        if Path(path).stat().st_size>8*1024**2:raise ValueError('Importfilen er for stor.')
        replace=QMessageBox.question(self,'Eksisterende klasser','Erstatte eksisterende klasser med samme navn? Nei beholder dem.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes
        text,added,skipped=merge_types(self.doc.text,Path(path).read_text('utf-8-sig'),replace);self.set_text(text);self.rebuild();self.info.setText(f'{added} importert • {skipped} beholdt. Kontroller Endringer før lagring.')
    def bulk(self):
        if not self.doc:raise ValueError('Åpne en types-fil først.')
        rows=sorted({index.row() for index in self.types.selectedIndexes()})
        if not rows:raise ValueError('Velg radene du vil endre.')
        key,ok=QInputDialog.getItem(self,'Masseendring','Felt:',TYPE_COLUMNS[1:8],0,False)
        if not ok:return
        factor,ok=QInputDialog.getDouble(self,'Masseendring','Multiplikator (1,2 = +20 %):',1.2,0,100,3)
        if not ok:return
        text=self.doc.text;values=type_rows(text)
        for row in rows:
            old=values[row][key]
            if old and int(old)>=0:text=edit_type(text,row,key,str(round(int(old)*factor)))
        self.set_text(text);self.rebuild()
    def save(self):
        if not self.doc:raise ValueError('Åpne en fil først.')
        self.sync();self.studio.editable_profile(self.doc.profile);warnings=self.doc.warnings()
        if not self.doc.dirty:return
        dialog=QDialog(self);dialog.setWindowTitle('Kontroller endringer – '+self.doc.relative);dialog.resize(1000,700);layout=QVBoxLayout(dialog)
        if warnings:layout.addWidget(label('\n'.join(warnings[:20]),'muted'))
        view=QPlainTextEdit(self.doc.diff());view.setReadOnly(True);layout.addWidget(view);row=QHBoxLayout();row.addWidget(button('Avbryt',dialog.reject));row.addWidget(button('Lagre med backup',dialog.accept,'primary'));layout.addLayout(row)
        if dialog.exec()!=QDialog.Accepted:return
        if hasattr(self.studio.manager,'save_document'):self.studio.manager.save_document(self.doc)
        else:self.doc.save()
        self.studio.events.put('Konfigurasjon lagret med backup: '+self.doc.relative);self.rebuild()
    def history(self):
        if not self.doc:raise ValueError('Åpne en fil først.')
        files=sorted([p.name for p in self.doc.history_dir.glob('*') if p.name!='source.json'],reverse=True)
        if not files:raise ValueError('Ingen lagret historikk for denne filen.')
        name,ok=QInputDialog.getItem(self,'Gjenopprett til editor','Velg versjon. Ingenting skrives før du lagrer.',files,0,False)
        if ok:self.doc.restore(self.doc.history_dir/name);self.set_text(self.doc.text);self.rebuild()
