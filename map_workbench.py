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
            self.workbench.update_document(self.layer);self.workbench.status.setText(f'Changed X {x:.2f}, Z {z:.2f}. Not saved yet.')
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
        layout=QVBoxLayout(self);row=QHBoxLayout();row.addWidget(button('Map image',lambda:studio.guard(self.choose_image)));row.addWidget(button('+ XML layer',lambda:studio.guard(self.add_layer)));self.layer_choice=QComboBox();row.addWidget(self.layer_choice,1);row.addWidget(button('Show/hide layer',self.toggle_layer));row.addWidget(button('Fit map',self.fit));layout.addLayout(row)
        row=QHBoxLayout();self.groups=QComboBox();row.addWidget(self.groups,1);row.addWidget(button('+ Point by coordinates',lambda:studio.guard(self.manual_point)));row.addWidget(button('Edit selected point',lambda:studio.guard(self.edit_point)));row.addWidget(button('Delete selected points',lambda:studio.guard(self.remove_points)));row.addWidget(button('Validate and save layer',lambda:studio.guard(self.save_active),'primary'));layout.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('Undo',lambda:studio.guard(lambda:self.history_step(False))));row.addWidget(button('Redo',lambda:studio.guard(lambda:self.history_step(True))));row.addStretch();layout.addLayout(row)
        self.view=MapView(self);layout.addWidget(self.view,1);self.cursor=label('X / Z','eyebrow');layout.addWidget(self.cursor);self.status=label('Zoom with the mouse wheel. Drag the map to pan. Double-click to add a point to the selected group. Drag a point to move it.','muted');layout.addWidget(self.status)
        self.layer_choice.currentIndexChanged.connect(self.choose_layer)
        self.live_items=[];live=QHBoxLayout();self.live_players=QCheckBox('Live players');self.live_players.setChecked(True);self.live_heat=QCheckBox('Player heatmap');self.live_loot=QCheckBox('Sampled loot')
        for box in (self.live_players,self.live_heat,self.live_loot):live.addWidget(box);box.toggled.connect(lambda:self.draw_live(getattr(self.studio,'analytics_cache',{}).get(self.studio.p['id'],{})))
        self.live_status=label('Telemetry: not connected','muted');live.addWidget(self.live_status);layout.insertLayout(2,live)

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
        path,_=QFileDialog.getOpenFileName(self,'Map image for selected server','','Images (*.png *.jpg *.jpeg *.webp)')
        if path:self.studio.p['map_image']=path;self.studio.manager.save();self.render()
    def add_layer(self):
        files=[name for name in catalog(self.studio.p) if name.endswith('.xml')]
        if not files:raise ValueError('No XML files found in the server folder.')
        name,ok=QInputDialog.getItem(self,'Map layer','Choose a file with X/Z coordinates:',files,0,False)
        if not ok:return
        if any(layer['doc'].relative==name for layer in self.layers):raise ValueError('This layer has already been added.')
        doc=Document(self.studio.p,name,self.studio.manager.home);root=parse_xml(doc.text);points=coordinates(root)
        if not points:raise ValueError('The file has no XML elements with x and z attributes. Open other formats in the configuration center.')
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
        self.live_items=[]
        scene=self.view.scene();scene.clear();pix=QPixmap(self.studio.p.get('map_image',''))
        if not pix.isNull():scene.addPixmap(pix.scaled(1000,1000,Qt.IgnoreAspectRatio,Qt.SmoothTransformation))
        else:
            scene.setBackgroundBrush(QColor('#12212b'))
            text=scene.addText('Choose map image for '+self.studio.p['name']);text.setDefaultTextColor(QColor('#e2f4ff'));text.setPos(20,20)
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
        scene.setSceneRect(QRectF(-20,-20,1040,1040));self.draw_live(getattr(self.studio,'analytics_cache',{}).get(self.studio.p['id'],{}));self.fit()
    def draw_live(self,data):
        if not hasattr(self,'live_items'):return
        import html
        scene=self.view.scene()
        for item in self.live_items:scene.removeItem(item)
        self.live_items=[];status=data.get('status',{});sample=status.get('sample') if status.get('connected') else None
        self.live_status.setText('Telemetry: '+status.get('message','not connected'))
        heat=data.get('heat',[])
        if self.live_heat.isChecked() and heat:
            maximum=max(v['seconds'] for v in heat);width=100/float(self.studio.p['map_size'])*1000
            for point in heat:
                x,y=self.world_to_scene(point['x'],point['z']);color=QColor('#ff9b54');color.setAlpha(int(35+155*point['seconds']/max(1,maximum)))
                item=scene.addRect(x-width/2,y-width/2,width,width,QPen(Qt.NoPen),QBrush(color));item.setZValue(3);item.setToolTip(f"Occupancy: {point['seconds']:.0f} player-seconds / 100 m cell");self.live_items.append(item)
        if not sample:return
        if abs(sample['world_size']-float(self.studio.p['map_size']))>1:self.live_status.setText('Telemetry connected — map size differs from game world; check map calibration')
        if self.live_loot.isChecked() and sample['loot_age']<=60:
            if sample['loot_radius']>0:
                x,y=self.world_to_scene(sample['loot_x'],sample['loot_z']);r=sample['loot_radius']/float(self.studio.p['map_size'])*1000
                item=scene.addEllipse(x-r,y-r,r*2,r*2,QPen(QColor('#a78aff')),QBrush(QColor(167,138,255,25)));item.setZValue(3);item.setToolTip(f"Current loot sample area • age {sample['loot_age']:.1f} s");self.live_items.append(item)
            for point in sample['loot']:
                x,y=self.world_to_scene(point['x'],point['z']);item=scene.addRect(-2,-2,4,4,QPen(QColor('#e1acff')),QBrush(QColor('#a78aff')));item.setPos(x,y);item.setFlag(QGraphicsItem.ItemIgnoresTransformations);item.setZValue(4);item.setToolTip(html.escape(point['type'])+' (sampled ground loot)');self.live_items.append(item)
        if self.live_players.isChecked():
            for point in sample['players']:
                x,y=self.world_to_scene(point['x'],point['z']);item=scene.addEllipse(-4,-4,8,8,QPen(QColor('#e5fff8')),QBrush(QColor('#65dfc5')));item.setPos(x,y);item.setFlag(QGraphicsItem.ItemIgnoresTransformations);item.setZValue(6);item.setToolTip(html.escape(point['name'])+f" — health {point['health']:.0f}, ping {point['ping']} ms");self.live_items.append(item)
    def fit(self):self.view.fitInView(self.view.sceneRect(),Qt.KeepAspectRatio)
    def update_document(self,layer):layer['doc'].text=xml_text(layer['root'])
    def add_point(self,x,y):
        if not 0<=x<=1000 or not 0<=y<=1000:return
        layer=self.active_layer();i=self.groups.currentIndex()
        if not layer or i<0:raise ValueError('Choose a layer and coordinate group first.')
        parent=self.group_nodes[i];existing=next((p for p in coordinates(layer['root']) if p['parent'] is parent),None)
        if not existing:raise ValueError('The group has no point to use as a template.')
        self.checkpoint(layer)
        point=copy.deepcopy(existing['node']);wx,wz=self.scene_to_world(x,y);point.set('x',f'{wx:.3f}');point.set('z',f'{wz:.3f}');parent.append(point);self.update_document(layer);self.render()
    def manual_point(self):
        x,ok=QInputDialog.getDouble(self,'New point','X:',0,0,float(self.studio.p['map_size']),3)
        if not ok:return
        z,ok=QInputDialog.getDouble(self,'New point','Z:',0,0,float(self.studio.p['map_size']),3)
        if ok:self.add_point(*self.world_to_scene(x,z))
    def remove_points(self):
        layer=self.active_layer();items=[i for i in self.view.scene().selectedItems() if isinstance(i,PointItem) and i.layer is layer]
        if not items:return
        if any(item.point['parent'] is None for item in items):raise ValueError('The root node cannot be deleted.')
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
        self.status.setText('Redone. Not saved yet.' if redo else 'Undone. Not saved yet.')
    def edit_point(self):
        layer=self.active_layer();items=[i for i in self.view.scene().selectedItems() if isinstance(i,PointItem) and i.layer is layer]
        if len(items)!=1:raise ValueError('Select one point in the active layer first.')
        node=items[0].point['node'];size=float(self.studio.p['map_size'])
        x,ok=QInputDialog.getDouble(self,'Edit point','X:',float(node.get('x')),0,size,3)
        if not ok:return
        z,ok=QInputDialog.getDouble(self,'Edit point','Z:',float(node.get('z')),0,size,3)
        if not ok:return
        radius_key='r' if 'r' in node.attrib else 'radius' if 'radius' in node.attrib else None
        radius=None
        if radius_key:
            radius,ok=QInputDialog.getDouble(self,'Edit point','Radius (meters):',float(node.get(radius_key)),0,size,3)
            if not ok:return
        self.checkpoint(layer);node.set('x',f'{x:.3f}');node.set('z',f'{z:.3f}')
        if radius_key:node.set(radius_key,f'{radius:.3f}')
        self.update_document(layer);self.render();self.status.setText('Point changed. Not saved yet.')
    def save_active(self):
        layer=self.active_layer()
        if not layer:raise ValueError('Choose a layer first.')
        doc=layer['doc'];self.studio.editable_profile(doc.profile);doc.warnings()
        if not doc.dirty:return
        dialog=QMessageBox(self);dialog.setWindowTitle('Save map coordinates');dialog.setText('Save '+doc.relative+' with backup? Usually requires a restart.');dialog.setDetailedText(doc.diff());dialog.setStandardButtons(QMessageBox.Save|QMessageBox.Cancel)
        if dialog.exec()==QMessageBox.Save:
            if hasattr(self.studio.manager,'save_document'):self.studio.manager.save_document(doc)
            else:doc.save()
            self.studio.events.put('Map layer saved: '+doc.relative)
