"""Optional community invite without embedding or guessing a Discord server."""
from urllib.parse import urlparse
from PySide6.QtCore import QUrl,QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLineEdit,QCheckBox,QDialogButtonBox,QHBoxLayout
from desktop import label,button

from community_settings import validate_invite

class CommunityControls:
    def __init__(self,studio):
        self.studio=studio;row=QHBoxLayout();row.addWidget(label('COMMUNITY & SUPPORT','eyebrow'));row.addStretch();row.addWidget(button('Community Discord',lambda:studio.guard(self.open)));row.addWidget(button('Set Discord invite …',lambda:studio.guard(self.configure)));studio.stack.widget(12).layout().insertLayout(0,row)
        studio.statusBar().addPermanentWidget(button('Discord',lambda:studio.guard(self.open)))
        QTimer.singleShot(1200,self.welcome)
    def config(self):return self.studio.manager.raw.get('state',{}).get('community',{})
    def configure(self):
        cfg=self.config();d=QDialog(self.studio);d.setWindowTitle('Community Discord');layout=QVBoxLayout(d);form=QFormLayout();url=QLineEdit(cfg.get('invite',''));url.setPlaceholderText('https://discord.gg/your-invite');form.addRow('Your community invite',url);show=QCheckBox('Show community welcome at application startup');show.setChecked(cfg.get('show_startup',True));form.addRow(show);layout.addLayout(form);layout.addWidget(label('The link opens only when you choose Join Discord. It is separate from your bot token and operations-channel settings.','muted'));buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);layout.addWidget(buttons)
        if d.exec():self.studio.manager.client.call('community',{'invite':validate_invite(url.text()),'show_startup':show.isChecked()});self.studio.manager.refresh()
    def open(self):
        value=validate_invite(self.config().get('invite',''))
        if value:QDesktopServices.openUrl(QUrl(value))
        else:self.configure()
    def welcome(self):
        cfg=self.config()
        if not cfg.get('invite') or not cfg.get('show_startup',True):return
        try:validate_invite(cfg['invite'])
        except ValueError:return
        d=QDialog(self.studio);d.setWindowTitle('Welcome to CruzDoodelZ Server Studio');layout=QVBoxLayout(d);layout.addWidget(label('Your server workspace','title'));layout.addWidget(label('Join the community Discord for support, announcements and development discussion.'));layout.addWidget(button('Join Discord',self.open,'primary'));show=QCheckBox('Show this welcome at startup');show.setChecked(True);layout.addWidget(show);layout.addWidget(button('Continue to Studio',d.accept))
        d.exec()
        if not show.isChecked():self.studio.manager.client.call('community',{'invite':cfg['invite'],'show_startup':False});self.studio.manager.refresh()
