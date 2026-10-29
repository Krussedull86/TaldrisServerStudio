import copy,os,tempfile,threading,time,unittest,zipfile
from pathlib import Path
from unittest.mock import Mock,patch,call
from host_engine import HostEngine
from companion_programs import CompanionPrograms
from log_rotation import rotate
from runtime_tools import validate_runtime

def program(root,**kwargs):
    return dict(id='tool',name='Bridge',path=str(root/'Bridge.exe'),args='--config "file with spaces.json"',cwd='',enabled=True,on_start=True,on_restart=True,required=True,wait_seconds=0,**kwargs)

class RotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.logs=self.root/'server/profiles';self.logs.mkdir(parents=True);self.p=dict(id='p',root=str(self.root/'server'),profiles='profiles',log_keep_days=14,log_keep_archives=2,log_max_mb=10)
    def test_archive_removes_only_closed_log_files_and_keeps_original_bytes(self):
        (self.logs/'a.RPT').write_bytes(b'old-rpt\x00');(self.logs/'b.log').write_text('script');(self.logs/'world.bin').write_text('keep');outside=self.root/'outside.log';outside.write_text('private')
        try:(self.logs/'link.log').symlink_to(outside)
        except OSError:pass
        result=rotate(self.p,self.root/'data');self.assertEqual(result['archived'],2)
        with zipfile.ZipFile(result['archive']) as z:self.assertEqual(z.read('a.RPT'),b'old-rpt\x00');self.assertEqual(set(z.namelist()),{'a.RPT','b.log'})
        self.assertTrue((self.logs/'world.bin').is_file());self.assertTrue(outside.is_file());self.assertFalse((self.logs/'a.RPT').exists())
    def test_retention_only_removes_our_archives(self):
        result=rotate(self.p,self.root/'data');folder=Path(result['folder']);other=folder/'manual.zip';other.write_bytes(b'keep');(folder/'logs-user.zip').write_bytes(b'keep')
        for i in range(4):
            p=folder/f'logs-20260101-000000-{i:08x}.zip';p.write_bytes(b'zip');os.utime(p,(time.time()-i*100,time.time()-i*100))
        result=rotate(self.p,self.root/'data');self.assertEqual(result['removed_archives'],2);self.assertTrue(other.exists());self.assertTrue((folder/'logs-user.zip').exists())
    def test_changed_file_stays_in_source(self):
        log=self.logs/'a.log';log.write_text('before');original=zipfile.ZipFile.write
        def changing(z,path,*args,**kwargs):
            result=original(z,path,*args,**kwargs);Path(path).write_text('changed while reading');return result
        with patch.object(zipfile.ZipFile,'write',changing):result=rotate(self.p,self.root/'data')
        self.assertEqual(result['archived'],0);self.assertTrue(log.exists());self.assertGreater(result['skipped'],0)

class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.p=program(self.root);Path(self.p['path']).touch();self.supervisor=CompanionPrograms();self.stop=threading.Event()
    def test_full_path_and_arguments_match_existing_process(self):
        wrong=Mock();wrong.info=dict(pid=1,name='Bridge.exe',exe=str(self.root/'other/Bridge.exe'),cmdline=[])
        correct=Mock();correct.info=dict(pid=2,name='Bridge.exe',exe=self.p['path'],cmdline=[self.p['path'],'--config','file with spaces.json'])
        with patch('companion_programs.psutil.process_iter',return_value=[wrong,correct]),patch('companion_programs.subprocess.Popen') as spawn:
            self.supervisor.ensure([self.p],'start',lambda s:None,self.stop);spawn.assert_not_called();self.assertEqual(self.supervisor.inspect(self.p)['pids'],[2])
    def test_spawn_once_across_profiles_and_preserve_argv(self):
        proc=Mock(pid=55);proc.poll.return_value=None
        with patch('companion_programs.psutil.process_iter',return_value=[]),patch('companion_programs.subprocess.Popen',return_value=proc) as spawn:
            self.supervisor.ensure([self.p],'start',lambda s:None,self.stop);self.supervisor.ensure([self.p],'restart',lambda s:None,self.stop);spawn.assert_called_once();self.assertEqual(spawn.call_args.args[0],[self.p['path'],'--config','file with spaces.json']);proc.terminate.assert_not_called()
    def test_restart_only_and_required_failure(self):
        self.p['on_start']=False
        with patch('companion_programs.psutil.process_iter',return_value=[]),patch('companion_programs.subprocess.Popen',side_effect=OSError('failed')) as spawn:
            self.supervisor.ensure([self.p],'start',lambda s:None,self.stop);spawn.assert_not_called()
            with self.assertRaises(ValueError):self.supervisor.ensure([self.p],'restart',lambda s:None,self.stop)
            self.p['required']=False;self.supervisor.ensure([self.p],'restart',lambda s:None,self.stop)
    def test_manual_stop_revalidates_full_identity(self):
        process=Mock();process.exe.return_value=self.p['path'];process.cmdline.return_value=[self.p['path'],'--config','file with spaces.json']
        with patch.object(self.supervisor,'inspect',return_value=dict(id='tool',name='Bridge',status='running',pids=[99])),patch('companion_programs.psutil.Process',return_value=process):
            self.supervisor.control(self.p,'stop',lambda s:None,self.stop)
        process.terminate.assert_called_once();process.wait.assert_called_once_with(timeout=15)
        process.reset_mock();process.exe.return_value=str(self.root/'other.exe')
        with patch.object(self.supervisor,'inspect',return_value=dict(id='tool',name='Bridge',status='running',pids=[99])),patch('companion_programs.psutil.Process',return_value=process):
            with self.assertRaises(ValueError):self.supervisor.control(self.p,'stop',lambda s:None,self.stop)
        process.terminate.assert_not_called()
    def test_manual_start_overrides_automatic_disable(self):
        with patch.object(self.supervisor,'ensure') as ensure,patch.object(self.supervisor,'inspect',return_value=dict(status='stopped',pids=[])):
            self.supervisor.control(dict(self.p,enabled=False,on_start=False),'start',lambda s:None,self.stop)
        self.assertTrue(ensure.call_args.args[0][0]['enabled']);self.assertTrue(ensure.call_args.args[0][0]['on_start'])
    def test_validation_rejects_shell_or_relative_executable(self):
        with self.assertRaises(ValueError):validate_runtime({'programs':[dict(self.p,path='relative.exe')]})
        with self.assertRaises(ValueError):validate_runtime({'programs':[dict(self.p,path=str(self.root/'cmd.bat'))]})

class EngineAutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.e=HostEngine(self.root/'data');self.p=self.e.manager.state['servers'][0];server=self.root/'server';server.mkdir();self.p.update(root=str(server),auto_firewall=False,query_enabled=False,auto_update=True,mod_restart_enabled=True,mod_grace_minutes=12,update_game=False,maintenance_backup=False)
        (server/'DayZServer_x64.exe').touch();(server/'serverDZ.cfg').write_text('hostname="Test";');self.p['mods']=[dict(id='123',folder='@Test',load_mode='client',enabled=True,installed_updated=10)]
    def live(self):
        proc=Mock(pid=12345);proc.poll.return_value=None;self.e.manager.procs[self.p['id']]=proc;self.e.manager.launches[self.p['id']]={'restart_due':None};return proc
    def test_detected_update_schedules_once_without_extending_grace(self):
        self.live()
        with patch('host_engine.details',return_value=[dict(id='123',title='Updated',updated=20)]),patch.object(self.e,'rcon') as rcon:
            self.e.check_mods(self.p);deadline=self.p['shutdown_request']['deadline'];self.e.check_mods(self.p);self.assertEqual(self.p['shutdown_request']['deadline'],deadline);self.assertEqual(self.p['shutdown_request']['source'],'mod_update');rcon.assert_called_once();self.assertAlmostEqual(deadline-time.time(),12*60,delta=3)
    def test_cancelled_auto_restart_snoozes_and_disabled_setting_cancels(self):
        self.live()
        with patch.object(self.e,'rcon'):
            self.e.maybe_mod_restart(self.p,['Mod']);self.e.execute('cancel_restart',self.p['id'],{});self.e.maybe_mod_restart(self.p,['Mod']);self.assertNotIn('shutdown_request',self.p)
            self.p['mod_restart_snooze_until']=0;self.e.maybe_mod_restart(self.p,['Mod']);self.e.patch_state([{'id':self.p['id'],'fields':{'mod_restart_enabled':{'before':True,'after':False}}}]);self.assertNotIn('shutdown_request',self.p)
    def test_missing_rcon_and_shared_files_do_not_stop_server(self):
        self.live()
        with patch.object(self.e,'rcon',side_effect=ValueError('no RCon')):self.e.maybe_mod_restart(self.p,['Mod'])
        self.assertNotIn('shutdown_request',self.p);q=self.e.manager.add();q.update(root=self.p['root']);self.e.manager.procs[q['id']]=Mock();self.e.manager.procs[q['id']].poll.return_value=None
        with patch.object(self.e,'rcon') as rcon:self.e.maybe_mod_restart(self.p,['Mod']);rcon.assert_not_called()
    def test_hooks_execute_before_server_and_failures_release_busy_flag(self):
        self.p['log_rotation_enabled']=True
        order=Mock()
        with patch.object(self.e,'rotate_logs',order.rotate),patch.object(self.e.companions,'ensure',order.ensure),patch.object(self.e.manager,'start',order.start):self.e.start_server(self.p,'restart')
        self.assertEqual([c[0] for c in order.mock_calls],['rotate','ensure','start']);self.assertNotIn(self.p['id'],self.e.manager.busy)
        with patch.object(self.e,'rotate_logs'),patch.object(self.e.companions,'ensure',side_effect=ValueError('required tool failed')),patch.object(self.e.manager,'start') as start:
            with self.assertRaises(ValueError):self.e.start_server(self.p,'start')
            start.assert_not_called();self.assertNotIn(self.p['id'],self.e.manager.busy)
    def test_manual_rotation_refuses_live_server(self):
        self.live()
        with self.assertRaises(ValueError):self.e.rotate_logs(self.p)
    def test_maintenance_updates_before_restart_hooks(self):
        order=Mock()
        with patch.object(self.e,'steam',order.update),patch.object(self.e,'start_server',order.start):self.e.maintenance(self.p,True)
        self.assertEqual([c[0] for c in order.mock_calls],['update','start']);order.start.assert_called_once_with(self.p,'restart')

class RuntimeUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def test_browse_and_unsaved_checkboxes_survive_status_refresh(self):
        from PySide6.QtWidgets import QWidget,QFileDialog
        from PySide6.QtCore import Qt
        from runtime_tools_ui import RuntimeTools,ProgramDialog
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();studio=QWidget();studio.p={'id':'p','name':'Test'};studio.manager=Mock();studio.manager.state={'servers':[studio.p]};studio.guard=lambda fn:fn();widget=RuntimeTools(studio);widget.load(dict(id='p',programs=[program(root)]));widget.table.item(0,0).setCheckState(Qt.Unchecked);widget.update_status([dict(id='tool',status='running',pids=[42])]);self.assertFalse(widget.values()['programs'][0]['enabled']);self.assertIn('42',widget.table.item(0,4).text())
            dialog=ProgramDialog(widget)
            with patch.object(QFileDialog,'getOpenFileName',return_value=(str(root/'Bridge.exe'),'')):dialog.choose_exe()
            self.assertEqual(dialog.values()['path'],str(root/'Bridge.exe'));widget.deleteLater();dialog.deleteLater();studio.deleteLater()

class WindowsCompanionIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Real Windows EXE lifecycle')
    def test_real_exe_is_started_and_reused_without_duplicate(self):
        import sys
        with tempfile.TemporaryDirectory() as folder:
            p=program(Path(folder).resolve());p.update(path=sys.executable,args='-c "import time; time.sleep(20)"');supervisor=CompanionPrograms()
            try:
                supervisor.ensure([p],'start',lambda s:None,threading.Event());first=list(supervisor.launched.values());self.assertEqual(len(first),1);supervisor.ensure([p],'restart',lambda s:None,threading.Event());self.assertEqual(len(supervisor.launched),1);self.assertIs(list(supervisor.launched.values())[0],first[0]);self.assertIsNone(first[0].poll());supervisor.control(p,'restart',lambda s:None,threading.Event());self.assertIsNotNone(first[0].poll());self.assertEqual(supervisor.inspect(p)['status'],'running');supervisor.control(p,'stop',lambda s:None,threading.Event());self.assertEqual(supervisor.inspect(p)['status'],'stopped')
            finally:
                for proc in supervisor.launched.values():
                    if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
