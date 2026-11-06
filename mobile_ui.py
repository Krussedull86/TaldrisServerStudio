"""Local owner controls for opt-in Android pairing and gateway configuration."""
import json,time
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor,QPainter,QPixmap
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QSpinBox,QCheckBox,QScrollArea,QTableWidget,QTableWidgetItem,QHeaderView,QDialog,QPlainTextEdit,QMessageBox,QApplication
from desktop import label,button,card

class MobilePage(QScrollArea):
    def __init__(self,studio):
        super().__init__();self.studio=studio;self.busy=False;self.devices=[];self.setWidgetResizable(True);body=QWidget();self.setWidget(body);layout=QVBoxLayout(body)
        box,c=card('ANDROID ACCESS','Direct HTTPS connection to this background agent. No cloud account is required.');self.enabled=QCheckBox('Enable mobile HTTPS gateway');c.addWidget(self.enabled);form=QFormLayout();self.port=QSpinBox();self.port.setRange(1024,65535);self.port.setValue(8788);form.addRow('Dedicated TCP port',self.port);self.url=QLineEdit();self.url.setPlaceholderText('https://your-hostname-or-ip:8788');form.addRow('Phone connection address',self.url);c.addLayout(form);self.firewall=QCheckBox('Automatically manage this installation’s Windows Firewall rule');self.firewall.setChecked(True);c.addWidget(self.firewall)
        c.addWidget(label('For internet access, forward this TCP port in the router to this Windows machine. ISP carrier-grade NAT may require a VPN or relay. No UPnP router changes are made. Pairing pins the server certificate; do not expose the local owner API or RCon.','muted'));row=QHBoxLayout();row.addWidget(button('Save / apply gateway',lambda:studio.guard(self.save),'primary'));row.addWidget(button('Refresh status',self.refresh));c.addLayout(row);self.status=label('Loading mobile gateway status…','muted');c.addWidget(self.status);self.pin=QLineEdit();self.pin.setReadOnly(True);form.addRow('Certificate SHA-256',self.pin);layout.addWidget(box)
        box,c=card('PAIR A PHONE','Create a one-use QR invitation valid for five minutes. Select exactly which servers and actions the phone may access.');self.server_choices=QVBoxLayout();c.addLayout(self.server_choices);self.control=QCheckBox('Allow start, graceful stop, restart and cancel countdown');self.message=QCheckBox('Allow server messages');c.addWidget(self.control);c.addWidget(self.message);c.addWidget(button('Create pairing QR code',lambda:studio.guard(self.pair),'primary'));c.addWidget(label('Read access is always included. Device access expires after 90 days and can be revoked below. Restart/stop use an announced countdown; no force-stop or arbitrary console commands are exposed.','muted'));layout.addWidget(box)
        box,c=card('PAIRED DEVICES','Removing a device blocks future API requests. Already accepted server jobs may finish.');self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Device','Permissions','Servers','Expires']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setMinimumHeight(180);c.addWidget(self.table);c.addWidget(button('Revoke selected phone',lambda:studio.guard(self.revoke),'danger'));layout.addWidget(box);layout.addStretch();self.boxes={};self.populate_servers();QTimer.singleShot(400,self.refresh)
    def populate_servers(self):
        while self.server_choices.count():
            item=self.server_choices.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.boxes={}
        for p in self.studio.manager.state['servers']:
            b=QCheckBox(p['name']);b.setChecked(p['id']==self.studio.p['id']);self.boxes[p['id']]=b;self.server_choices.addWidget(b)
    def call(self,method,params,done,timeout=15):
        if self.busy:return
        self.busy=True;before=set(self.studio.tasks)
        self.studio.run_task(lambda:self.studio.manager.client.call(method,params,timeout=timeout),done,description='Mobile access')
        for task in self.studio.tasks-before:task.finished.connect(lambda:setattr(self,'busy',False))
    def refresh(self):self.call('mobile_status',{},self.render)
    def render(self,data):
        s=data['settings'];self.enabled.setChecked(s['enabled']);self.port.setValue(s['port']);self.url.setText(s['public_url']);self.firewall.setChecked(s['auto_firewall']);self.pin.setText(data['fingerprint']);self.status.setText(('Listening on TCP '+str(s['port']) if data['listening'] else 'Not listening')+(' • '+data['error'] if data['error'] else ''));self.devices=data['devices'];names={p['id']:p['name'] for p in self.studio.manager.state['servers']};self.table.setRowCount(len(self.devices));self.populate_servers()
        for row,d in enumerate(self.devices):
            for col,value in enumerate([d['name'],', '.join(d['scopes']),', '.join(names.get(k,k) for k in d['servers']),time.strftime('%Y-%m-%d',time.localtime(d['expires']))]):self.table.setItem(row,col,QTableWidgetItem(value))
    def save(self):
        params=dict(enabled=self.enabled.isChecked(),port=self.port.value(),public_url=self.url.text(),auto_firewall=self.firewall.isChecked());self.call('mobile_configure',params,self.render,150)
    def pair(self):
        params=dict(servers=[key for key,b in self.boxes.items() if b.isChecked()],scopes=['read']+(['control'] if self.control.isChecked() else [])+(['message'] if self.message.isChecked() else []));self.call('mobile_pair',params,self.show_pair)
    def show_pair(self,data):
        import qrcode
        raw=json.dumps(data,separators=(',',':'));d=QDialog(self);d.setWindowTitle('Pair Android device');layout=QVBoxLayout(d);layout.addWidget(label('Scan with DZSA Tools Android • invitation expires in five minutes','eyebrow'));qr=qrcode.QRCode(border=4,error_correction=qrcode.constants.ERROR_CORRECT_M);qr.add_data(raw);qr.make(fit=True);matrix=qr.get_matrix();scale=max(3,400//len(matrix));pix=QPixmap(len(matrix)*scale,len(matrix)*scale);pix.fill(Qt.white);painter=QPainter(pix);painter.setPen(Qt.NoPen);painter.setBrush(QColor('black'))
        for y,row in enumerate(matrix):
            for x,value in enumerate(row):
                if value:painter.drawRect(x*scale,y*scale,scale,scale)
        painter.end();image=label('');image.setPixmap(pix);image.setAlignment(Qt.AlignCenter);layout.addWidget(image);text=QPlainTextEdit(raw);text.setReadOnly(True);text.setMaximumHeight(100);layout.addWidget(text);layout.addWidget(button('Copy invitation JSON',lambda:QApplication.clipboard().setText(raw)));layout.addWidget(label('Only share this invitation with the intended phone. Verify the address and certificate fingerprint on that phone.','muted'));layout.addWidget(button('Close',d.accept));timer=QTimer(d);timer.setSingleShot(True);timer.timeout.connect(d.reject);timer.start(max(1,int((data['expires']-time.time())*1000)));d.exec()
    def revoke(self):
        index=self.table.currentRow()
        if index<0:raise ValueError('Select a phone first.')
        d=self.devices[index]
        if QMessageBox.question(self,'Revoke phone','Remove access for '+d['name']+'?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)==QMessageBox.Yes:self.call('mobile_revoke',{'device':d['id']},self.render)
