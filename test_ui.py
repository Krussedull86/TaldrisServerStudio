"""Offscreen GUI integration tests. No real DayZ or Steam process is launched."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,time,unittest,types
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
from desktop import STYLE
from integration import IntegratedStudio,SteamSession
import integration

class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]); cls.app.setStyle('Fusion'); cls.app.setStyleSheet(STYLE)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.window=IntegratedStudio(self.root/'data'); self.window.show(); self.app.processEvents()
    def tearDown(self):
        self.window.timer.stop(); self.window.close(); self.app.processEvents(); self.tmp.cleanup()
    def pump(self,predicate,seconds=8):
        end=time.monotonic()+seconds
        while not predicate() and time.monotonic()<end:self.app.processEvents(); time.sleep(.01)
        self.assertTrue(predicate())
    def test_local_browser_scan_selection_and_import(self):
        from local_mod_ui import LocalModDialog
        from local_mods import import_mods
        from PySide6.QtCore import Qt
        root=self.root/'dev mods'; ready=root/'@Ready'; (ready/'Addons').mkdir(parents=True); (ready/'Addons'/'test.pbo').write_bytes(b'test'); (root/'@Unbuilt').mkdir()
        dialog=LocalModDialog(str(root),self.window); dialog.show(); dialog.scan()
        self.pump(lambda:dialog.worker is not None and not dialog.worker.isRunning() and dialog.import_button.isEnabled())
        self.assertEqual(dialog.table.rowCount(),2); self.assertEqual(dialog.table.item(0,0).checkState(),Qt.Checked); self.assertEqual(dialog.table.item(1,0).checkState(),Qt.Unchecked)
        dialog.import_selected(); self.assertEqual(len(dialog.selected_rows),1)
        added,_=import_mods(self.window.p,dialog.selected_rows); self.window.refresh_mods(); self.assertEqual(added[0]['path'],str(ready)); self.assertIn('Lokal',self.window.mods.item(0,2).text()); dialog.close()
    def test_switch_local_mod_to_both(self):
        from local_mods import import_mods,scan_mods
        path=self.root/'@Both'; (path/'Addons').mkdir(parents=True); (path/'Addons'/'test.pbo').write_bytes(b'test'); import_mods(self.window.p,scan_mods(path)['mods']); self.window.refresh_mods(); self.window.mods.selectRow(0)
        with patch('integration.QInputDialog.getItem',return_value=('Begge (-mod + -serverMod)',True)):self.window.edit_selected_mod()
        self.assertEqual(self.window.p['mods'][0]['load_mode'],'both'); self.assertEqual(self.window.mods.item(0,3).text(),'Begge')
    def test_pages_and_import(self):
        w=self.window
        for i in range(10):w.go(i); self.app.processEvents()
        self.assertEqual(w.stack.count(),10); self.assertEqual(w.login.currentIndex(),0)
        item=dict(id='1559212036',title='CF',updated=100,size=100,file_type=0,description='Test',url='https://steamcommunity.com/sharedfiles/filedetails/?id=1559212036')
        w.import_items(w.p,[item]); w.import_items(w.p,[item]); self.assertEqual(len(w.p['mods']),1); self.assertIn('CF',w.mods.item(0,1).text())
    def fake_exe(self,body):
        p=self.root/'steamcmd.exe'; p.write_text('#!/usr/bin/env python3\n'+body); p.chmod(0o755); return p
    @unittest.skipIf(os.name=='nt','Uses a Unix mock executable; real SteamCMD needs Windows integration testing')
    def test_successful_process_deploy_and_provision(self):
        w=self.window; w.p.update(root=str(self.root/'server'),steamcmd=str(self.fake_exe('''import sys
from pathlib import Path
args=sys.argv
root=Path(args[args.index('+force_install_dir')+1]); root.mkdir(parents=True,exist_ok=True)
(root/'DayZServer_x64.exe').write_bytes(b'MZmock')
(root/'mpmissions'/'dayzOffline.chernarusplus').mkdir(parents=True,exist_ok=True)
mod=Path(__file__).parent/'steamapps'/'workshop'/'content'/'221100'/'123'; (mod/'addons').mkdir(parents=True,exist_ok=True)
(mod/'addons'/'test.pbo').write_bytes(b'test')
print("Success! App '223350' fully installed.",flush=True)
print('Success. Downloaded item 123 to "'+str(mod)+'" (4 bytes)',flush=True)
''')),mods=[dict(folder='@123',id='123',enabled=True,server=False)],start_after_install=False)
        with patch.object(integration,'os',types.SimpleNamespace(name='nt')):w.steam.start(w.p,'all',chained=True)
        self.pump(lambda:not w.steam.running() and not w.tasks and w.p['id'] not in w.manager.busy)
        self.assertTrue((Path(w.p['root'])/'@123'/'addons'/'test.pbo').exists()); self.assertTrue((Path(w.p['root'])/'serverDZ.cfg').exists()); self.assertTrue(w.p['mods'][0]['installed_at'])
    @unittest.skipIf(os.name=='nt','Uses a Unix mock executable; real SteamCMD needs Windows integration testing')
    def test_authentication_failure_does_not_provision(self):
        w=self.window; w.p.update(root=str(self.root/'server'),steamcmd=str(self.fake_exe('print("ERROR! Failed to install app: No subscription",flush=True)\n')),start_after_install=True)
        with patch.object(integration,'os',types.SimpleNamespace(name='nt')):w.steam.start(w.p,'server',chained=True)
        self.pump(lambda:not w.steam.running()); self.assertFalse((Path(w.p['root'])/'serverDZ.cfg').exists()); self.assertIn('avviste',w.console_status.text())
    @unittest.skipIf(os.name=='nt','Uses a Unix mock executable; real SteamCMD needs Windows integration testing')
    def test_secret_not_in_terminal_or_settings(self):
        w=self.window; w.p.update(root=str(self.root/'server'),steamcmd=str(self.fake_exe('''import sys
print('Password:',flush=True)
s=sys.stdin.readline().strip(); print('Echo test: '+s,flush=True)
print('Logged in OK',flush=True)
''')))
        with patch.object(integration,'os',types.SimpleNamespace(name='nt')):w.steam.start(w.p,'login')
        self.pump(lambda:'Password:' in w.terminal.toPlainText()); w.secret.setText('never-persist-this'); w.send_secret(); self.pump(lambda:not w.steam.running())
        self.assertNotIn('never-persist-this',w.terminal.toPlainText()); self.assertNotIn('never-persist-this',w.manager.file.read_text()); self.assertIn('[skjult]',w.terminal.toPlainText())
if __name__=='__main__':unittest.main()
