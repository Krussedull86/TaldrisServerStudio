import tempfile,unittest,copy,json,time
from pathlib import Path
from unittest.mock import Mock,patch
from core import Manager
from mission_settings import choices,configured_mission,save_mission,check_config_edit
from config_documents import digest

class MissionSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.manager=Manager(self.root/'data');self.p=self.manager.state['servers'][0];self.p['root']=str(self.root);self.cfg=self.root/'serverDZ.cfg';self.text='// keep\ninstanceId=1;hostname="Keep";class Missions {class DayZ {template="dayzOffline.old";};};';self.cfg.write_text(self.text)
    def test_choices_follow_cfg_and_discover_custom_missions(self):
        (self.root/'mpmissions/dayzOffline.custom').mkdir(parents=True);items,current=choices(self.p);self.assertIn('dayzOffline.nasdara',items);self.assertIn('dayzOffline.custom',items);self.assertEqual(current,'dayzOffline.old')
    def test_save_custom_template_updates_cfg_profile_and_backup(self):
        result=save_mission(self.manager,self.p,'dayzOffline.nasdara',digest(self.text));self.assertEqual(configured_mission(self.p),'dayzOffline.nasdara');self.assertEqual(self.p['mission'],'dayzOffline.nasdara');self.assertEqual(Path(result['backup']).read_text(),self.text);self.assertIn('hostname="Keep"',self.cfg.read_text());self.assertIn('// keep',self.cfg.read_text())
    def test_save_independent_cfg_while_another_instance_shares_root(self):
        other=self.manager.add();other.update(root=str(self.root),config='other.cfg',profiles='other-profile');self.manager.procs[other['id']]=Mock();self.manager.procs[other['id']].poll.return_value=None
        save_mission(self.manager,self.p,'dayzOffline.nasdara',digest(self.text));self.assertEqual(configured_mission(self.p),'dayzOffline.nasdara')
        with self.assertRaises(ValueError):check_config_edit(self.manager,self.p,'mpmissions/test/types.xml')
        other['config']='serverDZ.cfg'
        with self.assertRaises(ValueError):save_mission(self.manager,self.p,'dayzOffline.old',digest(self.cfg.read_text()))
    def test_stale_or_running_save_keeps_cfg(self):
        with self.assertRaises(ValueError):save_mission(self.manager,self.p,'dayzOffline.nasdara','stale')
        with patch.object(self.manager,'running',return_value=True):
            with self.assertRaises(ValueError):save_mission(self.manager,self.p,'dayzOffline.nasdara',digest(self.text))
        self.assertEqual(self.cfg.read_text(),self.text)

    def test_shared_root_restart_defers_shared_file_updates(self):
        from host_engine import HostEngine
        engine=HostEngine(self.root/'agent');p=engine.manager.state['servers'][0];p.update(root=str(self.root));q=engine.manager.add();q.update(root=str(self.root))
        with patch.object(engine.manager,'running',side_effect=lambda profile:profile['id']==q['id']),patch.object(engine.manager,'start') as start,patch.object(engine,'backup') as backup,patch.object(engine,'steam') as steam:
            engine.maintenance(p,True);start.assert_called_once_with(p);backup.assert_not_called();steam.assert_not_called();self.assertTrue(p['maintenance_deferred'])

class ProcessOwnershipTests(unittest.TestCase):
    def test_discovery_and_restore_never_attach_one_pid_to_two_profiles(self):
        from process_registry import discover_processes,restore_processes
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manager=Manager(root/'data');a=manager.state['servers'][0];b=manager.add()
            for p in (a,b):p.update(root=str(root),config='serverDZ.cfg',profiles='profiles',port=2302)
            exe=root/'DayZServer_x64.exe';args=[str(exe),'-config='+str(root/'serverDZ.cfg'),'-profiles='+str(root/'profiles'),'-port=2302'];fake=Mock(pid=123456);fake.info={'name':'DayZServer_x64.exe'};fake.exe.return_value=str(exe);fake.cmdline.return_value=args;fake.create_time.return_value=time.time();fake.is_running.return_value=True;fake.status.return_value='running'
            with patch('process_registry.psutil.process_iter',return_value=[fake]),patch('process_registry.psutil.Process',return_value=fake):
                discover_processes(manager);self.assertEqual(len(manager.procs),1)
                path=manager.home/'processes.json';records=json.loads(path.read_text());records[b['id']]=copy.deepcopy(records[a['id']]);path.write_text(json.dumps(records));manager.procs.clear();manager.launches.clear();restore_processes(manager);self.assertEqual(len(manager.procs),1)

class MissionButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def test_wizard_save_button_accepts_custom_text_and_writes_cfg(self):
        from integration import IntegratedStudio
        from PySide6.QtWidgets import QPushButton
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manager=Manager(root/'data');p=manager.state['servers'][0];p['root']=str(root);manager.save();cfg=root/'serverDZ.cfg';cfg.write_text('class Missions {class DayZ {template="dayzOffline.old";};};')
            w=IntegratedStudio(root/'data');w.mission.setCurrentText('dayzOffline.nasdara');button=next(b for b in w.findChildren(QPushButton) if b.text()=='Lagre kartvalg til CFG');button.click();self.assertEqual(configured_mission(w.p),'dayzOffline.nasdara');self.assertIn('lagret',w.setup_status.text());w.mission.setCurrentText('dayzOffline.custom');next(b for b in w.findChildren(QPushButton) if b.text()=='Lagre oppsett').click();self.assertEqual(configured_mission(w.p),'dayzOffline.custom');w.timer.stop();w.close();w.deleteLater()
