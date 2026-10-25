"""Editable XML coordinate layers on each server's calibrated map image."""
from pathlib import Path
import copy,math
from PySide6.QtCore import Qt,QRectF,Signal
from PySide6.QtGui import QPixmap,QPen,QBrush,QColor,QPainter
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QCheckBox,QLineEdit,QGraphicsView,QGraphicsScene,QGraphicsEllipseItem,QGraphicsItem,QFileDialog,QMessageBox,QInputDialog)
from desktop import label,button
from config_documents import Document,parse_xml,xml_text,catalog

COLORS=['#62e5c3','#f4bf72','#9d9aff','#fa869c','#73caff']


def coordinates(root):
    result=[]
    def visit(node,path,parent):
        if not isinstance(node.tag,str):return
        attrs=node.attrib
        if 'x' in attrs and 'z' in attrs:
            try:
                x,z=float(attrs['x']),float(attrs['z'])
                if not math.isfinite(x+z):raise ValueError()
                result.append(dict(node=node,parent=parent,path=path,x=x,z=z,name=node.get('name') or path))
            except ValueError:pass
        for i,child in enumerate(node):visit(child,path+'/'+str(child.tag)+'['+str(i)+']'+(' '+child.get('name') if child.get('name') else ''),node)
    visit(root,root.tag,None);return result


class PointItem(QGraphicsEllipseItem):
    def __init__(self,workbench,layer,point,color):
        super().__init__(-5,-5,10,10);self.workbench=workbench;self.layer=layer;self.point=point;self.ready=False;self.radius_item=None;self.pending_drag=False
        self.setZValue(2);self.setBrush(QBrush(QColor(color)));self.setPen(QPen(QColor('#ffffff')));self.setFlags(QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemSendsGeometryChanges|QGraphicsItem.ItemIgnoresTransformations)
        self.setPos(*workbench.world_to_scene(point['x'],point['z']));self.setToolTip(point['name']+f"\nX {point['x']:.2f} / Z {point['z']:.2f}");self.ready=True
    def mousePressEvent(self,event):
        self.pending_drag=self.layer is self.workbench.active_layer()
        super().mousePressEvent(event)
    def itemChange(self,change,value):
        if change==QGraphicsItem.ItemPositionChange and self.ready:
            if self.layer is not self.workbench.active_layer():return self.pos()
            return type(value)(max(0,min(1000,value.x())),max(0,min(1000,value.y())))
        if change==QGraphicsItem.ItemPositionHasChanged and self.ready:
            if self.pending_drag:self.workbench.checkpoint(self.layer);self.pending_drag=False
            x,z=self.workbench.scene_to_world(self.pos().x(),self.pos().y());self.point['node'].set('x',f'{x:.3f}');self.point['node'].set('z',f'{z:.3f}');self.point.update(x=x,z=z)
            if self.radius_item:self.radius_item.setPos(self.pos())
            self.setToolTip(self.point['name']+f'\nX {x:.2f} / Z {z:.2f}')
            self.workbench.update_document(self.layer);self.workbench.status.setText(f'Endret X {x:.2f}, Z {z:.2f}. Ikke lagret ennå.')
        return super().itemChange(change,value)


class MapView(QGraphicsView):
    def __init__(self,workbench):
        super().__init__();self.workbench=workbench;self.setScene(QGraphicsScene(self));self.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform);self.setDragMode(QGraphicsView.ScrollHandDrag)
    def reset_view(self):self.workbench.fit()
    def wheelEvent(self,event):
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        if .1<self.transform().m11()*factor<100:self.scale(factor,factor)
    def mouseDoubleClickEvent(self,event):
        pos=self.mapToScene(event.position().toPoint());self.workbench.studio.guard(lambda:self.workbench.add_point(pos.x(),pos.y()))
    def mouseMoveEvent(self,event):
        pos=self.mapToScene(event.position().toPoint());x,z=self.workbench.scene_to_world(pos.x(),pos.y());self.workbench.cursor.setText(f'X {x:.1f} / Z {z:.1f}');super().mouseMoveEvent(event)


class MapWorkbench(QWidget):
    def __init__(self,studio):
        super().__init__();self.studio=studio;self.layers=[];self.server_id=None
        layout=QVBoxLayout(self);row=QHBoxLayout();row.addWidget(button('Kartbilde',lambda:studio.guard(self.choose_image)));row.addWidget(button('+ XML-lag',lambda:studio.guard(self.add_layer)));self.layer_choice=QComboBox();row.addWidget(self.layer_choice,1);row.addWidget(button('Vis/skjul lag',self.toggle_layer));row.addWidget(button('Tilpass kart',self.fit));layout.addLayout(row)
        row=QHBoxLayout();self.groups=QComboBox();row.addWidget(self.groups,1);row.addWidget(button('+ Punkt med koordinater',lambda:studio.guard(self.manual_point)));row.addWidget(button('Rediger valgt punkt',lambda:studio.guard(self.edit_point)));row.addWidget(button('Slett valgte punkter',lambda:studio.guard(self.remove_points)));row.addWidget(button('Kontroller og lagre lag',lambda:studio.guard(self.save_active),'primary'));layout.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('Angre',lambda:studio.guard(lambda:self.history_step(False))));row.addWidget(button('Gjør om',lambda:studio.guard(lambda:self.history_step(True))));row.addStretch();layout.addLayout(row)
        self.view=MapView(self);layout.addWidget(self.view,1);self.cursor=label('X / Z','eyebrow');layout.addWidget(self.cursor);self.status=label('Zoom med musehjul. Dra kartet for å flytte visningen. Dobbeltklikk for å legge til punkt i valgt gruppe. Dra et punkt for å flytte det.','muted');layout.addWidget(self.status)
        self.layer_choice.currentIndexChanged.connect(self.choose_layer)
    def world_to_scene(self,x,z):
        size=float(self.studio.p['map_size']);return x/size*1000,(1-z/size)*1000
    def scene_to_world(self,x,y):
        size=float(self.studio.p['map_size']);return x/1000*size,(1-y/1000)*size
    def active_layer(self):
        i=self.layer_choice.currentIndex();return self.layers[i] if 0<=i<len(self.layers) else None
    def reload_server(self):
        if self.server_id!=self.studio.p['id']:
            # Preserve unsaved edits per server while moving between profiles.
            if not hasattr(self,'cache'):self.cache={}
            if self.server_id:self.cache[self.server_id]=self.layers
            self.server_id=self.studio.p['id'];self.layers=self.cache.get(self.server_id,[]);self.layer_choice.blockSignals(True);self.layer_choice.clear();self.layer_choice.addItems([l['doc'].relative for l in self.layers]);self.layer_choice.blockSignals(False)
        self.render();self.choose_layer()
    def choose_image(self):
        path,_=QFileDialog.getOpenFileName(self,'Kartbilde for valgt server','','Bilder (*.png *.jpg *.jpeg *.webp)')
        if path:self.studio.p['map_image']=path;self.studio.manager.save();self.render()
    def add_layer(self):
        files=[name for name in catalog(self.studio.p) if name.endswith('.xml')]
        if not files:raise ValueError('Ingen XML-filer funnet i servermappen.')
        name,ok=QInputDialog.getItem(self,'Kartlag','Velg fil med X/Z-koordinater:',files,0,False)
        if not ok:return
        if any(layer['doc'].relative==name for layer in self.layers):raise ValueError('Dette laget er allerede lagt til.')
        doc=Document(self.studio.p,name,self.studio.manager.home);root=parse_xml(doc.text);points=coordinates(root)
        if not points:raise ValueError('Filen har ingen XML-elementer med x- og z-attributter. Åpne andre formater i konfigurasjonssenteret.')
        self.layers.append(dict(doc=doc,root=root,visible=True,color=COLORS[len(self.layers)%len(COLORS)]));self.layer_choice.addItem(name);self.layer_choice.setCurrentIndex(len(self.layers)-1);self.render();self.choose_layer()
    def choose_layer(self,*args):
        self.groups.clear();self.group_nodes=[];layer=self.active_layer()
        if not layer:return
        seen=set()
        for point in coordinates(layer['root']):
            parent=point['parent']
            if parent is not None and id(parent) not in seen:seen.add(id(parent));self.group_nodes.append(parent);self.groups.addItem(point['path'].rsplit('/',1)[0])
    def toggle_layer(self):
        layer=self.active_layer()
        if layer:layer['visible']=not layer['visible'];self.render()
    def render(self):
        scene=self.view.scene();scene.clear();pix=QPixmap(self.studio.p.get('map_image',''))
        if not pix.isNull():scene.addPixmap(pix.scaled(1000,1000,Qt.IgnoreAspectRatio,Qt.SmoothTransformation))
        else:
            scene.setBackgroundBrush(QColor('#12212b'))
            text=scene.addText('Velg kartbilde for '+self.studio.p['name']);text.setDefaultTextColor(QColor('#e2f4ff'));text.setPos(20,20)
        for step in range(0,1001,100):scene.addLine(step,0,step,1000,QPen(QColor(150,190,210,60)));scene.addLine(0,step,1000,step,QPen(QColor(150,190,210,60)))
        for layer in self.layers:
            if not layer['visible']:continue
            for point in coordinates(layer['root']):
                item=PointItem(self,layer,point,layer['color']);scene.addItem(item)
                radius=point['node'].get('r') or point['node'].get('radius')
                if radius:
                    try:
                        r=float(radius)/float(self.studio.p['map_size'])*1000
                        if r>0:
                            x,y=self.world_to_scene(point['x'],point['z']);item.radius_item=scene.addEllipse(-r,-r,2*r,2*r,QPen(QColor(layer['color'])));item.radius_item.setPos(x,y);item.radius_item.setZValue(1)
                    except ValueError:pass
        scene.setSceneRect(QRectF(-20,-20,1040,1040));self.fit()
    def fit(self):self.view.fitInView(self.view.sceneRect(),Qt.KeepAspectRatio)
    def update_document(self,layer):layer['doc'].text=xml_text(layer['root'])
    def add_point(self,x,y):
        if not 0<=x<=1000 or not 0<=y<=1000:return
        layer=self.active_layer();i=self.groups.currentIndex()
        if not layer or i<0:raise ValueError('Velg et lag og en koordinatgruppe først.')
        parent=self.group_nodes[i];existing=next((p for p in coordinates(layer['root']) if p['parent'] is parent),None)
        if not existing:raise ValueError('Gruppen mangler et punkt å bruke som mal.')
        self.checkpoint(layer)
        point=copy.deepcopy(existing['node']);wx,wz=self.scene_to_world(x,y);point.set('x',f'{wx:.3f}');point.set('z',f'{wz:.3f}');parent.append(point);self.update_document(layer);self.render()
    def manual_point(self):
        x,ok=QInputDialog.getDouble(self,'Nytt punkt','X:',0,0,float(self.studio.p['map_size']),3)
        if not ok:return
        z,ok=QInputDialog.getDouble(self,'Nytt punkt','Z:',0,0,float(self.studio.p['map_size']),3)
        if ok:self.add_point(*self.world_to_scene(x,z))
    def remove_points(self):
        layer=self.active_layer();items=[i for i in self.view.scene().selectedItems() if isinstance(i,PointItem) and i.layer is layer]
        if not items:return
        if any(item.point['parent'] is None for item in items):raise ValueError('Rotnoden kan ikke slettes.')
        self.checkpoint(layer)
        for item in items: item.point['parent'].remove(item.point['node'])
        self.update_document(layer);self.render();self.choose_layer()
    def checkpoint(self,layer):
        text=xml_text(layer['root']);history=layer.setdefault('undo',[])
        if not history or history[-1]!=text:history.append(text)
        del history[:-50];layer['redo']=[]
    def history_step(self,redo=False):
        layer=self.active_layer()
        if not layer:return
        source=layer.setdefault('redo' if redo else 'undo',[])
        if not source:return
        text=source.pop();current=xml_text(layer['root'])
        if text==current and source:text=source.pop()
        if text==current:return
        layer.setdefault('undo' if redo else 'redo',[]).append(current)
        layer['root']=parse_xml(text);self.update_document(layer);self.render();self.choose_layer()
        self.status.setText('Gjort om. Ikke lagret ennå.' if redo else 'Angret. Ikke lagret ennå.')
    def edit_point(self):
        layer=self.active_layer();items=[i for i in self.view.scene().selectedItems() if isinstance(i,PointItem) and i.layer is layer]
        if len(items)!=1:raise ValueError('Velg ett punkt i det aktive laget først.')
        node=items[0].point['node'];size=float(self.studio.p['map_size'])
        x,ok=QInputDialog.getDouble(self,'Rediger punkt','X:',float(node.get('x')),0,size,3)
        if not ok:return
        z,ok=QInputDialog.getDouble(self,'Rediger punkt','Z:',float(node.get('z')),0,size,3)
        if not ok:return
        radius_key='r' if 'r' in node.attrib else 'radius' if 'radius' in node.attrib else None
        radius=None
        if radius_key:
            radius,ok=QInputDialog.getDouble(self,'Rediger punkt','Radius (meter):',float(node.get(radius_key)),0,size,3)
            if not ok:return
        self.checkpoint(layer);node.set('x',f'{x:.3f}');node.set('z',f'{z:.3f}')
        if radius_key:node.set(radius_key,f'{radius:.3f}')
        self.update_document(layer);self.render();self.status.setText('Punkt endret. Ikke lagret ennå.')
    def save_active(self):
        layer=self.active_layer()
        if not layer:raise ValueError('Velg et lag først.')
        doc=layer['doc'];self.studio.editable_profile(doc.profile);doc.warnings()
        if not doc.dirty:return
        dialog=QMessageBox(self);dialog.setWindowTitle('Lagre kartkoordinater');dialog.setText('Lagre '+doc.relative+' med backup? Krever normalt restart.');dialog.setDetailedText(doc.diff());dialog.setStandardButtons(QMessageBox.Save|QMessageBox.Cancel)
        if dialog.exec()==QMessageBox.Save:
            if hasattr(self.studio.manager,'save_document'):self.studio.manager.save_document(doc)
            else:doc.save()
            self.studio.events.put('Kartlag lagret: '+doc.relative)
